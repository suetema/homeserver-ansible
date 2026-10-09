# Plex GPU fix and Jammy acceptance — 2026-10-09

**Outcome: approved GitOps fix deployed; native GPU opens and a real PMS
hardware decode/encode transcode pass. GPU blocker cleared on Ubuntu 22.04.5.
No Ubuntu 24.04 transition was started by this unit.**

## Authorization and deployed changes

Owner answered **“do it”** to the parent's request to commit/push narrow Flux
changes and deploy the reviewed fix. This supersedes the diagnosis document's
earlier preparation-only boundary for this specific fix. Sole live mutator;
no subagents, driver/firmware installation, kernel/runtime modifications,
privileged Plex, account/sharing/licensing changes, or OS/k3s/app upgrades.

Two narrow `homelab-flux` main commits, pushed and reconciled:

1. **`bd92dcda9b3425fc297a5708841cc2f4f66fbc5e`** — vendored standalone
   Intel GPU device plugin plus Kustomize overlay, namespace kube-system,
   node selector **ryback**; add this base to apps/prd resources. Plugin became
   Ready and advertised **`gpu.intel.com/i915: 1` before changing Plex**.
2. **`402d5b676dde3d08dae82a645a3ce7f00b609d61`** — pin the existing Plex
   chart **1.9.0** and add `values.pms.resources` GPU request/limit **1**.
   Exactly one normal StatefulSet rolling replacement; Helm revision **40**.

Before editing, local HEAD/index/remote main were verified: HEAD and remote
`af90c28494ef65a7a10eed301cd78452175121aa`, index empty, target files clean.
Only the three plugin-stage files and then Plex values were staged. All
pre-existing unrelated local edits/untracked work were preserved, including
encrypted infrastructure changes. Task brief/docs/tests were not mixed into
deployment commits. Index is empty at handoff.

## Verified image provenance and change boundary

- Official Intel **v0.37.1** release verified (published 2026-10-02).
- Vendored manifest bytes equal upstream, SHA-256
  **`4aa8a8e39f8868347c81dfaeb2254058624083f6801ab036655357d5c8205225`**.
- Plugin image verified accessible by immutable digest, Linux/amd64:
  **`intel/intel-gpu-plugin@sha256:004641b2547d58f1eadce58473fa160ad71377de1eb588cf1f82832387bf3e33`**.
  Live imageID agrees. Upstream restricted host integration retained: no
  privileged container, all capabilities dropped, read-only root filesystem,
  RuntimeDefault seccomp, no service-account token, read-only DRM/sysfs mounts.
- Plex image unchanged:
  **`index.docker.io/plexinc/pms-docker:1.43.4.10903-e5521bd8c`**;
  live immutable imageID remains
  **`docker.io/plexinc/pms-docker@sha256:e0ab27395614a8e1a4fdf84c6bc60ac664915cfdde70c52d030c7728a1c48e14`**.
- Rendered against **actual deployed Helm revision 39 values**, with credentials
  redacted in memory before local rendering. Existing chart tarball digest
  verified against its official index. Baseline StatefulSet spec equals Helm's
  stored manifest; before/after differs **only by the GPU resources block**.
  No volume/mount edit, security-context edit, or app image change.

Active PVC **`pms-config-plex-plex-media-server-0`**, UID
**`9b023257-f570-4fd0-bbb6-b37ac6e5aa6f`**, bound PV
**`pvc-9b023257-f570-4fd0-bbb6-b37ac6e5aa6f`** preserved. `/config` and every
other mount/volume and claim template match before/after. No legacy config used.
Mounted Preferences.xml's ProcessedMachineIdentifier matches local PMS identity;
before/after identity hash **`1ff7596803c972f1bf0a013523ff3c0ba332febd792a70af0a1d5095032cd4c1`**
is unchanged. Owner authentication/library reads pass. Plex remains unprivileged
with unchanged AppArmor context/preferences.

Pod UID changed from `4576284f-8c12-4e9f-8f6d-f66002874148` to
`55c477c2-37b3-40a7-8368-b717928c28f8`; new container restart count **0**.
One monitoring loop falsely reached its deadline because it compared the API's
GPU quantity string `"1"` against integer `1`; the actual rollout had already
succeeded. Read-only inspection confirmed Ready; no extra rollout was induced.

## Acceptance evidence

### Device authorization

`python3 scripts/test_or_probe_plex_gpu.py` failed before the fix and now exits
**0**: all **eight** native O_RDWR opens pass (host/pod, root/Plex-equivalent,
both card0/renderD128). Same DRM device inodes and numeric groups retained.

CRI OCI now allocates **226:0 and 226:128** with explicit **`rw` allow rules**.
Container systemd scope remains **DevicePolicy=strict**, now allowing only these
additional DRM devices. Two cgroup_device BPF filters remain attached (744/748
at inspection); no hot exception or global filtering disable was applied.
The successful opens after allocation lock down the original failure seam.

### Real PMS hardware transcode

`scripts/test_or_probe_plex_gpu_transcode.py transcode` discovers the sole ready
pod's mounted preferences, reads its token **only in memory on ryback**, and
checks ProcessedMachineIdentifier against `/identity`. Credentials are HTTP
headers, never query strings/argv/output. No cloud requests or account changes.

Selected existing short episode **“Exercise”**, ratingKey **5044**, duration
**388,864 ms**, H.264 **1920×1080**, source size **176,196,612 bytes**. Forced
PMS universal HLS transcode to 640×360/max 1000 kbps, with direct play and
direct stream disabled. No metadata edits, timeline, scrobble/watch-state
updates, downloads or media writes; only normal transient transcode output/logs.

Successful session `homelab-gpu-2313fdb1-91f8-47ea-85e9-e09ee65c9fa0`:

- Real generated HLS MPEG-TS segment read: **985,496 bytes**.
- PMS `videoDecision=transcode`, H.264 output, AAC audio transcode.
- **`transcodeHwRequested=1`**.
- **`transcodeHwDecoding=vaapi`**, title **Intel (VA API)**.
- **`transcodeHwEncoding=vaapi`**, title **Intel (VA API)**.
- **`transcodeHwFullPipeline=1`**, reported speed about **13.4×**.
- Stopped **only this owned stream** in a finally block; zero owned probe
  sessions remain afterward. No other user's stream was stopped.

Initial probe requests were rejected before creating a session because PMS
could not match the probe's custom client profile. Selecting its existing
**Chrome** client profile fixed the request; no server setting changed.
Read-only capability checks confirmed existing active subscription and default
hardware decoder/encoder preferences enabled; no Plex Pass change required.

### Final health

- **59 running pods Ready** (previous 58 + one new plugin), no restart increase
  during a further 30-second observation.
- All **43 Flux resources Ready** (37 HelmReleases, 6 Kustomizations).
- apps applied `main@sha1:402d5b676dde3d08dae82a645a3ce7f00b609d61`.
- All pre-existing application image specifications unchanged.
- Same live Plex server identity; authenticated Movies/TV Shows reads pass.
- No new kernel AppArmor DENIED, OOM or I/O/ext4 error signatures in the fix
  window. No rollback needed or applied.

## Evidence, rollback and handoff

Credential-free evidence files in this repository:
`docs/plex-gpu-fix-baseline-2026-10-09.json`,
`docs/plex-gpu-fix-after-2026-10-09.json`,
`docs/plex-gpu-fix-transcode-2026-10-09.json`,
`docs/plex-gpu-fix-health-2026-10-09.json`.
Root progress `/var/backups/homelab-upgrade/status.json` updated without losing
earlier checkpoint/version fields; phase **validated-plex-gpu-fix**.

If rollback becomes necessary, GitOps-remove only Plex's GPU request/limit
first and let its normal rollout finish, then remove only this plugin base and
resource entry; preserve the PVC/data and all unrelated work. That returns to
today's former GPU-blocked configuration, not a proven working old transcode.

**Jammy GPU acceptance is complete; parent can resume the authorized Noble
workflow after its normal checkpoint/preflight review.** This unit performed
no OS upgrade/reboot and does not establish an actual pre-upgrade working
hardware-transcode baseline. Dormant Compose-v1/Python issue remains separate.
Local evidence/docs/helpers remain uncommitted; only the narrow Flux deployments
were committed and pushed.
