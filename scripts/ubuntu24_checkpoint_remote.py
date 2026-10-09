"""Fresh narrow pre-Noble recovery checkpoint; encrypted transfer uses reviewed helper.

No deployment edits or app-state copies. Secrets are root-only and never printed.
Retains historical status and previously captured auth records without requiring
stale callback processes to remain running.
"""
import datetime
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys

import backup_remote as backup
from ubuntu22_checkpoint_remote import run, BASE


def status(phase, milestone, next_step, blockers=None):
    target = BASE / 'status.json'
    value = json.loads(target.read_text()) if target.exists() else {}
    history = value.setdefault('historical_milestones', [])
    if value.get('phase') and value.get('phase') != phase:
        history.append({k: value.get(k) for k in
                        ['phase', 'utc', 'last_verified_milestone', 'os', 'kernel', 'checkpoint']})
    value.update(phase=phase, utc=datetime.datetime.utcnow().isoformat()+'Z',
                 command_category=phase, running_command_category=phase,
                 last_verified_milestone=milestone, next_step=next_step,
                 os=run(['lsb_release', '-ds']).decode().strip(), kernel=os.uname().release,
                 k3s=run(['/usr/local/bin/k3s', '--version']).decode().splitlines()[0],
                 blockers=blockers or [],
                 nonblocking_issues=['Dormant Compose v1 Python import failure; preserved, not incidentally repaired.'],
                 local_status_doc='docs/ubuntu-24-upgrade-2026-10-09.md')
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
    private = BASE / 'mcp-recovery'
    if not (private / 'processes.json').is_file() or not (private / 'gcp-oauth.keys.json').is_file():
        raise RuntimeError('Private MCP recovery records missing')
    roots = ['/boot', '/etc/apt', '/etc/default', '/etc/grub.d', '/etc/netplan',
             '/etc/ssh', '/etc/systemd', '/etc/update-manager', '/etc/rancher',
             '/etc/fstab', '/etc/hosts', '/etc/hostname', '/etc/resolv.conf',
             '/etc/sudoers', '/etc/sudoers.d', '/etc/sysctl.conf', '/etc/sysctl.d',
             '/etc/modprobe.d', '/etc/modules-load.d', '/etc/udev/rules.d', '/etc/ufw',
             '/usr/local/bin/k3s', '/var/lib/rancher/k3s/agent/etc',
             '/home/maarten/.config/google-calendar-mcp',
             '/home/maarten/.config/homelab-upgrade', '/tmp/gcp-oauth.keys.json', str(private)]
    for root in roots:
        source = Path(root)
        if not source.exists():
            if root in ['/tmp/gcp-oauth.keys.json', '/home/maarten/.config/homelab-upgrade']:
                raise RuntimeError('Expected OAuth recovery path missing')
            continue
        destination = payload / root.lstrip('/')
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(str(source), str(destination), symlinks=True)
        else:
            shutil.copy2(str(source), str(destination), follow_symlinks=False)
    metadata = payload / 'backup-metadata/host'
    metadata.mkdir(parents=True)
    for name, command in {
        'packages.txt': ['dpkg-query', '-W'], 'manual-packages.txt': ['apt-mark', 'showmanual'],
        'holds.txt': ['apt-mark', 'showhold'],
        'mounts.txt': ['findmnt', '-o', 'TARGET,SOURCE,FSTYPE,UUID,OPTIONS'],
        'block-devices.json': ['lsblk', '-J', '-o', 'NAME,SIZE,FSTYPE,UUID,MOUNTPOINT'],
        'addresses.json': ['ip', '-j', 'address'], 'routes.json': ['ip', '-j', 'route'],
        'firewall.txt': ['iptables-save'], 'efi.txt': ['efibootmgr', '-v'],
        'pods.json': ['k3s', 'kubectl', 'get', 'pods', '-A', '-o', 'json'],
        'pvs.json': ['k3s', 'kubectl', 'get', 'pv,pvc', '-A', '-o', 'json'],
        'flux.json': ['k3s', 'kubectl', 'get', 'helmreleases,kustomizations', '-A', '-o', 'json'],
        'gpu-deployments.json': ['k3s', 'kubectl', 'get', 'ds,sts', '-A', '-o', 'json'],
        'nodes.json': ['k3s', 'kubectl', 'get', 'nodes', '-o', 'json'],
        'ingresses.json': ['k3s', 'kubectl', 'get', 'ingress', '-A', '-o', 'json'],
        'k3s-unit.txt': ['systemctl', 'cat', 'k3s'],
        'ssh-units.txt': ['systemctl', 'cat', 'ssh.service', 'ssh.socket'],
    }.items():
        (metadata / name).write_bytes(run(command))
    status('noble-checkpoint-k3s-pause', 'Jammy/GPU baseline accepted; fresh metadata reviewed',
           'stopped SQLite snapshot plus matching token, then restart control plane')
    if run(['systemctl', 'is-active', 'k3s']).strip() != b'active':
        raise RuntimeError('k3s must be active before checkpoint')
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
                raise RuntimeError('Snapshot SQLite integrity failure')
        finally:
            destination.close()
            source.close()
    finally:
        run(['systemctl', 'start', 'k3s'])
    (stage / 'report.json').write_text(json.dumps({'run_id': run_id, 'sqlite': []}))
    (BASE / 'noble-checkpoint-run-id').write_text(run_id+'\n')
    status('noble-checkpoint-transfer', 'consistent SQLite/token captured; k3s restarted',
           'encrypt/authenticate/hash/SQLite-check on Mac, including post-GPU local Flux')
    print(json.dumps({'run_id': run_id, 'k3s_restarted': True, 'mcp_private_material_captured': True,
                      'application_data_copied': False}))


if __name__ == '__main__':
    if os.geteuid() != 0:
        raise RuntimeError('Root required')
    if sys.argv[1] == 'prepare':
        prepare(sys.argv[2])
    elif sys.argv[1] == 'status':
        status(*sys.argv[2:5])
    else:
        raise ValueError('Unknown action')
