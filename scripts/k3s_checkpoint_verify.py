"""Encrypt fetched private tar, authenticate EVERY byte, check hashes and SQLite.

No SSH or live mutations. Invoked by Ansible on the Mac. Whole DB directory is
restored together (including WAL), so immutable=1 must NOT bypass its WAL state.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import subprocess
import sys
import tarfile
import tempfile


def safe_name(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or not p.parts:
        raise ValueError('Unsafe archive path')
    return p


def verify(archive, age, identity, parent):
    hashes, manifest, pairing = {}, None, None
    with tempfile.TemporaryDirectory(prefix='sqlite-verify-', dir=parent) as temp:
        dbroot = Path(temp)
        with tempfile.TemporaryFile() as errors:
            process = subprocess.Popen([str(age), '-d', '-i', str(identity), str(archive)],
                                       stdout=subprocess.PIPE, stderr=errors)
            try:
                with tarfile.open(fileobj=process.stdout, mode='r|') as tar:
                    for member in tar:
                        name = str(safe_name(member.name))
                        if member.isdir() or member.issym():
                            continue
                        if not member.isfile():
                            raise RuntimeError('Unexpected archive member type')
                        if name in hashes:
                            raise RuntimeError('Duplicate archive path')
                        h = hashlib.sha256()
                        data = bytearray() if name in ['backup-metadata/manifest.json',
                                                      'backup-metadata/pairing.json'] else None
                        target = None
                        if name.startswith('var/lib/rancher/k3s/server/db/'):
                            target = dbroot / name
                            target.parent.mkdir(parents=True, exist_ok=True)
                        handle = target.open('xb') if target else None
                        member_stream = tar.extractfile(member)
                        try:
                            for chunk in iter(lambda: member_stream.read(1024 * 1024), b''):
                                h.update(chunk)
                                if data is not None:
                                    data.extend(chunk)
                                if handle:
                                    handle.write(chunk)
                        finally:
                            member_stream.close()
                            if handle:
                                handle.close()
                        hashes[name] = h.hexdigest()
                        if name == 'backup-metadata/manifest.json':
                            manifest = json.loads(data)
                        if name == 'backup-metadata/pairing.json':
                            pairing = json.loads(data)
                # Tar EOF alone does not authenticate the final age chunk.
                while process.stdout.read(1024 * 1024):
                    pass
                if process.wait(timeout=60):
                    raise RuntimeError('Age authentication failure')
            finally:
                if process.poll() is None:
                    process.terminate()
                process.wait()
                process.stdout.close()
        if not manifest or not pairing:
            raise RuntimeError('Missing recovery metadata')
        expected = {f['path']: f['sha256'] for f in manifest['files']}
        actual = {k: v for k, v in hashes.items() if k != 'backup-metadata/manifest.json'}
        if expected != actual:
            raise RuntimeError('Recovery manifest mismatch')
        for required in ['var/lib/rancher/k3s/server/db/state.db',
                         'var/lib/rancher/k3s/server/token', 'usr/local/bin/k3s',
                         'etc/systemd/system/k3s.service']:
            if required not in hashes:
                raise RuntimeError('Missing required recovery file')
        if hashes['usr/local/bin/k3s'] != pairing['sha256']:
            raise RuntimeError('Wrong matching binary')
        if pairing.get('unit_sha256') and hashes['etc/systemd/system/k3s.service'] != pairing['unit_sha256']:
            raise RuntimeError('Wrong matching service configuration')
        db = dbroot / 'var/lib/rancher/k3s/server/db/state.db'
        with sqlite3.connect('file:' + str(db) + '?mode=rw', uri=True) as connection:
            if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise RuntimeError('Native restored SQLite integrity failure')
            # Requires the actual Kine schema, including any WAL-only schema/data.
            connection.execute('SELECT id FROM kine LIMIT 1').fetchall()
        return dict(pairing, status='verified', verified_regular_files=len(hashes),
                    sqlite_integrity='ok', age_authenticated_to_eof=True)


def main():
    os.umask(0o077)
    source, age, identity, recipient = map(Path, sys.argv[1:5])
    if source.is_symlink() or source.parent.stat().st_mode & 0o077:
        raise RuntimeError('Non-private plaintext stage')
    source.chmod(0o600)
    archive = source.with_suffix('.tar.age')
    partial = archive.with_suffix('.age.partial')
    if archive.exists() or partial.exists():
        raise RuntimeError('Refusing checkpoint overwrite')
    result = subprocess.run([str(age), '-R', str(recipient), '-o', str(partial), str(source)],
                            capture_output=True, timeout=300)
    if result.returncode:
        raise RuntimeError('Encryption failed')
    partial.chmod(0o600)
    partial.rename(archive)
    receipt = verify(archive, age, identity, source.parent)
    receipt.update(archive=archive.name, encrypted_bytes=archive.stat().st_size)
    (source.parent / 'verified.json').write_text(json.dumps(receipt, indent=2))
    source.unlink()  # only our fetched file, only after authenticated verification
    print(json.dumps(receipt))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('Private checkpoint verification failed; staging retained.', file=sys.stderr)
        sys.exit(1)
