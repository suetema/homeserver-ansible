"""Start backed-up apps only in owned copies and network-isolated containers.

Injected helper module supplies validated staging, Docker commands and cleanup.
No secrets, world contents or native logs are returned to the caller.
"""

import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import time

import restore_verify_remote as helper


FOUNDRY = "ghcr.io/felddy/foundryvtt@sha256:8ec86078b0c461644d896cbe3a9f9bcae7d1ce8dc8d91eeb0b0f1d94c91c072f"
SUWAYOMI = "ghcr.io/suwayomi/tachidesk@sha256:11cec3830b354771bd832fe1f0fb65ada30625223bc5caa0436a9425b3ca1491"
REDIS = "redis@sha256:9d317178eceac8454a2284a9e6df2466b93c745529947f0cd42a0fa9609d7005"
APPS = ["foundryvtt", "foundryvtt-hans", "foundryvtt-rogier", "suwayomi"]


def runtime_copy(stage):
    """Copy reproducible runtime through read-only pod exec, never live app data."""
    target = stage / "runtime"
    if target.exists():
        return target
    target.mkdir(mode=0o755)
    pods = json.loads(helper.checked(["k3s", "kubectl", "get", "pods", "-n", "foundryvtt", "-o", "json"]))["items"]
    ready = [p for p in pods if all(c.get("ready") for c in p["status"].get("containerStatuses", []))]
    if len(ready) != 1:
        raise RuntimeError("Foundry runtime source ambiguous")
    archive = stage / "runtime.tar"
    with archive.open("wb") as out:
        result = subprocess.run(["k3s", "kubectl", "exec", "-n", "foundryvtt",
                                 ready[0]["metadata"]["name"], "--", "tar", "-c",
                                 "-C", "/home/node/resources", "app"], stdout=out,
                                stderr=subprocess.PIPE, timeout=180)
    if result.returncode:
        raise RuntimeError("Read-only runtime copy failed")
    with tarfile.open(str(archive)) as source:
        for member in source:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or path.parts[0] != "app":
                raise ValueError("Unsafe runtime member")
            destination = target.joinpath(*path.parts)
            # Never traverse a symlink created by another archive member.
            if any(p.is_symlink() for p in destination.parents if p != target.parent):
                raise ValueError("Runtime symlink traversal")
            destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            if member.isdir():
                destination.mkdir(mode=0o755, exist_ok=True)
            elif member.isfile():
                with destination.open("xb") as out:
                    shutil.copyfileobj(source.extractfile(member), out)
                destination.chmod(member.mode & 0o777)
            elif member.issym():
                link = PurePosixPath(member.linkname)
                resolved = Path(os.path.normpath(str(destination.parent / str(link))))
                if link.is_absolute() or target not in resolved.parents:
                    raise ValueError("Runtime link escapes copy")
                destination.symlink_to(member.linkname)
            else:
                raise ValueError("Unexpected runtime member type")
    archive.unlink()
    return target


def container(name, run_id, image, folder, destination, extra=None, command=None):
    helper.checked(["docker", "pull", image], timeout=900)
    args = ["docker", "run", "-d", "--name", name, "--label", helper.LABEL + "=" + run_id,
            "--network", "none", "--restart", "no", "--cpus", "1", "--memory", "2g",
            "--pids-limit", "256", "--mount",
            "type=bind,src=" + str(folder) + ",dst=" + destination]
    args += extra or []
    args += [image] + (command or [])
    helper.checked(args)


def chown_copy(folder, uid):
    for path in [folder] + list(folder.rglob("*")):
        if path.is_symlink():
            raise ValueError("Unexpected symlink in test app copy")
        os.chown(str(path), uid, uid)


def http(name, route, port, method="GET", body=None):
    inspection = json.loads(helper.checked(["docker", "inspect", name]))[0]
    pid = inspection["State"].get("Pid")
    if not pid or not inspection["State"].get("Running"):
        raise RuntimeError("Isolated app exited")
    args = ["nsenter", "-t", str(pid), "-n", "curl", "--silent", "--show-error",
            "--max-time", "15", "--location", "--write-out", "\n%{http_code}", "-X", method]
    if body is not None:
        args += ["-H", "Content-Type: application/json", "--data-binary", body]
    args += ["http://127.0.0.1:" + str(port) + route]
    result = helper.checked(args, timeout=20)
    data, code = result.rsplit(b"\n", 1)
    return int(code), data


LEVEL_CHECK = r'''
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const {ClassicLevel}=require('/runtime/app/node_modules/classic-level');
(async()=>{
 let results=[];
 async function walk(dir){for(const e of fs.readdirSync(dir,{withFileTypes:true})){
  const p=path.join(dir,e.name);
  if(!e.isDirectory())continue;
  if(fs.existsSync(path.join(p,'CURRENT'))){
   const db=new ClassicLevel(p,{createIfMissing:false,errorIfExists:false,keyEncoding:'buffer',valueEncoding:'buffer'});
   await db.open();let count=0;const h=crypto.createHash('sha256');
   for await(const [key,value] of db.iterator()){count++;h.update(key);h.update(value);}
   await db.close();results.push({store:p.slice('/data/'.length),records:count,content_sha256:h.digest('hex')});
  }else await walk(p);
 }}
 await walk('/data/Data');console.log(JSON.stringify(results));
})().catch(()=>process.exit(1));
'''


def foundry_check(stage, run_id, app, runtime, report, world_limit=None, world_timeout=150):
    source = stage / app
    folder = stage / (app + "-working")
    shutil.copytree(str(source), str(folder))
    chown_copy(folder, 1000)
    name = "homelab-app-" + run_id.rsplit("-", 1)[1] + "-" + app
    result = {"app": app, "image": FOUNDRY, "world_count": len(list((folder / "Data/worlds").glob("*/world.json")))}
    report["apps"].append(result)
    extra = ["--user", "1000:1000", "--entrypoint", "node", "--mount",
             "type=bind,src=" + str(runtime) + ",dst=/runtime,readonly"]
    try:
        container(name, run_id, FOUNDRY, folder, "/data", extra,
                  ["-e", "setInterval(()=>{},1000)"])
        result["native_leveldb"] = json.loads(helper.checked(["docker", "exec", name, "node", "-e", LEVEL_CHECK]))
    finally:
        helper.remove_owned_container(name, run_id)
    # Change startup settings only in the disposable backup copy.
    options = folder / "Config/options.json"
    config = json.loads(options.read_text())
    config.update({"world": None, "hostname": None, "routePrefix": None,
                   "proxySSL": False, "proxyPort": None, "port": 30000,
                   "upnp": False, "telemetry": False})
    options.write_text(json.dumps(config))
    os.chown(str(options), 1000, 1000)
    try:
        container(name, run_id, FOUNDRY, folder, "/data", extra,
                  ["/runtime/app/main.mjs", "--dataPath=/data", "--port=30000"])
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            try:
                code, data = http(name, "/", 30000)
                if code == 200:
                    break
            except RuntimeError:
                pass
            time.sleep(2)
        else:
            raise RuntimeError("Foundry recovered setup did not start")
        result["http_status"] = code
        result["setup_or_license_page"] = "license" if b"license-key" in data.lower() else "setup_or_auth"
    finally:
        helper.remove_owned_container(name, run_id)
    result["world_launches"] = []
    descriptors = sorted((source / "Data/worlds").glob("*/world.json"))
    selected = descriptors if world_limit is None else descriptors[:world_limit]
    result["worlds_untested"] = len(descriptors) - len(selected)
    for index, descriptor in enumerate(selected):
        world = json.loads(descriptor.read_text())
        world_id = world["id"]
        if not __import__('re').fullmatch(r"[a-zA-Z0-9_-]+", world_id):
            raise ValueError("Unexpected world identifier")
        world_folder = stage / (app + "-world-" + str(index))
        shutil.copytree(str(source), str(world_folder))
        world_options = world_folder / "Config/options.json"
        world_options.write_text(json.dumps(config))
        chown_copy(world_folder, 1000)
        launch = {"world": world_id, "original_core_version": world.get("coreVersion"),
                  "system": world.get("system"), "join_page": False}
        result["world_launches"].append(launch)
        try:
            container(name, run_id, FOUNDRY, world_folder, "/data", extra,
                      ["/runtime/app/main.mjs", "--dataPath=/data", "--port=30000", "--world=" + world_id])
            deadline = time.monotonic() + world_timeout
            while time.monotonic() < deadline:
                try:
                    code, data = http(name, "/join", 30000)
                    if code == 200 and b"auth join flexcol" in data:
                        launch["join_page"] = True
                        break
                except RuntimeError:
                    pass
                time.sleep(2)
            if not launch["join_page"]:
                launch["status"] = "world_launch_not_verified"
                logs = subprocess.run(["docker", "logs", name], capture_output=True)
                logtext = (logs.stdout + logs.stderr).decode(errors="replace").lower()
                launch["log_categories"] = [word for word in ["license", "signature", "migration", "incompatible",
                    "compatibility", "failed", "error", "unsupported", "out of memory", "permission denied",
                    "could not", "cannot", "not installed", "world launch"] if word in logtext]
                # Keep raw logs private; only fixed categories appear in reports.
                (stage / (app + "-world-" + str(index) + ".log")).write_bytes(logs.stdout + logs.stderr)
                inspection = json.loads(helper.checked(["docker", "inspect", name]))[0]
                launch["running"] = inspection["State"]["Running"]
                if launch["running"]:
                    target = helper.checked(["nsenter", "-t", str(inspection["State"]["Pid"]), "-n",
                        "curl", "--silent", "--max-time", "10", "--location", "--output", "/dev/null",
                        "--write-out", "%{url_effective}", "http://127.0.0.1:30000/join"])
                    from urllib.parse import urlsplit
                    launch["final_route"] = urlsplit(target.decode()).path
            else:
                client = r'''
const {io}=require('/runtime/app/node_modules/socket.io-client');
const socket=io('http://127.0.0.1:30000',{reconnection:false,timeout:10000});
const timer=setTimeout(()=>process.exit(1),15000);
socket.on('connect',()=>socket.emit('getJoinData',data=>{
 if(!data.world||!Array.isArray(data.users))process.exit(1);
 console.log(JSON.stringify({world:data.world.id,user_count:data.users.length}));
 clearTimeout(timer);socket.disconnect();
}));socket.on('connect_error',()=>process.exit(1));
'''
                join = json.loads(helper.checked(["docker", "exec", name, "node", "-e", client], timeout=25))
                if join["world"] != world_id:
                    raise RuntimeError("Wrong restored world loaded")
                launch["user_count"] = join["user_count"]
                launch["status"] = "world_join_and_user_database_read"
        finally:
            helper.remove_owned_container(name, run_id)
    result["full_world_launch"] = (result["worlds_untested"] == 0 and
        all(w["join_page"] and w.get("user_count") is not None for w in result["world_launches"])) \
        if result["world_launches"] else None
    result["status"] = "worlds_verified" if result["full_world_launch"] else "setup_and_native_stores_verified"
    if result["world_launches"] and not result["full_world_launch"]:
        report["world_launches_incomplete"] = True


def suwayomi_check(stage, run_id, report):
    folder = stage / "suwayomi-working"
    shutil.copytree(str(stage / "suwayomi"), str(folder))
    chown_copy(folder, 1000)
    name = "homelab-app-" + run_id.rsplit("-", 1)[1] + "-suwayomi"
    result = {"app": "suwayomi", "image": SUWAYOMI}
    report["apps"].append(result)
    try:
        container(name, run_id, SUWAYOMI, folder, "/home/suwayomi/.local/share/Tachidesk")
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            try:
                code, data = http(name, "/", 4567)
                if code == 200:
                    break
            except RuntimeError:
                pass
            time.sleep(2)
        else:
            raise RuntimeError("Suwayomi recovered application did not start")
        result["http_status"] = code
        code, data = http(name, "/api/graphql", 4567, "POST",
                          '{"query":"{ __schema { queryType { name fields { name } } } }"}')
        schema = json.loads(data)
        if code != 200 or schema.get("errors"):
            raise RuntimeError("Restored Suwayomi GraphQL unavailable")
        result["graphql_query_fields"] = [f["name"] for f in schema["data"]["__schema"]["queryType"]["fields"]]
        query = '{ mangas(condition:{inLibrary:true}) { totalCount nodes { id inLibrary } } categories { totalCount } chapters { totalCount } }'
        code, data = http(name, "/api/graphql", 4567, "POST", json.dumps({"query": query}))
        library = json.loads(data)
        if code != 200 or library.get("errors"):
            raise RuntimeError("Restored H2 library read failed")
        result["library_mangas"] = library["data"]["mangas"]["totalCount"]
        result["categories"] = library["data"]["categories"]["totalCount"]
        result["chapters"] = library["data"]["chapters"]["totalCount"]
        result["library_ids_sha256"] = hashlib.sha256(json.dumps(
            sorted(n["id"] for n in library["data"]["mangas"]["nodes"])).encode()).hexdigest()
        result["status"] = "restored_h2_library_read_via_app"
    finally:
        helper.remove_owned_container(name, run_id)


def run_tests(run_id):
    stage = helper.verify_stage(run_id)
    report = {"run_id": run_id, "apps": [], "network": "none", "live_volumes_mounted": False}
    try:
        runtime = runtime_copy(stage)
        for app in APPS[:3]:
            print("Checking isolated " + app, file=__import__('sys').stderr, flush=True)
            foundry_check(stage, run_id, app, runtime, report)
            (stage / "app-progress.json").write_text(json.dumps(report, indent=2))
        suwayomi_check(stage, run_id, report)
        report["status"] = "world_checks_incomplete" if report.get("world_launches_incomplete") else "app_checks_finished"
        (stage / "result.json").write_text(json.dumps(report, indent=2))
    except Exception as error:
        report["status"] = "failed"
        report["error_type"] = type(error).__name__
        report["failure"] = helper.LAST_FAILURE
        (stage / "app-progress.json").write_text(json.dumps(report, indent=2))
        raise
    print(json.dumps(report))


def run_world_probe(run_id):
    stage = helper.verify_stage(run_id)
    report = {"run_id": run_id, "apps": [], "network": "none", "live_volumes_mounted": False}
    foundry_check(stage, run_id, "foundryvtt", runtime_copy(stage), report,
                  world_limit=1, world_timeout=45)
    report["status"] = "world_probe_finished"
    (stage / "result.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


def run_world_ui_probe(run_id):
    stage = helper.verify_stage(run_id)
    folder = stage / "foundryvtt-world-0"
    runtime = stage / "runtime"
    name = "homelab-app-" + run_id.rsplit("-", 1)[1] + "-ui-probe"
    extra = ["--user", "1000:1000", "--entrypoint", "node", "--mount",
             "type=bind,src=" + str(runtime) + ",dst=/runtime,readonly"]
    report = {"routes": []}
    try:
        container(name, run_id, FOUNDRY, folder, "/data", extra,
                  ["/runtime/app/main.mjs", "--dataPath=/data", "--port=30000", "--world=porvenir"])
        for _ in range(30):
            try:
                http(name, "/", 30000)
                break
            except RuntimeError:
                time.sleep(1)
        pid = json.loads(helper.checked(["docker", "inspect", name]))[0]["State"]["Pid"]
        import re
        from urllib.parse import urlsplit
        for route in ["/", "/setup", "/join", "/license"]:
            code, data = http(name, route, 30000)
            url = helper.checked(["nsenter", "-t", str(pid), "-n", "curl", "--silent",
                "--max-time", "15", "--location", "--output", "/dev/null", "--write-out",
                "%{url_effective}", "http://127.0.0.1:30000" + route])
            body = re.search(rb'<body[^>]*class=["\x27]([^"\x27]*)', data)
            report["routes"].append({"requested": route, "final": urlsplit(url.decode()).path,
                "status": code, "body_class": body.group(1).decode() if body else None})
    finally:
        helper.remove_owned_container(name, run_id)
    print(json.dumps(report))


def run_redis(run_id):
    stage = helper.verify_stage(run_id)
    folder = stage / "redis-working"
    shutil.copytree(str(stage / "redis"), str(folder))
    if not (folder / "dump.rdb").is_file():
        raise RuntimeError("Missing native RDB export")
    name = "homelab-app-" + run_id.rsplit("-", 1)[1] + "-redis"
    report = {"run_id": run_id, "image": REDIS, "network": "none", "live_volumes_mounted": False}
    try:
        # Root only inside unprivileged isolated container; no host capabilities
        # or privileged mode. Never mount any production Redis directory.
        container(name, run_id, REDIS, folder, "/data",
                  ["--user", "0:0", "--entrypoint", "redis-server"],
                  ["--dir", "/data", "--dbfilename", "dump.rdb", "--appendonly", "no", "--save", ""])
        helper.wait_for(["docker", "exec", name, "redis-cli", "ping"], seconds=30)
        info = helper.checked(["docker", "exec", name, "redis-cli", "--raw", "info", "persistence"]).decode()
        if "loading:0" not in info:
            raise RuntimeError("RDB recovery did not finish")
        report["db0_keys"] = int(helper.checked(["docker", "exec", name, "redis-cli", "dbsize"]).strip())
        report["keyspace"] = helper.checked(["docker", "exec", name, "redis-cli", "--raw", "info", "keyspace"]).decode().strip()
        report["status"] = "native_rdb_loaded_by_redis"
    finally:
        helper.remove_owned_container(name, run_id)
    (stage / "result.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


def run_h2(run_id):
    stage = helper.verify_stage(run_id)
    source = stage / "suwayomi"
    name = "homelab-app-" + run_id.rsplit("-", 1)[1] + "-h2"
    output = stage / "h2-export"
    output.mkdir(mode=0o700, exist_ok=True)
    report = {"run_id": run_id, "image": SUWAYOMI, "native_tool": "org.h2.tools.Script",
              "network": "none", "source_read_only": True}
    try:
        container(name, run_id, SUWAYOMI, output, "/export",
                  ["--user", "0:0", "--entrypoint", "java", "--mount",
                   "type=bind,src=" + str(source) + ",dst=/restore,readonly"],
                  ["-cp", "/home/suwayomi/startup/tachidesk_latest.jar", "org.h2.tools.Script",
                   "-url", "jdbc:h2:/restore/database;IFEXISTS=TRUE;ACCESS_MODE_DATA=r",
                   "-user", "", "-password", "", "-script", "/export/native.sql"])
        exit_code = helper.checked(["docker", "wait", name], timeout=120).strip()
        if exit_code != b"0":
            logs = subprocess.run(["docker", "logs", name], capture_output=True)
            text = (logs.stdout + logs.stderr).decode(errors="replace").lower()
            report["failure_categories"] = [word for word in ["wrong user name or password", "classnotfoundexception",
                "could not find or load", "permission denied", "unsupported database", "file corrupted",
                "read-only", "database not found"] if word in text]
            report["status"] = "native_check_failed"
            (stage / "h2-progress.json").write_text(json.dumps(report, indent=2))
            raise RuntimeError("Native H2 read-only export failed")
        data = (output / "native.sql").read_bytes()
        report["sql_sha256"] = hashlib.sha256(data).hexdigest()
        report["sql_bytes"] = len(data)
        report["table_definitions"] = sum(1 for line in data.splitlines()
                                           if line.startswith((b"CREATE MEMORY TABLE", b"CREATE CACHED TABLE")))
        report["status"] = "native_h2_full_read_only_export_passed"
    finally:
        helper.remove_owned_container(name, run_id)
    (stage / "result.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
