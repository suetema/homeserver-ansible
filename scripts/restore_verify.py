"""Decrypt selected exports and verify them in isolated, limited Docker containers.

Plaintext is temporary/private; no live app is stopped, changed or used as a
restore target. Docker is used only as a disposable Linux test harness on ryback.
"""

import io
import json
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone

import backup_to_mac as backup


def payload_name(name):
    if name.startswith("backup-metadata/postgres/") and name.endswith((".sql", ".dump")):
        return name.removeprefix("backup-metadata/")
    if name.startswith("etc/k8sconfigs/couchdb/data/"):
        return "couchdb/" + name.removeprefix("etc/k8sconfigs/couchdb/data/")
    if name == "etc/k8sconfigs/endurain/redis/dump.rdb":
        return "redis/dump.rdb"
    return None


def make_payload(archive, target, selector=payload_name):
    count = 0
    with tempfile.TemporaryFile() as errors:
        decrypt = subprocess.Popen([str(backup.AGE), "-d", "-i", str(backup.IDENTITY), str(archive)],
                                   stdout=subprocess.PIPE, stderr=errors)
        decompress = subprocess.Popen([backup.ZSTD, "-q", "-d", "-c"], stdin=decrypt.stdout,
                                      stdout=subprocess.PIPE, stderr=errors)
        decrypt.stdout.close()
        try:
            with tarfile.open(fileobj=decompress.stdout, mode="r|") as source:
                with tarfile.open(str(target), "w") as destination:
                    for member in source:
                        name = selector(member.name)
                        if not name or not member.isfile():
                            continue
                        backup.safe_name(name)
                        copied = tarfile.TarInfo(name)
                        copied.size = member.size
                        copied.mode = 0o600
                        destination.addfile(copied, source.extractfile(member))
                        count += 1
            while decompress.stdout.read(1024 * 1024):
                pass
            if decompress.wait() != 0 or decrypt.wait() != 0:
                raise RuntimeError("Restore payload authentication/decompression failed")
        finally:
            for child in [decompress, decrypt]:
                if child.poll() is None:
                    child.terminate()
                child.wait()
                if child.stdout and not child.stdout.closed:
                    child.stdout.close()
    return count


def remote(action, run_id, payload=None):
    script = Path(__file__).with_name("restore_verify_remote.py").read_text()
    command = "sudo -n python3 -c " + shlex.quote(script) + " " + action + " " + run_id
    result = subprocess.run(backup.SSH + [command], stdin=payload or subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3600)
    if result.returncode:
        print(result.stderr.decode(errors="replace")[-1500:], file=sys.stderr)
        raise RuntimeError("Isolated restore test failed; private test staging retained")
    return json.loads(result.stdout)


def main():
    os.umask(0o077)
    if len(sys.argv) != 2:
        raise ValueError("Usage: restore_verify.py BACKUP-RUN-ID")
    backup_id = sys.argv[1]
    # Reuse the strict identifier validation; no paths may escape the backup root.
    import restore_verify_remote
    restore_verify_remote.stage_for(backup_id)
    folder = backup.ROOT / backup_id
    original = json.loads((folder / "verification.json").read_text())
    archive = folder / "databases.tar.zst.age"
    recorded = next(row for row in original["archives"] if row["archive"] == archive.name)
    if backup.digest_file(archive) != recorded["sha256"]:
        raise RuntimeError("Encrypted archive changed since verification")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
    report = {"run_id": run_id, "backup_run_id": backup_id, "status": "preparing"}
    report_path = folder / ("restore-test-" + run_id + ".json")
    report_path.write_text(json.dumps(report, indent=2))
    print("Isolated restore run: " + run_id, flush=True)
    with tempfile.TemporaryDirectory(prefix="restore-payload-", dir=str(folder)) as temporary:
        payload = Path(temporary) / "payload.tar"
        print("Preparing authenticated exports for isolated tests", flush=True)
        report["payload_files"] = make_payload(archive, payload)
        with payload.open("rb") as handle:
            report["transfer"] = remote("receive", run_id, handle)
        report_path.write_text(json.dumps(report, indent=2))
        print("Testing PostgreSQL and CouchDB imports; no live volumes or published ports", flush=True)
        report["results"] = remote("run", run_id)
        report["cleanup"] = remote("cleanup", run_id)
    report["status"] = "verified"
    report_path.write_text(json.dumps(report, indent=2))
    print("Full PostgreSQL imports verified: " + str(len(report["results"]["postgres"])), flush=True)
    print("CouchDB restored databases readable: " + str(len(report["results"]["couchdb"]["databases"])), flush=True)
    print("Disposable test containers and plaintext staging removed", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Restore verification stopped: " + type(error).__name__, file=sys.stderr)
        sys.exit(1)
