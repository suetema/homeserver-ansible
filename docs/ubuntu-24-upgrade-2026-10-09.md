# ryback Ubuntu 24.04 maintenance — 2026-10-09

**COMPLETE: Ubuntu 24.04.5 / 6.8.0-146-generic booted and acceptance passed.
59 pods and 43 Flux resources Ready; real Plex VAAPI decode/encode transcode and
both same-user MCP stdio checks pass. STOP after Noble; no k3s/app continuation.
Prior access-loss/stop evidence below is retained as history.**

## Authorization and boundary

Parent reviewed Jammy and the separately approved/deployed GPU fix and instructed
this sole live mutator to continue the owner's authorized sequential upgrade to
Ubuntu 24.04. Service interruptions/reboots authorized; physical recovery and
backup key available, USB on demand/not prepared, residual remote lockout accepted.
No new k3s/ingress/app/chart/image upgrades, GitOps changes/commits/pushes,
firmware/security hardening or unrelated cleanup. Stop after Noble acceptance or
a concrete blocker. Preserve dormant Docker/Compose data/configuration; Compose
v1 Python migration issue is nonblocking and not repaired incidentally.

## Starting milestone

- Read GPU fix, independent compatibility review and parent execution log.
- Live Ubuntu 22.04.5, HWE `6.8.0-138-generic`; k3s `v1.33.11+k3s1`, separate
  containerd `2.2.3-k3s1.33`, unified cgroup v2/systemd drivers, swap intentional.
- GPU fix: standalone Intel plugin v0.37.1 by immutable digest and Plex existing
  chart 1.9.0 with i915 request/limit 1. Preserve both, unchanged Plex image and
  original config PVC/UID/cloud identity. Jammy native opens + real PMS hardware
  decode/encode full-pipeline HLS probe passed in the prior unit.
- Fresh Ubuntu-only apt metadata authenticated; dpkg/apt healthy, no holds,
  **zero available Jammy updates**. External Docker/Node repos remain excluded.
  Stable `do-release-upgrade -c` offers **24.04.5 LTS**; no development flag.
- Root 627 GiB free, /boot 942 MiB free, EFI 1.1 GiB free. Media UUID genuinely
  mounted. Fresh consistent narrow checkpoint planned before package transition.

## Deliberate maintenance safeguards

- Checkpoint stopped k3s SQLite + matching token/binary/config, host boot/network/
  package state, post-GPU Flux/plugin/PVC inventory and private MCP credentials.
  Encrypt/authenticate/hash-check/SQLite restore-check on Mac. Existing broad
  application backups retained; k3s stop is not application quiescence.
- Preserve/review conffiles individually and removals explicitly; no indiscriminate
  autoremove. Retain known-working Jammy HWE and older kernel fallbacks.
- Persistent root terminal; account for Noble needrestart automatic daemon restarts.
  No restore/stopped-database copy while service can restart.
- Review actual generated GRUB kernel/initrd/root selection and SSH service/socket/
  generator/drop-ins; fresh independent SSH login before controlled reboot.
- Disable k3s boot autostart only for reboot; validate all six mounted UUIDs/RW
  before restoring enabled state/start. Reconnect deadline ten minutes; stop and
  escalate to physical fallback if missed.
- Postboot cluster/plugin/PVC/Flux/DNS/HTTPS, original-user MCP stdio smoke and
  bounded native DRM + actual PMS hardware-transcode probes. Stop owned stream.
  No claim of full Foundry gameplay or whole-machine rebuild rehearsal.

Progress is recorded here and in root-owned credential-free
`/var/backups/homelab-upgrade/status.json`, retaining earlier milestones.

## Fresh checkpoint and release transaction

- Verified run **`20261009T075949Z-b6d955cb`** on Mac:
  - `databases-host-preubuntu24.tar.zst.age`: **887,250,018 bytes**, all **553**
    regular-file hashes match; complete age authentication/zstd pass; restored
    SQLite quick_check **ok**, eight schema objects. Stopped k3s only for SQLite/
    token capture, restarted in finally. No fresh live-app copy claimed consistent.
  - `local-recovery-post-gpu.tar.zst.age`: **1,874,557 bytes**, **2,051** regular
    files verified, preserving both local checkouts/uncommitted work and post-GPU
    Flux configuration. No Flux file edited, staged, committed or pushed.
  - No changed/missing/skipped archived paths. Private MCP records, original and
    durable OAuth copies, saved account tokens, GPU deployments/node resources,
    pod/Flux/PV/PVC inventory and host configuration included.
- First preparation attempt stopped **before k3s pause** because this iptables-save
  does not accept `-w`; corrected only the new helper and captured a fresh run.
  Failed private staging retained until the verified replacement is safely usable.
- Original apt timers temporarily stopped (not disabled); protect package race.
  Root tmux `ubuntu24`, original Jammy tmux executable retained privately so the
  upgraded client cannot strand control of the persistent old server.
- Stable `do-release-upgrade -f DistUpgradeViewText`, `Prompt=lts`, tool signature
  authenticated; no `-d`, suite rewrite or blanket config/restart replacement.
- Initial proposal would replace original working Jammy 6.8.0-138 binaries with
  same-version Noble builds. **Aborted before applying packages**, added three
  temporary holds on `linux-image-6.8.0-138-generic`, `linux-modules-6.8.0-138-generic`
  and `linux-modules-extra-6.8.0-138-generic`, then recomputed official upgrade.
  This preserves the actual working Jammy fallback, not merely its version label.
- Reviewed final proposal and confirmed `y`: **670 upgrades, 277 installs,
  62 removals**, 1,419 MB download. Removals are ABI/t64/library replacements plus
  obsolete gpg-wks-server/python3-distutils/usrmerge, not Docker/Node/kernel/data
  removal. Primary maintained Noble GA kernel **6.8.0-146**; old Jammy fallback
  held. Third-party Docker/Node candidate versions are exactly installed versions.
- `/etc/systemd/networkd.conf`: inspected actual Noble diff and chose **keep
  current file (`n`)**, preserving networking policy rather than combining cleanup.
- At approximately **08:10 UTC**, new SSH connections began returning
  **Connection refused** during the package/service transition. Normal port 22
  and recovery port 1022 did not recover in the initial three-minute check.
  Continue bounded read-only reconnect observation through **08:20:59 UTC**
  (ten-minute maintenance-access deadline), no follow-on commands or reboot
  while access is unavailable. Remote status cannot be updated while SSH is lost.

## Historical blocker / recovery handoff (resolved)

- Final bounded reconnect attempt ended **2026-10-09T08:21:03Z**. Both normal
  **22** and upgrader recovery **1022** still refuse connections. TCP **6443**
  (k3s API) and **32400** (Plex) remain reachable: this is not evidence of a dead
  machine, missing storage or a successful reboot. No claim that all workloads
  or the post-Noble GPU pipeline were revalidated after this access loss.
- Last visible terminal: Noble package transaction installing dbus and related
  libraries after the reviewed networkd config keep decision. New SSH failed
  during the later OpenSSH/service transition; exact unit failure/prompt cannot
  be inspected remotely. Do not assume root cause or package completion.
- Root upgrade remains in persistent tmux **`ubuntu24`**, with preserved original
  client `/var/backups/homelab-upgrade/tmux-jammy`. No blanket dpkg reset/kill,
  forced reboot, GitOps changes or subsequent maintenance scheduled.
- Root `/var/backups/homelab-upgrade/status.json` last reports
  **`noble-release-packages`**; it cannot be updated to blocked while SSH is lost.
  This local document is the current access-loss status. Historical Jammy/GPU
  milestones, checkpoint fields and package holds remain preserved.

### Requested owner console action (parent coordinates)

At ryback's local console, log in as the existing user and try the unchanged
SSH service, without rebooting or interrupting the package transaction:

```sh
sudo systemctl start ssh.service
```

If that fails, capture/inspect the service/socket status and package terminal:

```sh
sudo systemctl status ssh.service ssh.socket --no-pager
sudo /var/backups/homelab-upgrade/tmux-jammy attach -t ubuntu24
```

Report the displayed error/configuration prompt to the parent; do not paste
credentials/raw secrets. **Do not reboot, kill apt/dpkg, remove packages or accept
all configuration replacements.** A second console can inspect SSH while the
upgrader terminal remains attached. Once fresh SSH is restored, this authorized
unit can resume prompt/SSH socket/GRUB review before any controlled reboot.

## Historical stopped handoff state (superseded below)

- Last verified boot: **Ubuntu 22.04.5 / 6.8.0-138-generic**. Noble userspace is
  being installed; **actual final OS version/current completion is unknown**.
  Intended new maintained GA kernel **6.8.0-146**, not yet boot-target validated.
- Original Jammy image/modules/extras held on their exact `~22.04.1` builds;
  older fallbacks retained. Do not clear holds before recovery/boot review.
- k3s/app/plugin upgrades were not performed. Control plane was restarted only
  after the consistent checkpoint; autostart has **not yet been disabled for
  reboot**. Needrestart may restart host services as part of the OS transaction;
  no checkpoint or application restoration is in progress during these restarts.
- Full fresh checkpoint and local post-GPU Flux archive verified before applying
  packages at `~/homelab-backups/ryback/20261009T075949Z-b6d955cb/`. Existing broad
  application checkpoints untouched. Root private snapshot/recovery staging
  retained because this unit is blocked, not yet safely completed.
- Own new files only: this document and `scripts/ubuntu24_checkpoint_remote.py`.
  No other agent's file changed; no new commit/push, data deletion, app/ingress/
  k3s/firmware/security upgrade or Compose repair.

## Resumption after approved SSH recovery

- Read `docs/ssh-recovery-execution-2026-10-09.md`. Owner could not recall console
  password; parent separately obtained approval for temporary privileged Kubernetes
  recovery. Recovery agent started only the unchanged `ssh.service`, verified fresh
  key/sudo access, removed both owned jobs/pods and made no package/reboot/password
  changes. Recovery complete by **09:08 UTC**, sole OS operator handoff restored.
- Actual original root tmux `ubuntu24` is paused at **`/etc/sudoers`**; dpkg remains
  active. **No second release upgrader or competing apt/dpkg operation started.**
  Current userspace 24.04.5, still running original 6.8.0-138 kernel.
- Inspected sudoers diff; chose **keep local (`n`)**, preserving passwordless sudo
  instead of Noble's replacement policy. Inspected `/etc/sysctl.conf` diff; chose
  **keep local (`n`)**, preserving IPv4/IPv6 forwarding. Inotify drop-in retained.
- Credential-free root phase advanced to `noble-release-resumed`, preserving
  checkpoint/GPU/SSH recovery history. SSH service active, socket inactive at
  resumption; final enablement/generator review follows package completion.

## Completed Noble transaction / preboot review

- OpenSSH config dialog: inspected actual `/tmp` replacement diff; selected
  **keep local version**, retaining existing authentication policy. `sshd -t`
  and `visudo -c` pass. New independent key-authenticated user/sudo SSH succeeds.
- Original upgrader reported **System upgrade is complete**; declined **157**
  optional obsolete removals and automatic restart. No dpkg/release process or
  package lock holder remains; unattended-upgrades PID 829 is its existing
  shutdown helper/daemon (same old start), not a competing active transaction.
  Dpkg audit empty, apt check good; simulation zero installs/removals/upgrades,
  only three deliberately held fallback packages skipped. No blanket restart:
  release logs explicitly note needrestart suspended during installation.
- Noble socket activation now effective: `ssh.socket` **enabled + active**,
  `ssh.service` **disabled + active** (socket starts it on demand), no local drops,
  installed `sshd-socket-generator`, unchanged IPv4/IPv6 port 22 listeners owned
  by systemd + sshd. Not a disabled SSH access path; independent login passes.
- Generated GRUB entry 0 verified: `/vmlinuz-6.8.0-146-generic`, matching
  `/initrd.img-6.8.0-146-generic`, root UUID `badcfde0-9b10-4f96-8684-f2baba24b223`,
  /boot UUID `00a45d23-2bd1-4021-b6d7-6351737909c3`, explicit unified cgroups.
  EFI Boot0000 shim and grub binaries present; EFI grub stub points to that real
  /boot UUID and generated config. Eight-second menu/older fallback entries remain.
  Noble i915 module matches PCI 8086:4692, r8169 installed/in initramfs, files nonempty.
- Original k3s binary, fstab and Jammy 6.8.0-138 vmlinuz byte-identical to checkpoint.
  Noble regenerated the old Jammy initramfs; preserved that regenerated file
  privately and restored **only the old fallback initrd** from the verified
  checkpoint, confirmed byte-identical. Do not claim unchanged fallback merely
  because kernel filenames match; this now preserves the tested boot pair.
- Installed: `linux-generic` / image **6.8.0-146.146**; fallback image
  **6.8.0-138.138~22.04.1**; OpenSSH **1:9.6p1-3ubuntu13.19**, systemd
  **255.4-1ubuntu8.17**. Docker **5:20.10.18~3-0~ubuntu-focal**, host containerd
  **1.6.8-1**, Node **22.22.2-1nodesource1** unchanged.
- Root 625 GiB free, /boot 1.2 GiB, EFI 1.1 GiB. Original apt timers reactivated
  enabled/active only after transaction finished. Inotify remains 1024, no failed
  units preboot. Previous boot ID `5c76611f-122b-448a-9e13-5de77168d2e4`.

## Controlled reboot and completed acceptance

- Requested reboot **2026-10-09T09:18:32.665362Z**, deadline **09:28:32Z**.
  Fresh independent key/sudo SSH reached the new boot **09:21:00.618322Z**.
  Actual OS **Ubuntu 24.04.5 LTS**, actual kernel **6.8.0-146-generic**, new boot
  ID `a4bc2e89-da1a-43a8-ad20-9fba8daac1f9`. No second recovery required.
- Temporarily disabled/stopped k3s before reboot. While inactive, all **six**
  exact fstab UUIDs genuinely mounted RW and passed temporary write/fsync/unlink:
  root, media, /boot, EFI, /root and /home. Only then restored k3s enabled/start.
  Media UUID/ownership unchanged, fstab byte-identical; no application/media/PVC
  restoration, data replacement, broad media backup or bulk deletion performed.
- Node Ready, unchanged **k3s v1.33.11+k3s1** / bundled **containerd 2.2.3-k3s1.33**.
  Unified cgroup2fs, cpuset/cpu/io/memory/pids controllers available;
  `SystemdCgroup=true`, live kubelet `cgroupDriver=systemd`, `failSwapOn=false`,
  `memorySwap={}`. Intentional **8 GiB swap**, zero usage at inspection. Retained
  inotify **1024**, IPv4/IPv6 forwarding **1**. i915/r8169 bound, microcode **0x3e**.
  Interface actually **enp1s0**, **192.168.1.110/24**, gateway **192.168.1.1**;
  hostname ryback, synchronized Europe/Brussels clock.
- All **59 active/running pods Ready**, **43 Flux resources Ready** (37 HR/6 KS).
  apps remain at approved GPU revision `402d5b676dde3d08dae82a645a3ce7f00b609d61`.
  Exact pre-Noble application image specifications unchanged; all checkpoint
  PV/PVC UIDs preserved and every live PVC Bound. API `/readyz` ok. Early startup
  readiness delays and clubnzb-proxy retry recovered naturally without edits.
- All **22 named ingress** DNS checks resolve to **192.168.1.201**, real HTTPS
  verification passes without `-k`, TLS failures or 5xx. Expected protected 401
  and login redirects accepted. Three hostless Foundry ingress/services separately
  followed to **HTTP 200 `/auth`**, not license pages. Cluster DNS resolves
  `kubernetes.default.svc.cluster.local` to **10.43.0.1** from existing HA pod.
- **90-second** final observation: zero container restart-count increases, no
  pods become unready; current boot kernel journal has zero matched AppArmor
  DENIED/OOM/I/O/ext4/GPU-hang/reset error signatures. No failed systemd units.
- Effective postboot SSH: **ssh.socket enabled/active**, **ssh.service
  disabled/active** (socket-triggered), installed Noble generator, no local unit
  drops; syntax and independent key/sudo login pass. k3s and original apt timers
  enabled/active. Docker and standalone host containerd active, unchanged versions.
  Dpkg audit empty, apt check healthy; zero pending transactions/upgrades other
  than the three deliberately held original fallback packages.

### GPU acceptance and DRM numbering

- Noble enumerated the same Intel PCI **0000:00:02.0 / 8086:4692** as **card1**
  (226:1), not Jammy's card0; **renderD128** (226:128) remains. i915 is active;
  plugin automatically allocated actual nodes with no manifest/runtime change.
  Node GPU allocatable **1**, immutable plugin digest unchanged and Ready; Plex
  request/limit remain **1**, image/digest unchanged. Same config PVC UID
  **9b023257-f570-4fd0-bbb6-b37ac6e5aa6f**, same server identity SHA-256
  **1ff7596803c972f1bf0a013523ff3c0ba332febd792a70af0a1d5095032cd4c1**.
- Existing `test_or_probe_plex_gpu.py` hardcodes card0. Ran its native probe code
  with **in-memory-only device discovery** anchored to the sole actual i915 PCI
  card and matching render device; did not edit the other agent's helper or add
  a host symlink. All **eight O_RDWR opens pass** (host root/Plex-equivalent and
  pod root/Plex, both actual nodes). Static card0 assumption is a probe follow-up,
  not a hardware-access blocker.
- Unmodified `test_or_probe_plex_gpu_transcode.py transcode` passes: existing
  “Exercise” H.264 1080p media, forced HLS 640×360; real **985,496-byte** segment,
  `transcodeHwRequested=1`, **VAAPI decode + encode**, **full pipeline=1**, about
  **15.8×**. Owned session `homelab-gpu-547a3133-444d-453a-a1bb-090a0a0c507d`
  stopped in finally. No watch-state/account/sharing/license/cloud-pref edits.

### MCP/private recovery

- `/tmp/gcp-oauth.keys.json` again absent after reboot; restored privately from
  the matching durable original-user copy, both verified UID/GID **1000:1000**,
  **0600**, bytes match preserved root recovery copy. No credentials/argv/env
  printed, new registration/browser flow, password reset or startup service.
- Both preserved Node entrypoints launched privately as original UID **1000**
  in stdio mode, read-only **initialize + tools/list pass**, version **2.6.1**,
  **13 tools each**. Both smoke processes terminated; logs remain root-only.
  Historical ports 3500/3502 are auth callbacks, not required service listeners.

### Evidence, cleanup and stop

- Root status phase **`validated-noble`**, retaining historical milestones,
  package versions/checkpoints and SSH recovery, with exact Noble versions and
  nonblocking issues. Root credential-free evidence under
  `/var/backups/homelab-upgrade/`: `noble-mount-validation.json`,
  `noble-postboot-validation.json`, `noble-gpu-opens.json`,
  `noble-gpu-transcode.json`, `noble-plex-baseline.json`,
  `noble-mcp-validation.json`, `packages-noble.txt`.
- Restricted copies of final status/evidence/inventory retained beside the verified
  Mac checkpoint **`~/homelab-backups/ryback/20261009T075949Z-b6d955cb/`**.
  After acceptance and checkpoint verification, reviewed helper owner-marker
  cleanup removed **only** this run's plaintext staging and its failed initial
  **20261009T075849Z-83819e1d** staging (no datastore had been captured there).
  Existing broad/encrypted backups and private durable MCP material untouched.
- Only own new doc/helper changed locally. Existing unrelated working-tree edits
  preserved; no commit/push, Flux edit, new recovery workload or k3s/app/ingress/
  security/firmware deployment. Release's ordinary Ubuntu package updates are
  not a separate firmware-flash operation. Minor inspection-script mistakes
  (inactive-unit exit code, guessed enp3s0/card0, missing ingress host and guessed
  Foundry port) corrected read-only; none mutated workloads or invalidated checks.
- **Stop after Noble.** Nonblocking: dormant Compose v1 Python import failure,
  excluded third-party repositories, deferred 157-package cleanup, **three temporary
  Jammy fallback holds** retained through acceptance (review removal separately,
  keep working fallback), and static GPU probe card0 assumption. Normal usage-cycle
  acceptance still belongs to owner. Full Foundry gameplay, authenticated app
  writes/downloads, USB boot or whole-machine physical rebuild remain untested.
