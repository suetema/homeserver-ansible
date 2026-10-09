"""Narrow, explicitly authorized pre-OS checkpoint; secrets stay in private staging.

Upload beside the reviewed backup_remote.py; run only as root on ryback.
Does not alter deployments, app data or boot policy.
"""
import datetime
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import backup_remote as backup


BASE = Path('/var/backups/homelab-upgrade')


def run(args):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    if result.returncode:
        raise RuntimeError('Checkpoint command failed: ' + args[0])
    return result.stdout


def status(phase, milestone, next_step, blockers=None):
    value = dict(phase=phase, utc=datetime.datetime.utcnow().isoformat()+'Z',
                 command_category=phase, last_verified_milestone=milestone,
                 next_step=next_step, os=run(['lsb_release', '-ds']).decode().strip(),
                 kernel=os.uname().release,
                 k3s=run(['/usr/local/bin/k3s', '--version']).decode().splitlines()[0],
                 blockers=blockers or [])
    target = BASE / 'status.json'
    temporary = BASE / 'status.json.new'
    temporary.write_text(json.dumps(value, indent=2)+'\n')
    temporary.chmod(0o644)
    temporary.replace(target)


def prepare(run_id):
    os.umask(0o077)
    stage = backup.run_dir(run_id)
    stage.mkdir(parents=True, mode=0o700, exist_ok=False)
    (stage / '.owned-by-homelab-backup').write_text(run_id)
    payload = stage / 'payload'
    payload.mkdir(mode=0o700)
    mcp = backup.collect_mcp_recovery(payload)
    if mcp['processes_captured'] < 2 or not mcp['client_config_captured']:
        raise RuntimeError('Expected MCP recovery material missing')
    process_file = payload / 'backup-metadata/host/google-calendar-mcp-processes.json'
    processes = json.loads(process_file.read_text())
    for process in processes:
        process['uid'] = Path('/proc/'+process['pid']).stat().st_uid
        process['gid'] = Path('/proc/'+process['pid']).stat().st_gid
    process_file.write_text(json.dumps(processes, indent=2))
    # Preserve transient credentials privately on the host as well as off-host.
    private = BASE / 'mcp-recovery'
    private.mkdir(mode=0o700, exist_ok=False)
    shutil.copy2(str(process_file), str(private / 'processes.json'))
    shutil.copy2('/tmp/gcp-oauth.keys.json', str(private / 'gcp-oauth.keys.json'))
    for root in ['/boot', '/etc/apt', '/etc/default', '/etc/grub.d', '/etc/netplan',
                 '/etc/ssh', '/etc/systemd/system', '/etc/update-manager',
                 '/etc/fstab', '/etc/hosts', '/etc/hostname', '/etc/resolv.conf',
                 '/usr/local/bin/k3s', '/home/maarten/.config/google-calendar-mcp']:
        source = Path(root)
        if not source.exists():
            continue
        destination = payload / root.lstrip('/')
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(str(source), str(destination), symlinks=True)
        else:
            shutil.copy2(str(source), str(destination), follow_symlinks=False)
    metadata = payload / 'backup-metadata/host'
    for name, command in {
        'packages.txt': ['dpkg-query', '-W'],
        'manual-packages.txt': ['apt-mark', 'showmanual'],
        'holds.txt': ['apt-mark', 'showhold'],
        'mounts.txt': ['findmnt', '-o', 'TARGET,SOURCE,FSTYPE,UUID,OPTIONS'],
        'block-devices.json': ['lsblk', '-J', '-o', 'NAME,SIZE,FSTYPE,UUID,MOUNTPOINT'],
        'addresses.json': ['ip', '-j', 'address'],
        'routes.json': ['ip', '-j', 'route'],
        'firewall.txt': ['iptables-save'],
        'efi.txt': ['efibootmgr', '-v'],
        'pods.json': ['k3s', 'kubectl', 'get', 'pods', '-A', '-o', 'json'],
        'pvs.json': ['k3s', 'kubectl', 'get', 'pv,pvc', '-A', '-o', 'json'],
        'flux.json': ['k3s', 'kubectl', 'get', 'helmreleases,kustomizations', '-A', '-o', 'json'],
        'ingresses.json': ['k3s', 'kubectl', 'get', 'ingress', '-A', '-o', 'json'],
        'k3s-unit.txt': ['systemctl', 'cat', 'k3s'],
    }.items():
        (metadata / name).write_bytes(run(command))
    status('checkpoint-k3s-pause', 'preflight healthy', 'copy consistent SQLite and matching token')
    was_active = run(['systemctl', 'is-active', 'k3s']).strip() == b'active'
    if not was_active:
        raise RuntimeError('k3s not active before checkpoint')
    try:
        run(['systemctl', 'stop', 'k3s'])
        target = payload / 'var/lib/rancher/k3s/server'
        (target / 'db').mkdir(parents=True)
        for name in ['token', 'cred', 'tls']:
            source = Path('/var/lib/rancher/k3s/server') / name
            if source.is_dir():
                shutil.copytree(str(source), str(target / name), symlinks=True)
            elif source.exists():
                shutil.copy2(str(source), str(target / name))
        source = sqlite3.connect('file:/var/lib/rancher/k3s/server/db/state.db?mode=ro', uri=True)
        destination = sqlite3.connect(str(target / 'db/state.db'))
        try:
            source.backup(destination)
            if destination.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                raise RuntimeError('k3s snapshot integrity failure')
        finally:
            destination.close()
            source.close()
    finally:
        run(['systemctl', 'start', 'k3s'])
    (stage / 'report.json').write_text(json.dumps({'run_id': run_id, 'sqlite': []}))
    (BASE / 'checkpoint-run-id').write_text(run_id+'\n')
    status('checkpoint-transfer', 'consistent k3s snapshot captured; service restarted',
           'authenticate/hash-check encrypted Mac checkpoint')
    print(json.dumps(dict(run_id=run_id, mcp=mcp, k3s_restarted=True)))


if __name__ == '__main__':
    if os.geteuid() != 0:
        raise RuntimeError('Root required')
    if sys.argv[1] == 'prepare':
        prepare(sys.argv[2])
    elif sys.argv[1] == 'status':
        status(*sys.argv[2:5])
    else:
        raise ValueError('Unknown action')
