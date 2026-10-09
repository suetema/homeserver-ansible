"""Isolated Docker restore tests; no live application volume is ever mounted."""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import time


BASE = Path("/var/backups/homelab-restore-tests")
LABEL = "io.homelab.restore-test"
POSTGRES18 = "postgres@sha256:4aabea78cf39b90e834caf3af7d602a18565f6fe2508705c8d01aa63245c2e20"
POSTGRES15 = "postgres@sha256:3b0d656f5fff31c7d8a64f500a703dcf3f35e98ce78f602831a73059a5e6a012"
COUCHDB = "couchdb@sha256:0ff2633acd380777f2c65af22eabb1d961569e05e25b12c5239b00a7f8b56d54"
LAST_FAILURE = None


def stage_for(run_id):
    if not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}", run_id):
        raise ValueError("Invalid restore-test ID")
    return BASE / run_id


def checked(args, timeout=300, stdin=None):
    global LAST_FAILURE
    result = subprocess.run(args, input=stdin, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout)
    if result.returncode:
        # Native dumps/globals/errors may contain sensitive data. Never echo them.
        text = result.stderr.decode(errors="replace").lower()
        markers = [marker for marker in ["already exists", "does not exist", "permission denied",
                   "no space left", "could not extend", "out of memory", "killed", "collation",
                   "extension", "connection", "role", "not found", "syntax error"] if marker in text]
        LAST_FAILURE = {"program": args[0], "exit": result.returncode, "error_categories": markers,
                        "utility": args[3] if args[:2] == ["docker", "exec"] else args[1]}
        if args[:2] == ["docker", "exec"] and args[3] == "psql":
            LAST_FAILURE["redacted_diagnostics"] = [
                re.sub(r'''["'][^"'\n]*["']''', "<redacted>", line)
                for line in result.stderr.decode(errors="replace").splitlines()
                if "ERROR:" in line or "DETAIL:" in line][:3]
        raise RuntimeError("Isolated test command failed: " + args[0])
    return result.stdout


def receive(run_id):
    os.umask(0o077)
    stage = stage_for(run_id)
    BASE.mkdir(mode=0o700, parents=True, exist_ok=True)
    stage.mkdir(mode=0o700, exist_ok=False)
    (stage / ".owned-restore-test").write_text(run_id)
    entries = []
    with tarfile.open(fileobj=sys.stdin.buffer, mode="r|") as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise ValueError("Unsafe test payload path")
            if path.parts[0] not in {"postgres", "couchdb", "redis", "foundryvtt",
                                     "foundryvtt-hans", "foundryvtt-rogier", "suwayomi"} or not member.isfile():
                raise ValueError("Unexpected test payload member")
            target = stage.joinpath(*path.parts)
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            digest = hashlib.sha256()
            with target.open("xb") as out:
                source = archive.extractfile(member)
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(block)
                    out.write(block)
            entries.append({"path": str(path), "sha256": digest.hexdigest()})
    (stage / "received.json").write_text(json.dumps(entries))
    print(json.dumps({"received_files": len(entries), "stage": str(stage)}))


def verify_stage(run_id):
    stage = stage_for(run_id)
    if stage.is_symlink() or (stage / ".owned-restore-test").read_text() != run_id:
        raise RuntimeError("Refusing unowned test stage")
    return stage


def wait_for(args, seconds=90):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        if result.returncode == 0:
            return result.stdout
        time.sleep(1)
    raise TimeoutError("Isolated restore-test service did not become ready")


def remove_owned_container(name, run_id):
    result = subprocess.run(["docker", "inspect", name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        return
    container = json.loads(result.stdout)[0]
    if container["Config"].get("Labels", {}).get(LABEL) != run_id:
        raise RuntimeError("Refusing to remove unowned test container")
    checked(["docker", "rm", "-f", "-v", name])


def run_tests(run_id):
    stage = verify_stage(run_id)
    token = run_id.rsplit("-", 1)[1]
    containers = []
    report = {"run_id": run_id, "postgres": [], "couchdb": {},
              "network": "none", "live_volumes_mounted": False,
              "application_functional_test": False}
    try:
        for namespace, image in [("endurain", POSTGRES18), ("velomate", POSTGRES15),
                                 ("homeassistant", POSTGRES18)]:
            print("Restore-testing PostgreSQL: " + namespace, file=sys.stderr, flush=True)
            folder = stage / "postgres" / namespace
            dumps = sorted(folder.glob("*.dump"))
            if not dumps or not (folder / "globals.sql").is_file():
                raise RuntimeError("Missing PostgreSQL export payload")
            checked(["docker", "pull", image], timeout=900)
            name = "homelab-restore-" + token + "-" + namespace
            # Keep PostgreSQL's original bootstrap role identity. Predefined-role
            # grants in CNPG globals carry GRANTED BY postgres and cannot be
            # replayed faithfully under a differently named initdb superuser.
            bootstrap = "postgres"
            globals_sql = (folder / "globals.sql").read_text()
            globals_replay, skipped = re.subn(r"^CREATE ROLE postgres;\s*$", "", globals_sql,
                                             flags=re.MULTILINE)
            if skipped > 1:
                raise RuntimeError("Unexpected duplicate bootstrap-role statements")
            (folder / "globals-replay.sql").write_text(globals_replay)
            # Large restored tables/indexes must not consume the container's RAM
            # budget as tmpfs pages. This is a fresh, disposable disk-backed copy.
            data = stage / "postgres-data" / (namespace + "-" + secrets.token_hex(4))
            data.mkdir(mode=0o755, parents=True)
            # The parent stage remains root-only on the host; within the bind
            # mount PostgreSQL's unprivileged user must traverse this root.
            data.chmod(0o755)
            containers.append(name)
            checked(["docker", "run", "-d", "--name", name, "--label", LABEL + "=" + run_id,
                     "--network", "none", "--restart", "no", "--cpus", "1", "--memory", "2g",
                     "--pids-limit", "256", "--shm-size", "256m",
                     "--mount", "type=bind,src=" + str(data) + ",dst=/var/lib/postgresql",
                     "--tmpfs", "/var/run/postgresql:rw,nosuid,size=16m",
                     "--mount", "type=bind,src=" + str(folder) + ",dst=/restore,readonly",
                     "-e", "POSTGRES_USER=" + bootstrap, "-e", "POSTGRES_DB=restore_bootstrap",
                     "-e", "POSTGRES_HOST_AUTH_METHOD=trust", image])
            prefix = ["docker", "exec", name]
            wait_for(prefix + ["sh", "-c", '[ "$(cat /proc/1/comm)" = postgres ] && '
                              "pg_isready -U " + bootstrap + " -d restore_bootstrap"])
            checked(prefix + ["psql", "-U", bootstrap, "-d", "restore_bootstrap",
                              "-v", "ON_ERROR_STOP=1", "-f", "/restore/globals-replay.sql"])
            for dump in dumps:
                database = dump.stem
                if not re.fullmatch(r"[a-zA-Z0-9_-]+", database):
                    raise ValueError("Unexpected database name")
                target = "verified_postgres" if database == "postgres" else database
                checked(prefix + ["createdb", "-U", bootstrap, "--template=template0", target])
                checked(prefix + ["pg_restore", "-U", bootstrap, "--exit-on-error",
                                  "--single-transaction", "--dbname=" + target,
                                  "/restore/" + dump.name], timeout=900)
                query = "SELECT count(*) FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema')"
                tables = int(checked(prefix + ["psql", "-U", bootstrap, "-d", target,
                                              "-Atc", query]).strip())
                # Count every ordinary restored user table; do not expose table names/data.
                count_sql = """DO $$ DECLARE t record; n bigint; BEGIN
                  FOR t IN SELECT schemaname, tablename FROM pg_tables
                    WHERE schemaname NOT IN ('pg_catalog','information_schema') LOOP
                    EXECUTE format('SELECT count(*) FROM %I.%I', t.schemaname, t.tablename) INTO n;
                  END LOOP; END $$;"""
                checked(prefix + ["psql", "-U", bootstrap, "-d", target, "-v", "ON_ERROR_STOP=1",
                                  "-c", count_sql], timeout=300)
                checked(prefix + ["pg_amcheck", "-U", bootstrap, "--install-missing", target], timeout=300)
                report["postgres"].append({"namespace": namespace, "database": database,
                                           "user_tables": tables, "roles_restored": True,
                                           "bootstrap_create_skipped": skipped,
                                           "full_import": True, "all_user_tables_readable": True,
                                           "pg_amcheck": "ok", "image": image})
                (stage / "progress.json").write_text(json.dumps(report, indent=2))
            remove_owned_container(name, run_id)
        print("Restore-testing CouchDB file snapshots", file=sys.stderr, flush=True)
        checked(["docker", "pull", COUCHDB], timeout=900)
        name = "homelab-restore-" + token + "-couchdb"
        password = secrets.token_urlsafe(24)  # Test-only credential; never a live token.
        original_data = stage / "couchdb"
        if not original_data.is_dir():
            raise RuntimeError("Missing CouchDB snapshot payload")
        data = stage / ("couchdb-test-" + secrets.token_hex(4))
        shutil.copytree(str(original_data), str(data))
        # Modify ownership only on this isolated copy, never on live app state.
        for path in [data] + list(data.rglob("*")):
            os.chown(str(path), 5984, 5984)
        containers.append(name)
        checked(["docker", "run", "-d", "--name", name, "--label", LABEL + "=" + run_id,
                 "--network", "none", "--restart", "no", "--cpus", "1", "--memory", "512m",
                 "--pids-limit", "256", "--mount", "type=bind,src=" + str(data) + ",dst=/opt/couchdb/data",
                 "-e", "COUCHDB_USER=restoreverify", "-e", "COUCHDB_PASSWORD=" + password, COUCHDB])
        # Curl executes INSIDE the isolated container, with no host port published.
        curl = ["docker", "exec", name, "curl", "--silent", "--show-error", "--fail-with-body",
                "--user", "restoreverify:" + password]
        wait_for(curl + ["http://127.0.0.1:5984/_up"])
        databases = json.loads(checked(curl + ["http://127.0.0.1:5984/_all_dbs"]))
        counts = []
        from urllib.parse import quote
        for database in databases:
            path = "http://127.0.0.1:5984/" + quote(database, safe="")
            info = json.loads(checked(curl + [path]))
            docs = json.loads(checked(curl + [path + "/_all_docs?include_docs=true"]))
            if any("error" in row for row in docs.get("rows", [])):
                raise RuntimeError("Restored CouchDB document unreadable")
            counts.append({"database": database, "doc_count": info.get("doc_count"),
                           "documents_read": len(docs.get("rows", []))})
        report["couchdb"] = {"image": COUCHDB, "databases": counts,
                             "physical_restore_started": True, "all_current_docs_readable": True}
        report["status"] = "isolated_database_restore_verified"
    except Exception:
        report["status"] = "failed"
        report["failure"] = LAST_FAILURE
        report["container_states"] = []
        for name in containers:
            inspection = subprocess.run(["docker", "inspect", name], stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
            if inspection.returncode == 0:
                state = json.loads(inspection.stdout)[0]["State"]
                logs = subprocess.run(["docker", "logs", name], stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
                logtext = (logs.stdout + logs.stderr).decode(errors="replace").lower()
                report["container_states"].append({"name": name,
                                                   "oom_killed": state.get("OOMKilled"),
                                                   "exit_code": state.get("ExitCode"),
                                                   "log_error_categories": [m for m in [
                                                       "permission denied", "no space left",
                                                       "signal 9", "bus error", "out of memory",
                                                       "fatal", "panic"] if m in logtext]})
        (stage / "progress.json").write_text(json.dumps(report, indent=2))
        raise
    finally:
        for name in containers:
            remove_owned_container(name, run_id)
    (stage / "result.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


def cleanup(run_id):
    stage = verify_stage(run_id)
    if not (stage / "result.json").is_file():
        raise RuntimeError("Retaining failed restore-test stage")
    shutil.rmtree(str(stage))
    print(json.dumps({"stage_removed": run_id}))


if __name__ == "__main__":
    try:
        if os.geteuid() != 0:
            raise RuntimeError("Root needed for isolated test staging")
        action, run_id = sys.argv[1:3]
        if action == "receive":
            receive(run_id)
        elif action == "run":
            run_tests(run_id)
        elif action == "cleanup":
            cleanup(run_id)
        else:
            raise ValueError("Unknown action")
    except Exception as error:
        print("Restore test failed: " + type(error).__name__ + "; native errors withheld", file=sys.stderr)
        sys.exit(1)
