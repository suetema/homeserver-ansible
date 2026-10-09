"""Pull encrypted backups, verify all archived file hashes, and test SQLite restores.

No deployment changes, service stops, media backup or automatic live restoration.
Requires the privately installed age tools; private identity never leaves the Mac.
"""

import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from contextlib import closing
from datetime import datetime, timezone


HOME = Path.home()
ROOT = HOME / "homelab-backups" / "ryback"
AGE = HOME / "homelab-backups/tools/age-v1.3.2/age"
IDENTITY = HOME / ".config/homelab-backup/ryback.agekey"
RECIPIENT = HOME / "homelab-backups/tools/ryback.recipient"
ZSTD = shutil.which("zstd")
REMOTE_SCRIPT = Path(__file__).with_name("backup_remote.py")
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o",
       "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3", "192.168.1.110"]


def digest_file(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def safe_name(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("Unsafe archive member")
    return path


def remote(action, run_id):
    result = subprocess.run(SSH + ["sudo -n python3 - " + action + " " + run_id],
                            input=REMOTE_SCRIPT.read_bytes(), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=1800)
    if result.returncode:
        # This helper captures all child stderr and emits only safe phase/path logs.
        print(result.stderr.decode(errors="replace")[-4000:], file=sys.stderr)
        raise RuntimeError("Remote backup preparation/cleanup failed; staging retained")
    return json.loads(result.stdout)


def encrypt_stream(destination, producer):
    partial = destination.with_suffix(destination.suffix + ".partial")
    if destination.exists() or partial.exists():
        raise RuntimeError("Refusing backup overwrite")
    children = []
    with tempfile.TemporaryFile() as errors:
        try:
            source = producer(errors)
            children.append(source)
            compressed = subprocess.Popen([ZSTD, "-q", "-3", "-T2", "-c"],
                                          stdin=source.stdout, stdout=subprocess.PIPE,
                                          stderr=errors)
            children.append(compressed)
            source.stdout.close()
            encrypted = subprocess.Popen([str(AGE), "-R", str(RECIPIENT), "-o", str(partial)],
                                         stdin=compressed.stdout, stderr=errors)
            children.append(encrypted)
            compressed.stdout.close()
            statuses = [child.wait() for child in reversed(children)]
            if any(statuses):
                raise RuntimeError("Backup stream failed; partial archive retained")
            partial.chmod(0o600)
            partial.rename(destination)
        finally:
            for child in children:
                if child.poll() is None:
                    child.terminate()
            for child in children:
                child.wait()


def server_archive(destination, run_id, category):
    def producer(errors):
        process = subprocess.Popen(
            SSH + ["sudo -n python3 - archive " + run_id + " " + category],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors)
        process.stdin.write(REMOTE_SCRIPT.read_bytes())
        process.stdin.close()
        return process
    encrypt_stream(destination, producer)


def local_recovery_archive(destination):
    # Includes uncommitted user work and Git history, entirely encrypted.
    directories = [HOME / "Documents/homeserver-ansible", HOME / "Documents/homelab-flux"]
    key = HOME / ".config/sops/age/keys.txt"
    if key.is_file():
        directories.append(key)

    def producer(errors):
        command = ["/usr/bin/tar", "-c", "--exclude=.DS_Store", "--exclude=.ansible", "--exclude=node_modules",
                   "--exclude=.venv", "--exclude=__pycache__", "-C", str(HOME)]
        command.extend(str(p.relative_to(HOME)) for p in directories)
        return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors,
                                env=dict(os.environ, COPYFILE_DISABLE="1"))
    encrypt_stream(destination, producer)


def verify(destination, workdir):
    hashes, manifests, sqlite_tests = {}, [], []
    with tempfile.TemporaryFile() as errors:
        decrypt = subprocess.Popen([str(AGE), "-d", "-i", str(IDENTITY), str(destination)],
                                   stdout=subprocess.PIPE, stderr=errors)
        decompress = subprocess.Popen([ZSTD, "-q", "-d", "-c"], stdin=decrypt.stdout,
                                      stdout=subprocess.PIPE, stderr=errors)
        decrypt.stdout.close()
        try:
            with tarfile.open(fileobj=decompress.stdout, mode="r|") as archive:
                for member in archive:
                    name = str(safe_name(member.name))
                    if not member.isfile():
                        continue
                    handle = archive.extractfile(member)
                    hasher = hashlib.sha256()
                    is_manifest = name.startswith("backup-metadata/") and name.endswith("-file-manifest.json")
                    is_sqlite = destination.name.startswith("databases") and name.endswith((".db", ".sqlite", ".sqlite3"))
                    contents = bytearray() if is_manifest else None
                    restored = None
                    target = None
                    if is_sqlite:
                        target = workdir / (secrets.token_hex(8) + ".sqlite")
                        restored = target.open("xb")
                    try:
                        for block in iter(lambda: handle.read(1024 * 1024), b""):
                            hasher.update(block)
                            if contents is not None:
                                contents.extend(block)
                            if restored:
                                restored.write(block)
                    finally:
                        if restored:
                            restored.close()
                    hashes[name] = hasher.hexdigest()
                    if contents is not None:
                        manifests.append(json.loads(contents))
                    if target:
                        with target.open("rb") as file_handle:
                            sqlite_header = file_handle.read(16) == b"SQLite format 3\x00"
                        if sqlite_header:
                            # These are complete, closed SQLite backup-API snapshots,
                            # not live databases. Apple SQLite otherwise tries to open
                            # missing WAL sidecars even for read-only standalone copies.
                            with closing(sqlite3.connect("file:" + str(target) +
                                                        "?mode=ro&immutable=1", uri=True)) as database:
                                count = database.execute("SELECT count(*) FROM sqlite_master").fetchone()[0]
                                try:
                                    check = database.execute("PRAGMA quick_check").fetchall()
                                    if check != [("ok",)]:
                                        raise RuntimeError("Restored SQLite integrity failure")
                                    status = "ok"
                                except sqlite3.OperationalError as error:
                                    if "collation" not in str(error) and "no such function" not in str(error):
                                        raise
                                    status = "requires_application_sqlite_extensions"
                                sqlite_tests.append({"source": name, "schema_objects": count,
                                                     "quick_check": status})
                        target.unlink()
            # Drain through EOF to check zstd/age truncation and authentication.
            while decompress.stdout.read(1024 * 1024):
                pass
            if decompress.wait() != 0 or decrypt.wait() != 0:
                raise RuntimeError("Archive decryption/decompression failed")
        finally:
            for process in [decompress, decrypt]:
                if process.poll() is None:
                    process.terminate()
                process.wait()
                if process.stdout and not process.stdout.closed:
                    process.stdout.close()
    for manifest in manifests:
        for row in manifest["files"]:
            if hashes.get(row["path"]) != row["sha256"]:
                raise RuntimeError("Archived file hash mismatch")
    if not destination.name.startswith("local-") and len(manifests) != 1:
        raise RuntimeError("Missing server archive manifest")
    return {"archive": destination.name, "encrypted_bytes": destination.stat().st_size,
            "sha256": digest_file(destination), "verified_regular_files": len(hashes),
            "file_hashes_verified": bool(manifests), "sqlite_restore_tests": sqlite_tests,
            "online_changed_files": [p for m in manifests for p in m["changed_during_read"]],
            "missing_paths": [p for m in manifests for p in m["missing_paths"]],
            "special_or_cross_device_skipped": [p for m in manifests for p in m["special_or_cross_device_skipped"]]}


def main():
    os.umask(0o077)
    if not ZSTD or not AGE.is_file() or not IDENTITY.is_file():
        raise RuntimeError("Backup encryption/compression prerequisites missing")
    ROOT.mkdir(parents=True, mode=0o700, exist_ok=True)
    if shutil.disk_usage(ROOT).free < 45 * 1024 ** 3:
        raise RuntimeError("Insufficient Mac free space")
    resume = len(sys.argv) == 3 and sys.argv[1] == "--resume"
    if len(sys.argv) != 1 and not resume:
        raise ValueError("Usage: backup_to_mac.py [--resume RUN-ID]")
    if resume:
        import re
        run_id = sys.argv[2]
        if not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}", run_id):
            raise ValueError("Invalid resume run ID")
    else:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
    destination = ROOT / run_id
    if destination.is_symlink():
        raise RuntimeError("Refusing symlink backup directory")
    destination.mkdir(mode=0o700, exist_ok=resume)
    result = {"run_id": run_id, "status": "preparing", "archives": [],
              "identity_path": str(IDENTITY), "media_disk_backed_up": False,
              "media_exceptions": ["/mnt/volume1/books", "/mnt/volume1/k8s-books"],
              "services_stopped": False, "upgrade_ready": False}
    report_path = destination / "verification.json"
    if resume:
        result = json.loads(report_path.read_text())
        if result["run_id"] != run_id or result["status"] == "verified_online_baseline":
            raise RuntimeError("Invalid/already completed resume manifest")
    report_path.write_text(json.dumps(result, indent=2))
    print("Backup destination: " + str(destination), flush=True)
    print("Creating online database snapshots and native exports...", flush=True)
    result["preparation"] = remote("prepare-resume" if resume else "prepare", run_id)
    report_path.write_text(json.dumps(result, indent=2))
    with tempfile.TemporaryDirectory(prefix="restore-test-", dir=str(destination)) as temporary:
        workdir = Path(temporary)
        for category in ["databases", "host", "applications", "book-exceptions", "local-recovery"]:
            archive = destination / (category + ".tar.zst.age")
            if archive.exists() and resume:
                print("Re-verifying existing encrypted archive: " + category, flush=True)
                verified = verify(archive, workdir)
                result["archives"] = [a for a in result["archives"] if a["archive"] != archive.name]
                result["archives"].append(verified)
                report_path.write_text(json.dumps(result, indent=2))
                continue
            print("Transferring encrypted " + category + " archive...", flush=True)
            if category == "local-recovery":
                local_recovery_archive(archive)
            else:
                server_archive(archive, run_id, category)
            print("Verifying decryption, archive contents and file hashes: " + category, flush=True)
            result["archives"].append(verify(archive, workdir))
            report_path.write_text(json.dumps(result, indent=2))
    result["cleanup"] = remote("cleanup", run_id)
    result["status"] = "verified_online_baseline"
    result["completed_utc"] = datetime.now(timezone.utc).isoformat()
    report_path.write_text(json.dumps(result, indent=2))
    print(json.dumps({"status": result["status"], "run_id": run_id,
                      "encrypted_GiB": round(sum(a["encrypted_bytes"] for a in result["archives"]) / 1024**3, 2),
                      "sqlite_restore_tests": sum(len(a["sqlite_restore_tests"]) for a in result["archives"]),
                      "upgrade_ready": result["upgrade_ready"]}), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Backup stopped safely: " + type(error).__name__ + "; no live state restored or services stopped", file=sys.stderr)
        sys.exit(1)
