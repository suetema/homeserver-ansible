"""Temporary Ansible-managed host-local checkpoint recovery safeguard.

ONLY starts the unchanged, checksum-matching existing k3s service. Never copies
an old executable, restores/downgrades a datastore, stops workloads, or reboots.
Armed before the checkpoint pause; disarmed and timer/service proven inactive
before binary promotion. All metadata is credential-free and root-private.
"""
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

BASE = Path('/var/backups/homelab-upgrade')
META = BASE / 'k3s-checkpoint-guard.json'
BINARY = Path('/usr/local/bin/k3s')
UNIT = Path('/etc/systemd/system/k3s.service')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_metadata():
    if META.is_symlink() or META.stat().st_uid != os.geteuid() or META.stat().st_mode & 0o777 != 0o600:
        raise RuntimeError('Unsafe safeguard metadata')
    return json.loads(META.read_text())


def write_metadata(value):
    temporary = META.with_suffix('.json.new')
    if temporary.is_symlink():
        raise RuntimeError('Unsafe metadata stage')
    with temporary.open('w') as handle:
        os.fchmod(handle.fileno(), 0o600)
        json.dump(value, handle)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(META)
    fd = os.open(BASE, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextlib.contextmanager
def lock():
    with (BASE / 'k3s-checkpoint-guard.lock').open('a') as handle:
        os.fchmod(handle.fileno(), 0o600)
        deadline = time.monotonic() + 5
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Safeguard lock deadline exceeded')
                time.sleep(0.1)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def arm(run_id, binary_sha256, unit_sha256):
    with lock():
        if META.exists() and read_metadata().get('armed'):
            raise RuntimeError('An earlier checkpoint safeguard is still armed')
        if digest(BINARY) != binary_sha256 or digest(UNIT) != unit_sha256:
            raise RuntimeError('Current immutable binary/unit pairing changed before arm')
        write_metadata({'run_id': run_id, 'binary_sha256': binary_sha256,
                        'unit_sha256': unit_sha256, 'armed': True,
                        'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        'action': 'armed_unchanged_binary_only'})


def disarm(run_id):
    with lock():
        value = read_metadata()
        if value['run_id'] != run_id:
            raise RuntimeError('Wrong safeguard owner')
        value.update(armed=False, action='disarmed_before_promotion')
        write_metadata(value)


def fire():
    with lock():
        value = read_metadata()
        if not value.get('armed'):
            return 'disarmed_no_action'
        # In particular: never execute an old binary over a migrated DB. If a
        # promotion somehow already occurred, fail closed rather than downgrade.
        if digest(BINARY) != value['binary_sha256'] or digest(UNIT) != value['unit_sha256']:
            value.update(armed=False, action='identity_changed_no_action')
            write_metadata(value)
            return value['action']
        subprocess.run(['systemctl', 'start', '--no-block', 'k3s'],
                       capture_output=True, check=True, timeout=10)
        value.update(armed=False, action='started_unchanged_service_after_checkpoint_deadline',
                     fired_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        write_metadata(value)
        return value['action']


if __name__ == '__main__':
    os.umask(0o077)
    try:
        if os.geteuid() != 0:
            raise RuntimeError('Root required')
        if sys.argv[1] == 'arm':
            arm(*sys.argv[2:5])
        elif sys.argv[1] == 'disarm':
            disarm(sys.argv[2])
        elif sys.argv[1] == 'fire':
            print(json.dumps({'action': fire()}))
        else:
            raise RuntimeError('Unknown safeguard action')
    except Exception:
        print('Checkpoint safeguard failed closed; no raw/private output.', file=sys.stderr)
        sys.exit(1)
