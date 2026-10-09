"""Authorized temporary GitOps pause/snapshot/resume, then encrypted transfer.

Only the four named Flux files are committed. Original bytes/settings are saved
before pause and restored in finally, even when reconciliation/snapshot fails.
No kubectl scale/edit/patch or application configuration writes are used.
"""

from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile

import yaml

import backup_to_mac as backup


REPO = Path.home() / "Documents/homelab-flux"
NAMES = ["foundryvtt", "foundryvtt-hans", "foundryvtt-rogier", "suwayomi"]
FILES = ["apps/prd/" + name + "-values.yaml" for name in NAMES]


def git(*args):
    return subprocess.run(["git"] + list(args), cwd=str(REPO), check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120).stdout


def expected_pause(original, name):
    result = copy.deepcopy(yaml.safe_load(original))
    if name == "suwayomi":
        result["spec"]["values"]["controllers"]["main"]["replicas"] = 0
    else:
        if "postRenderers" in result["spec"]:
            raise ValueError("Review existing Foundry post-renderers before pausing")
        result["spec"]["postRenderers"] = [{"kustomize": {"patches": [{
            "target": {"kind": "StatefulSet", "name": name},
            "patch": "- op: replace\n  path: /spec/replicas\n  value: 0\n"}]}}]
    return result


def remote_command(command, timeout=600):
    result = subprocess.run(backup.SSH + [command], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout)
    if result.returncode:
        raise RuntimeError("GitOps checkpoint remote operation failed")
    return result.stdout


def reconcile():
    remote_command("sudo -n flux --kubeconfig=/etc/rancher/k3s/k3s.yaml reconcile "
                   "kustomization apps -n flux-system --with-source --timeout=5m")
    def release(name):
        return remote_command("sudo -n flux --kubeconfig=/etc/rancher/k3s/k3s.yaml reconcile "
                              "helmrelease " + name + " -n " + name + " --timeout=5m")
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(release, NAMES))


def wait_for_apps(paused):
    code = r'''
import json,subprocess,time
names=['foundryvtt','foundryvtt-hans','foundryvtt-rogier','suwayomi']
deadline=time.monotonic()+180
while time.monotonic()<deadline:
 ok=True
 for name in names:
  j=json.loads(subprocess.run(['k3s','kubectl','get','pods','-n',name,'-o','json'],capture_output=True,text=True,check=True).stdout)
  pods=j['items']
  if PAUSED:
   ok=ok and not pods
  else:
   ok=ok and len(pods)==1 and not pods[0]['metadata'].get('deletionTimestamp') and all(c.get('ready') for c in pods[0]['status'].get('containerStatuses',[])) and bool(pods[0]['status'].get('containerStatuses'))
 if ok:break
 time.sleep(2)
else:raise RuntimeError('Application state transition timed out')
print('paused' if PAUSED else 'ready')
'''
    import shlex
    remote_command("sudo -n python3 -c " + shlex.quote("PAUSED=" + repr(paused) + "\n" + code), timeout=240)


def main():
    os.umask(0o077)
    if git("branch", "--show-current").decode().strip() != "main":
        raise RuntimeError("Checkpoint requires reviewed main branch")
    if git("diff", "--cached", "--name-only").strip():
        raise RuntimeError("Existing staged user changes; refusing mixed commit")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
    folder = backup.ROOT / run_id
    folder.mkdir(mode=0o700, parents=True)
    originals, paused_versions = {}, {}
    for name, filename in zip(NAMES, FILES):
        original = git("show", "HEAD:" + filename)
        current = (REPO / filename).read_bytes()
        if yaml.safe_load(current) != expected_pause(original, name):
            raise RuntimeError("Unexpected local edits to a target application")
        originals[filename] = original
        paused_versions[filename] = current
    saved = folder / "original-flux-files.json"
    saved.write_text(json.dumps({name: content.decode() for name, content in originals.items()}, indent=2))
    report = {"run_id": run_id, "status": "preparing", "application_names": NAMES,
              "media_exceptions": ["/mnt/volume1/books", "/mnt/volume1/k8s-books"],
              "other_apps_paused": False, "original_apps_restored": False}
    report_path = folder / "checkpoint-verification.json"
    report_path.write_text(json.dumps(report, indent=2))
    print("Quiesced checkpoint: " + str(folder), flush=True)
    committed = False
    staged = False
    snapshot_ready = False
    try:
        git("add", "--", *FILES)
        staged = True
        if set(git("diff", "--cached", "--name-only").decode().splitlines()) != set(FILES):
            raise RuntimeError("Unexpected staged paths")
        git("commit", "-m", "Temporarily quiesce Foundry and Suwayomi for recovery snapshots")
        committed = True
        report["pause_commit"] = git("rev-parse", "HEAD").decode().strip()
        report_path.write_text(json.dumps(report, indent=2))
        git("push", "origin", "main")
        print("Applying authorized replicas-only pause", flush=True)
        reconcile()
        wait_for_apps(True)
        print("All four app pods stopped; copying clean state into private server staging", flush=True)
        report["snapshot"] = backup.remote("prepare-quiesced", run_id)
        snapshot_ready = True
    finally:
        # Never overwrite unrelated/concurrent edits to these same files.
        for filename in FILES:
            if (REPO / filename).read_bytes() != paused_versions[filename]:
                raise RuntimeError("Concurrent target-file change; original settings saved for recovery")
        for filename, content in originals.items():
            (REPO / filename).write_bytes(content)
        if committed:
            git("add", "--", *FILES)
            git("commit", "-m", "Restore Foundry and Suwayomi after recovery checkpoint")
            report["resume_commit"] = git("rev-parse", "HEAD").decode().strip()
            report_path.write_text(json.dumps(report, indent=2))
            git("push", "origin", "main")
            print("Restoring original application settings through Flux", flush=True)
            reconcile()
            wait_for_apps(False)
            report["original_apps_restored"] = True
        elif staged:
            # Only our four paths had been staged, and originals are restored.
            git("add", "--", *FILES)
        report_path.write_text(json.dumps(report, indent=2))
    if not snapshot_ready:
        raise RuntimeError("No successful checkpoint capture")
    archive = folder / "databases-quiesced.tar.zst.age"
    print("Apps Ready again; transferring and verifying encrypted checkpoint", flush=True)
    backup.server_archive(archive, run_id, "databases")
    with tempfile.TemporaryDirectory(prefix="restore-check-", dir=str(folder)) as temporary:
        report["archive"] = backup.verify(archive, Path(temporary))
    if report["archive"]["online_changed_files"] or report["archive"]["missing_paths"]:
        raise RuntimeError("Checkpoint archive changed or omitted files")
    report["cleanup"] = backup.remote("cleanup", run_id)
    report["status"] = "verified_quiesced_checkpoint"
    report_path.write_text(json.dumps(report, indent=2))
    print("Quiesced checkpoint verified; all four apps restored; encrypted GiB: " +
          str(round(report["archive"]["encrypted_bytes"] / 1024**3, 2)), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Checkpoint failed: " + type(error).__name__ + "; consult restricted checkpoint report", file=sys.stderr)
        sys.exit(1)
