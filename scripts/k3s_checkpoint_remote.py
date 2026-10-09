"""Ansible-only checkpoint actions; never stop/start services inside this helper.

Whole stopped SQLite directory and matching bootstrap material, NOT app/PVC data.
Failures retain private staging. Secret file paths/hashes live only in the archive.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tarfile

BASE = Path('/var/backups/homelab-upgrade')
SERVER = Path('/var/lib/rancher/k3s/server')


def stage_path(run_id):
    if not re.fullmatch(r'k3s-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}', run_id):
        raise ValueError('Invalid owned run ID')
    return BASE / run_id


def status(phase, target):
    path = BASE / 'status.json'
    value = json.loads(path.read_text()) if path.exists() else {}
    value.setdefault('historical_milestones', []).append(
        {k: value.get(k) for k in ['phase', 'utc', 'last_verified_milestone', 'os', 'kernel', 'checkpoint']})
    blocked = 'blocked' in phase
    terminal = blocked or phase == 'k3s-accepted' or phase.startswith('validated-')
    if blocked:
        next_step = 'Approve current-version GitOps image/chart isolation'
    elif phase.startswith('validated-'):
        next_step = 'Maintenance complete; no automatic subsequent minor'
    else:
        next_step = 'Validate the current hop; no automatic subsequent minor'
    value.update(phase=phase, utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 command_category='k3s-ansible',
                 running_command_category=None if terminal else 'k3s-ansible',
                 next_step=next_step,
                 k3s_target=target, local_status_doc='docs/k3s-upgrade-execution-2026-10-09.md')
    temporary = BASE / 'status.json.k3s-new'
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def stopped():
    result = subprocess.run(['systemctl', 'show', 'k3s', '-p', 'MainPID', '-p', 'ActiveState'],
                            capture_output=True, timeout=15, check=True).stdout.decode()
    if 'MainPID=0' not in result or 'ActiveState=inactive' not in result:
        raise RuntimeError('Checkpoint requires Ansible-stopped service with no main PID')
    for process in Path('/proc').glob('[0-9]*'):
        for fd in (process / 'fd').glob('*'):
            try:
                target = os.readlink(fd)
            except FileNotFoundError:
                continue
            if target.startswith(str(SERVER / 'db') + '/'):
                raise RuntimeError('Datastore still open by a process; refusing copy')


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def capture_payload(run_id, baseline):
    stopped()
    stage = stage_path(run_id)
    stage.mkdir(mode=0o700, exist_ok=False)
    (stage / '.owned-k3s').write_text(run_id)
    payload = stage / 'payload'
    payload.mkdir(mode=0o700)
    roots = [str(SERVER / n) for n in ['db', 'token', 'cred', 'tls', 'manifests']]
    roots += ['/usr/local/bin/k3s', '/etc/systemd/system/k3s.service',
              '/etc/systemd/system/k3s.service.env', '/etc/systemd/system/k3s.service.d',
              '/etc/default/k3s', '/etc/sysconfig/k3s', '/etc/rancher',
              '/var/lib/rancher/k3s/agent/etc', '/etc/fstab']
    for root in roots:
        source = Path(root)
        if not source.exists():
            if root in [str(SERVER / 'db'), str(SERVER / 'token'), '/usr/local/bin/k3s',
                        '/etc/systemd/system/k3s.service']:
                raise RuntimeError('Required recovery material missing')
            continue
        destination = payload / root.lstrip('/')
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination, symlinks=True)
        else:
            shutil.copy2(source, destination, follow_symlinks=False)
    stopped()
    metadata = payload / 'backup-metadata'
    metadata.mkdir(mode=0o700)
    captured = datetime.datetime.now(datetime.timezone.utc).timestamp()
    pairing = {'run_id': run_id, 'captured_epoch': captured, 'version': baseline['version'],
               'sha256': baseline['sha256'], 'unit_sha256': baseline['unit_sha256'],
               'no_datastore_open_descriptors': True, 'main_pid': 0,
               'scope': 'whole SQLite directory + token/config/TLS; no app/PVC backup'}
    (metadata / 'pairing.json').write_text(json.dumps(pairing))
    (metadata / 'inventory.json').write_text(json.dumps(baseline))
    files = []
    for p in sorted(payload.rglob('*')):
        if p.is_file() and not p.is_symlink():
            with p.open('rb') as handle:
                os.fsync(handle.fileno())
            files.append({'path': str(p.relative_to(payload)), 'sha256': sha256(p)})
        elif not p.is_dir() and not p.is_symlink():
            raise RuntimeError('Special file in recovery payload')
    (metadata / 'manifest.json').write_text(json.dumps({'files': files}))
    if sha256(payload / 'usr/local/bin/k3s') != baseline['sha256'] or sha256(payload / 'etc/systemd/system/k3s.service') != baseline['unit_sha256']:
        raise RuntimeError('Captured binary/unit does not match accepted pairing')
    archive = stage / 'checkpoint.tar.partial'
    with tarfile.open(archive, 'w') as tar:
        for p in sorted(payload.rglob('*')):
            tar.add(p, arcname=str(p.relative_to(payload)), recursive=False)
    archive.chmod(0o600)
    with archive.open('rb') as handle:
        os.fsync(handle.fileno())
    stopped()
    archive.replace(stage / 'checkpoint.tar')
    fd = os.open(stage, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    print(json.dumps(pairing))


def capture(run_id, baseline):
    # Host-local deadline survives a lost SSH controller. Partial output stays
    # private, never becomes checkpoint.tar and never deletes the source DB.
    def expired(signum, frame):
        raise TimeoutError('Stopped capture deadline exceeded')
    previous = signal.signal(signal.SIGALRM, expired)
    signal.alarm(60)
    try:
        capture_payload(run_id, baseline)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def cleanup(run_id):
    stage = stage_path(run_id)
    if stage.is_symlink() or (stage / '.owned-k3s').read_text() != run_id:
        raise RuntimeError('Wrong checkpoint owner')
    receipt = json.loads((stage / 'verified.json').read_text())
    if receipt.get('run_id') != run_id or receipt.get('status') != 'verified':
        raise RuntimeError('No verified encrypted off-host receipt')
    shutil.rmtree(stage)


if __name__ == '__main__':
    os.umask(0o077)
    try:
        if os.geteuid() != 0:
            raise RuntimeError('Root required')
        if sys.argv[1] == 'capture':
            capture(sys.argv[2], json.loads(sys.stdin.read()))
        elif sys.argv[1] == 'cleanup':
            cleanup(sys.argv[2])
        elif sys.argv[1] == 'status':
            status(sys.argv[2], sys.argv[3])
        else:
            raise ValueError('Unknown action')
    except Exception:
        print('Checkpoint action failed; private evidence retained, no raw error output.', file=sys.stderr)
        sys.exit(1)
