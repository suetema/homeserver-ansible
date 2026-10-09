"""Backup-only helper, sent over SSH; never modifies application configuration.

Only prepare writes, into a new root-only staging directory. Live SQLite sources
are opened read-only. PostgreSQL and Redis exports use existing container tools.
File archives remain online captures, not atomic multi-application snapshots.
"""

import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tarfile
import time
from contextlib import closing
from urllib.parse import quote


ROOTS = [Path("/etc/k8sconfigs"), Path("/etc/dockerconfigs"),
         Path("/var/lib/rancher/k3s/storage")]
BOOK_ROOTS = [Path("/mnt/volume1/books"), Path("/mnt/volume1/k8s-books")]
STATE = Path("/var/lib/rancher/k3s/server/db/state.db")
STAGING = Path("/var/backups/homelab-agent")
PG_PATHS = [Path("/etc/k8sconfigs/endurain/postgres"),
            Path("/etc/k8sconfigs/velomate/postgres")]
REDIS_PATH = Path("/etc/k8sconfigs/endurain/redis")
REPRODUCIBLE_PATHS = [Path("/etc/k8sconfigs/suwayomi/cache")]
MCP_CLIENT_CONFIG = Path("/tmp/gcp-oauth.keys.json")


def run_dir(run_id):
    if not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}", run_id):
        raise ValueError("Invalid backup run ID")
    return STAGING / run_id


def command(args, timeout=120, output=None):
    result = subprocess.run(args, stdin=subprocess.DEVNULL,
                            stdout=output or subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout)
    if result.returncode:
        # Do not echo commands, stderr, credentials, or raw responses.
        raise RuntimeError("{} backup command failed (exit {})".format(args[0], result.returncode))
    return result.stdout


def kube(*args):
    return command(["k3s", "kubectl"] + list(args))


def pod_for(namespace, container):
    pods = json.loads(kube("get", "pods", "-n", namespace, "-o", "json"))["items"]
    matches = [p for p in pods if p["status"]["phase"] == "Running"
               and any(c["name"] == container for c in p["spec"]["containers"])]
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one database pod")
    return matches[0]["metadata"]["name"]


def sqlite_sources(roots=None):
    found = [STATE] if roots is None else []
    for root in (ROOTS + BOOK_ROOTS if roots is None else roots):
        for base, dirs, files in os.walk(str(root), followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in {"container_cache", ".cache"})
            if any(under(Path(base), cache) for cache in REPRODUCIBLE_PATHS):
                dirs[:] = []
                continue
            for name in sorted(files):
                if not name.endswith((".db", ".sqlite", ".sqlite3")):
                    continue
                path = Path(base) / name
                if path.is_symlink() or not path.is_file():
                    continue
                with path.open("rb") as handle:
                    if handle.read(16) == b"SQLite format 3\x00":
                        found.append(path)
    return found


def snapshot_sqlite(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    uri = "file:" + quote(str(source), safe="/") + "?mode=ro"
    start = time.monotonic()

    def progress(status, remaining, total):
        if time.monotonic() - start > 300:
            raise TimeoutError("SQLite snapshot exceeded time limit")

    with closing(sqlite3.connect(uri, uri=True, timeout=15)) as live:
        with closing(sqlite3.connect(str(destination))) as backup:
            live.backup(backup, pages=1024, progress=progress, sleep=0.05)
            # Normalize only the destination for standalone restore portability.
            backup.execute("PRAGMA journal_mode=DELETE").fetchone()
    metadata = source.stat()
    os.chown(str(destination), metadata.st_uid, metadata.st_gid)
    os.chmod(str(destination), stat.S_IMODE(metadata.st_mode))
    validation = "ok"
    with closing(sqlite3.connect(str(destination))) as backup:
        try:
            rows = backup.execute("PRAGMA quick_check").fetchall()
            if rows != [("ok",)]:
                raise RuntimeError("SQLite snapshot integrity check failed")
        except sqlite3.OperationalError as error:
            if "collation" in str(error) or "no such function" in str(error):
                validation = "requires_application_sqlite_extensions"
            else:
                raise
    return {"source": str(source), "bytes": destination.stat().st_size,
            "snapshot": "sqlite_online_backup", "quick_check": validation}


def postgres_exports(directory):
    entries = []
    for namespace in ["endurain", "velomate", "homeassistant"]:
        pod = pod_for(namespace, "postgres")
        prefix = ["k3s", "kubectl", "exec", "-n", namespace, pod,
                  "-c", "postgres", "--"]
        if namespace == "homeassistant":
            auth = 'export PGUSER=postgres; '
        else:
            auth = 'export PGUSER="$POSTGRES_USER" PGPASSWORD="$POSTGRES_PASSWORD"; '
        query = "SELECT datname FROM pg_database WHERE NOT datistemplate ORDER BY datname"
        import shlex
        listing = command(prefix + ["sh", "-c", auth +
                          "psql -d postgres -Atc " + shlex.quote(query)])
        folder = directory / "backup-metadata" / "postgres" / namespace
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / "globals.sql").open("wb") as handle:
            command(prefix + ["sh", "-c", auth + "pg_dumpall --globals-only"],
                    output=handle)
        for name in listing.decode().splitlines():
            if not re.fullmatch(r"[a-zA-Z0-9_-]+", name):
                raise ValueError("Unexpected PostgreSQL database name")
            output = folder / (name + ".dump")
            with output.open("wb") as handle:
                command(prefix + ["sh", "-c", auth +
                                  "pg_dump --format=custom --dbname=" + shlex.quote(name)],
                        timeout=900, output=handle)
            with output.open("rb") as handle:
                if handle.read(5) != b"PGDMP":
                    raise RuntimeError("Invalid PostgreSQL export header")
            # Parse the archive using the exact version that produced it.
            with output.open("rb") as handle:
                result = subprocess.run(prefix[:3] + ["-i"] + prefix[3:] +
                                        ["pg_restore", "--file=/dev/null"],
                                        stdin=handle, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.PIPE, timeout=900)
            if result.returncode:
                raise RuntimeError("PostgreSQL archive parse verification failed")
            entries.append({"namespace": namespace, "database": name,
                            "bytes": output.stat().st_size,
                            "verification": "pg_restore_full_archive_parse",
                            "restore_test": "not_imported_into_isolated_database"})
    return entries


def redis_export(directory):
    pod = pod_for("endurain", "redis")
    destination = directory / "etc/k8sconfigs/endurain/redis/dump.rdb"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        command(["k3s", "kubectl", "exec", "-n", "endurain", pod, "-c", "redis",
                 "--", "redis-cli", "--rdb", "-"], output=handle)
    with destination.open("rb") as handle:
        if handle.read(5) != b"REDIS":
            raise RuntimeError("Invalid Redis export header")
    with destination.open("rb") as handle:
        result = subprocess.run(["k3s", "kubectl", "exec", "-i", "-n", "endurain",
                                 pod, "-c", "redis", "--", "redis-check-rdb", "/dev/stdin"],
                                stdin=handle, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=60)
    # Some versions require a seekable file; a header alone is not full validation.
    return {"bytes": destination.stat().st_size, "snapshot": "redis_replication_rdb",
            "validation": "redis_check_rdb_ok" if result.returncode == 0
            else "header_only_requires_seekable_restore_test"}


def copy_couchdb(directory):
    root = Path("/etc/k8sconfigs/couchdb/data")
    copied = 0
    # CouchDB documents online copying as supported. Copy secondary indexes first.
    files = sorted(root.rglob("*"), key=lambda p: (".shards" not in p.parts, str(p)))
    for source in files:
        if not source.is_file() or source.is_symlink():
            continue
        destination = directory / str(source).lstrip("/")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source), str(destination))
        metadata = source.stat()
        os.chown(str(destination), metadata.st_uid, metadata.st_gid)
        copied += 1
    return {"files": copied, "method": "documented_online_append_only_file_copy",
            "restore_test": "not_started_isolated_couchdb"}


def prepare(run_id, resume=False):
    os.umask(0o077)
    STAGING.mkdir(mode=0o700, parents=True, exist_ok=True)
    staging = run_dir(run_id)
    if resume:
        if staging.is_symlink() or (staging / ".owned-by-homelab-backup").read_text() != run_id:
            raise RuntimeError("Refusing to resume unowned staging")
    else:
        staging.mkdir(mode=0o700, exist_ok=False)
        (staging / ".owned-by-homelab-backup").write_text(run_id)
    payload = staging / "payload"
    payload.mkdir(mode=0o700, exist_ok=resume)
    report = {"run_id": run_id, "sqlite": [], "postgres": [],
              "excluded_media": "bulk /mnt/volume1 content outside approved book folders",
              "media_exceptions": [str(p) for p in BOOK_ROOTS],
              "limitations": ["No atomic cross-application snapshot",
                              "Foundry LevelDB and Suwayomi H2 need quiesced/native backup before upgrades",
                              "Per-run full PostgreSQL/CouchDB restore tests are separate",
                              "Bulk media disk excluded; only approved book exceptions included"]}
    report_path = staging / "report.json"
    if resume:
        report = json.loads(report_path.read_text())
        if report["run_id"] != run_id:
            raise RuntimeError("Resume manifest mismatch")
    complete = {row["source"]: row for row in report["sqlite"]}
    for source in sqlite_sources():
        destination = payload / str(source).lstrip("/")
        if str(source) in complete:
            if not destination.is_file() or destination.stat().st_size != complete[str(source)]["bytes"]:
                raise RuntimeError("Previously completed snapshot missing or changed")
            continue
        print("Snapshotting SQLite: " + str(source), file=sys.stderr, flush=True)
        report["sqlite"].append(snapshot_sqlite(source, destination))
        report_path.write_text(json.dumps(report, indent=2))
    print("Exporting PostgreSQL", file=sys.stderr, flush=True)
    report["postgres"] = postgres_exports(payload)
    report["postgres_raw_paths"] = [str(p) for root in ROOTS for p in root.rglob("PG_VERSION")
                                    if p.parent.name == "pgdata"
                                    or p.parent in PG_PATHS]
    report["postgres_raw_paths"] = [str(Path(p).parent) for p in report["postgres_raw_paths"]]
    print("Exporting Redis", file=sys.stderr, flush=True)
    report["redis"] = redis_export(payload)
    report["couchdb"] = copy_couchdb(payload)
    metadata = payload / "backup-metadata" / "host"
    metadata.mkdir(parents=True, exist_ok=resume)
    commands = {
        "packages.tsv": ["dpkg-query", "-W", "-f=${Package}\t${Version}\t${db:Status-Abbrev}\n"],
        "mounts.txt": ["findmnt", "--json"],
        "disks.json": ["lsblk", "-J", "-o", "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,UUID,MODEL"],
        "services.txt": ["systemctl", "list-unit-files", "--no-pager"],
        "k3s-unit.txt": ["systemctl", "cat", "k3s"],
        "k3s-version.txt": ["k3s", "--version"],
        "firewall-v4.txt": ["iptables-save"],
        "firewall-v6.txt": ["ip6tables-save"],
    }
    for filename, args in commands.items():
        print("Collecting host inventory: " + filename, file=sys.stderr, flush=True)
        with (metadata / filename).open("wb") as handle:
            command(args, output=handle)
    for user in ["root", "maarten"]:
        result = subprocess.run(["crontab", "-u", user, "-l"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (metadata / (user + "-crontab.txt")).write_bytes(result.stdout)
    for kind in ["nodes", "pods", "pv", "pvc", "deployments", "statefulsets", "services",
                 "ingresses", "helmreleases", "kustomizations", "secrets", "configmaps"]:
        (metadata / ("kubernetes-" + kind + ".json")).write_bytes(
            kube("get", kind, "-A", "-o", "json"))
    report["host_mcp"] = collect_mcp_recovery(payload)
    report_path.write_text(json.dumps(report, indent=2))
    (payload / "backup-metadata" / "database-report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({"run_id": run_id, "sqlite_count": len(report["sqlite"]),
                      "postgres_count": len(report["postgres"]), "redis": report["redis"],
                      "limitations": report["limitations"]}), flush=True)


def collect_mcp_recovery(payload):
    """Keep raw app command/config values solely in private encrypted recovery data."""
    processes = []
    for folder in Path("/proc").glob("[0-9]*"):
        try:
            args = [v.decode(errors="replace") for v in (folder / "cmdline").read_bytes().split(b"\0") if v]
            if not any("google-calendar-mcp" in arg for arg in args[:2]):
                continue
            environment = {}
            for entry in (folder / "environ").read_bytes().split(b"\0"):
                if b"=" not in entry:
                    continue
                key, value = entry.split(b"=", 1)
                name = key.decode(errors="replace")
                if any(word in name for word in ["GOOGLE", "OAUTH", "CALENDAR", "MCP"]) or name in {
                        "PORT", "HOST", "HTTP_PORT", "HTTP_HOST", "TRANSPORT"}:
                    environment[name] = value.decode(errors="replace")
            processes.append({"pid": folder.name, "argv": args, "environment": environment,
                              "cwd": os.readlink(str(folder / "cwd"))})
        except OSError:
            continue
    metadata = payload / "backup-metadata" / "host"
    metadata.mkdir(parents=True, exist_ok=True)
    (metadata / "google-calendar-mcp-processes.json").write_text(json.dumps(processes, indent=2))
    if MCP_CLIENT_CONFIG.is_file() and not MCP_CLIENT_CONFIG.is_symlink():
        target = payload / str(MCP_CLIENT_CONFIG).lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(MCP_CLIENT_CONFIG), str(target))
        info = MCP_CLIENT_CONFIG.stat()
        os.chown(str(target), info.st_uid, info.st_gid)
    captured = (payload / str(MCP_CLIENT_CONFIG).lstrip("/")).is_file()
    if processes and not captured:
        raise RuntimeError("Active host MCP credentials missing from recovery capture")
    return {"processes_captured": len(processes), "client_config_captured": captured}


def prepare_host_addendum(run_id):
    os.umask(0o077)
    STAGING.mkdir(mode=0o700, parents=True, exist_ok=True)
    stage = run_dir(run_id)
    if stage.exists():
        if stage.is_symlink() or (stage / ".owned-by-homelab-backup").read_text() != run_id:
            raise RuntimeError("Refusing unowned host-addendum resume")
    else:
        stage.mkdir(mode=0o700, exist_ok=False)
    (stage / ".owned-by-homelab-backup").write_text(run_id)
    payload = stage / "payload"
    payload.mkdir(mode=0o700, exist_ok=True)
    result = collect_mcp_recovery(payload)
    # Include npm launcher parents as well as the two node listener children.
    if result["processes_captured"] < 2 or not result["client_config_captured"]:
        raise RuntimeError("Expected host MCP recovery material missing")
    (stage / "report.json").write_text(json.dumps({"run_id": run_id, "sqlite": []}))
    print(json.dumps(result), flush=True)


def prepare_quiesced(run_id):
    """Capture only the four explicitly paused apps and approved book exceptions."""
    namespaces = ["foundryvtt", "foundryvtt-hans", "foundryvtt-rogier", "suwayomi"]
    sources = []
    pvs = json.loads(kube("get", "pv", "-o", "json"))["items"]
    for namespace in namespaces:
        if json.loads(kube("get", "pods", "-n", namespace, "-o", "json"))["items"]:
            raise RuntimeError("Refusing snapshot while an application pod remains")
        controllers = json.loads(kube("get", "statefulsets,deployments", "-n", namespace,
                                      "-o", "json"))["items"]
        if len(controllers) != 1 or controllers[0]["spec"].get("replicas", 1) != 0:
            raise RuntimeError("Application is not quiesced through GitOps")
        if namespace == "suwayomi":
            sources.append(Path("/etc/k8sconfigs/suwayomi"))
        else:
            matches = [p for p in pvs if p["spec"].get("claimRef", {}).get("namespace") == namespace]
            if len(matches) != 1:
                raise RuntimeError("Ambiguous Foundry persistent volume")
            path = Path(matches[0]["spec"]["local"]["path"])
            if path.parent != Path("/var/lib/rancher/k3s/storage") or path.is_symlink():
                raise RuntimeError("Unexpected Foundry storage mapping")
            sources.append(path)
    os.umask(0o077)
    STAGING.mkdir(mode=0o700, parents=True, exist_ok=True)
    stage = run_dir(run_id)
    stage.mkdir(mode=0o700, exist_ok=False)
    (stage / ".owned-by-homelab-backup").write_text(run_id)
    payload = stage / "payload"
    payload.mkdir(mode=0o700)
    report = {"run_id": run_id, "sqlite": [], "sources": [str(p) for p in sources + BOOK_ROOTS],
              "method": "GitOps replicas zero, all pods gone, copied into owned staging",
              "book_exceptions_authorized": True, "other_media_excluded": True}
    databases = sqlite_sources(BOOK_ROOTS)
    db_exclusions = set(databases) | {Path(str(p) + suffix) for p in databases
                                     for suffix in ["-wal", "-shm", "-journal"]}
    def copy_path(source, root_device):
        if source in db_exclusions or any(under(source, p) for p in REPRODUCIBLE_PATHS):
            return
        if any(part in {"container_cache", ".cache"} for part in source.parts):
            return
        metadata = source.lstat()
        if metadata.st_dev != root_device:
            raise RuntimeError("Unexpected filesystem in checkpoint source")
        destination = payload / str(source).lstrip("/")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if stat.S_ISLNK(metadata.st_mode):
            os.symlink(os.readlink(str(source)), str(destination))
            os.lchown(str(destination), metadata.st_uid, metadata.st_gid)
        elif stat.S_ISDIR(metadata.st_mode):
            destination.mkdir(exist_ok=True)
            for child in sorted(source.iterdir()):
                copy_path(child, root_device)
            shutil.copystat(str(source), str(destination))
            os.chown(str(destination), metadata.st_uid, metadata.st_gid)
        elif stat.S_ISREG(metadata.st_mode):
            shutil.copy2(str(source), str(destination))
            os.chown(str(destination), metadata.st_uid, metadata.st_gid)
        else:
            raise RuntimeError("Unexpected special file in checkpoint source")
    for source in sources + BOOK_ROOTS:
        if not source.is_dir() or source.is_symlink():
            raise RuntimeError("Checkpoint source missing or unsafe")
        copy_path(source, source.stat().st_dev)
    for source in databases:
        report["sqlite"].append(snapshot_sqlite(source, payload / str(source).lstrip("/")))
    metadata = payload / "backup-metadata"
    metadata.mkdir()
    (metadata / "quiesced-checkpoint.json").write_text(json.dumps(report, indent=2))
    (stage / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({"run_id": run_id, "staged_sources": len(report["sources"]),
                      "book_sqlite_snapshots": len(report["sqlite"])}), flush=True)


class HashReader:
    def __init__(self, handle):
        self.handle = handle
        self.hash = hashlib.sha256()

    def read(self, size=-1):
        data = self.handle.read(size)
        self.hash.update(data)
        return data


def under(path, root):
    return path == root or root in path.parents


def archive(run_id, category):
    staging = run_dir(run_id)
    if category == "legacy-plex":
        # Dedicated read-only archive of inactive legacy state; no staging needed.
        report = {"sqlite": []}
    else:
        if (staging / ".owned-by-homelab-backup").read_text() != run_id:
            raise RuntimeError("Invalid staging ownership")
        report = json.loads((staging / "report.json").read_text())
    postgres_paths = PG_PATHS + [Path(p) for p in report.get("postgres_raw_paths", [])]
    sqlite_paths = {Path(x["source"]) for x in report["sqlite"]}
    sidecars = {Path(str(p) + suffix) for p in sqlite_paths for suffix in ["-wal", "-shm", "-journal"]}
    payload = staging / "payload"
    if category == "databases":
        sources = [payload]
    elif category == "host":
        sources = [Path(p) for p in ["/etc", "/root", "/home/maarten", "/boot",
                   "/usr/local/bin", "/opt", "/srv", "/var/spool/cron",
                   "/var/lib/rancher/k3s/server", "/var/lib/rancher/k3s/agent/etc"]]
        if MCP_CLIENT_CONFIG.exists():
            sources.append(MCP_CLIENT_CONFIG)
    elif category == "applications":
        sources = ROOTS
    elif category == "book-exceptions":
        sources = BOOK_ROOTS
    elif category == "legacy-plex":
        sources = [Path("/etc/dockerconfigs/plex")]
    else:
        raise ValueError("Unknown archive category")
    entries, changed, missing, skipped = [], [], [], []

    def excluded(path):
        if category == "legacy-plex":
            return False
        if category == "databases":
            logical = Path("/" + str(path.relative_to(payload)))
            return any(under(logical, cache) for cache in REPRODUCIBLE_PATHS)
        if any(under(path, cache) for cache in REPRODUCIBLE_PATHS):
            return True
        if any(part in {"container_cache", ".cache", ".npm", ".vscode-server"} for part in path.parts):
            return True
        if path in sqlite_paths or path in sidecars:
            return True
        if any(under(path, p) for p in postgres_paths) or under(path, REDIS_PATH):
            return True
        if category == "applications" and under(path, Path("/etc/k8sconfigs/couchdb/data")):
            return True
        if category == "host":
            if any(under(path, root) for root in ROOTS):
                return True
            if under(path, Path("/var/lib/rancher/k3s/server/db")):
                return True
        return False

    def walk(source):
        if excluded(source):
            return
        try:
            before = source.lstat()
        except FileNotFoundError:
            missing.append(str(source))
            return
        if stat.S_ISDIR(before.st_mode):
            yield source
            for child in sorted(source.iterdir()):
                yield from walk(child)
        elif stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode):
            yield source
        else:
            skipped.append(str(source))

    with tarfile.open(fileobj=sys.stdout.buffer, mode="w|") as archive_file:
        for root in sources:
            if not root.exists():
                missing.append(str(root))
                continue
            root_device = root.stat().st_dev
            for source in walk(root):
                metadata = source.lstat()
                if metadata.st_dev != root_device:
                    skipped.append(str(source))
                    continue
                name = str(source.relative_to(payload)) if category == "databases" else str(source).lstrip("/")
                if name == ".":
                    continue
                info = archive_file.gettarinfo(str(source), arcname=name)
                if info.isfile():
                    with source.open("rb") as handle:
                        reader = HashReader(handle)
                        archive_file.addfile(info, reader)
                    after = source.stat()
                    if (metadata.st_size, metadata.st_mtime_ns, metadata.st_ino) != (
                            after.st_size, after.st_mtime_ns, after.st_ino):
                        changed.append(name)
                    entries.append({"path": name, "bytes": info.size,
                                    "sha256": reader.hash.hexdigest()})
                else:
                    archive_file.addfile(info)
        manifest = {"category": category, "run_id": run_id, "files": entries,
                    "changed_during_read": changed, "missing_paths": missing,
                    "special_or_cross_device_skipped": skipped,
                    "atomic_cross_application": False,
                    "notes": "Per-database consistent exports; online file capture otherwise"}
        data = json.dumps(manifest, indent=2).encode()
        info = tarfile.TarInfo("backup-metadata/" + category + "-file-manifest.json")
        info.size = len(data)
        info.mode = 0o600
        archive_file.addfile(info, io.BytesIO(data))


def cleanup(run_id):
    staging = run_dir(run_id)
    if staging.is_symlink() or (staging / ".owned-by-homelab-backup").read_text() != run_id:
        raise RuntimeError("Refusing unowned staging cleanup")
    shutil.rmtree(str(staging))
    print(json.dumps({"staging_removed": run_id}))


if __name__ == "__main__":
    try:
        if os.geteuid() != 0:
            raise RuntimeError("Root required for backup reads")
        action, run_id = sys.argv[1:3]
        if action == "prepare-host-addendum":
            prepare_host_addendum(run_id)
        elif action == "prepare-quiesced":
            prepare_quiesced(run_id)
        elif action in {"prepare", "prepare-resume"}:
            prepare(run_id, resume=action == "prepare-resume")
        elif action == "archive":
            archive(run_id, sys.argv[3])
        elif action == "cleanup":
            cleanup(run_id)
        else:
            raise ValueError("Unknown action")
    except Exception as error:
        print("Backup helper failed: " + type(error).__name__, file=sys.stderr)
        sys.exit(1)
