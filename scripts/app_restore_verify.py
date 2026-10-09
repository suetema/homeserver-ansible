"""Authenticated quiesced-checkpoint application tests without live writes."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
import tempfile

import backup_to_mac as backup
import restore_verify
import restore_verify_remote


def payload_name(name):
    if name.startswith("etc/k8sconfigs/suwayomi/"):
        return "suwayomi/" + name.removeprefix("etc/k8sconfigs/suwayomi/")
    prefix = "var/lib/rancher/k3s/storage/"
    if name.startswith(prefix):
        volume, sep, rest = name[len(prefix):].partition("/")
        for app in ["foundryvtt-hans", "foundryvtt-rogier", "foundryvtt"]:
            if sep and "_" + app + "_data-" + app + "-0" in volume:
                return app + "/" + rest
    return None


def remote(action, run_id, payload=None):
    helper = Path(__file__).with_name("restore_verify_remote.py").read_text()
    app = Path(__file__).with_name("app_restore_remote.py").read_text()
    code = "import types,sys\nm=types.ModuleType('restore_verify_remote')\n"
    code += "sys.modules[m.__name__]=m\nexec(" + repr(helper) + ",m.__dict__)\n"
    code += "exec(" + repr(app) + ")\n"
    code += {"receive": "helper.receive", "run": "run_tests", "redis": "run_redis", "h2": "run_h2",
             "world": "run_world_probe", "world-ui": "run_world_ui_probe",
             "cleanup": "helper.cleanup"}[action] + "(" + repr(run_id) + ")"
    result = subprocess.run(backup.SSH + ["sudo -n python3 -c " + shlex.quote(code)],
                            stdin=payload or subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=3600)
    if result.returncode:
        # Do not print application logs/errors; they can include credential values.
        raise RuntimeError("Isolated app check failed; private test stage retained")
    return json.loads(result.stdout)


def main():
    os.umask(0o077)
    checkpoint = sys.argv[1]
    restore_verify_remote.stage_for(checkpoint)
    folder = backup.ROOT / checkpoint
    archive = folder / "databases-quiesced.tar.zst.age"
    evidence = json.loads((folder / "checkpoint-verification.json").read_text())
    if backup.digest_file(archive) != evidence["archive"]["sha256"]:
        raise RuntimeError("Checkpoint digest mismatch")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
    report = {"run_id": run_id, "checkpoint": checkpoint, "status": "preparing"}
    path = folder / ("app-restore-" + run_id + ".json")
    path.write_text(json.dumps(report, indent=2))
    print("Isolated app restore run: " + run_id, flush=True)
    with tempfile.TemporaryDirectory(prefix="app-payload-", dir=str(folder)) as temporary:
        payload = Path(temporary) / "payload.tar"
        report["files"] = restore_verify.make_payload(archive, payload, payload_name)
        with payload.open("rb") as data:
            report["transfer"] = remote("receive", run_id, data)
        path.write_text(json.dumps(report, indent=2))
    report["results"] = remote("run", run_id)
    path.write_text(json.dumps(report, indent=2))
    if report["results"]["status"] == "world_checks_incomplete":
        report["status"] = "partial_world_checks_incomplete"
        path.write_text(json.dumps(report, indent=2))
        print("Native stores and startup checked; world launch incomplete; private diagnostics retained", flush=True)
        return
    report["cleanup"] = remote("cleanup", run_id)
    report["status"] = "checked"
    path.write_text(json.dumps(report, indent=2))
    print("Application checks complete; disposable containers and plaintext removed", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("App recovery check stopped: " + type(error).__name__, file=sys.stderr)
        sys.exit(1)
