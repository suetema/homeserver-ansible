# ryback Ubuntu 22.04 maintenance — 2026-10-09

**Outcome: Ubuntu 22.04.5 and maintained HWE 6.8.0-138 boot successfully. STOPPED
at Jammy acceptance because Plex's pod cannot open its GPU devices (`EPERM`),
despite healthy host GPU access. No Noble upgrade performed.** All 58 running
pods and 37 HelmReleases/6 Kustomizations are Ready; application image specifications
are unchanged. A dormant Compose v1 Python incompatibility also remains.

## Authorization and boundary

Owner explicitly authorized starting upgrades on 2026-10-09, including service
interruptions, reboots and subagent execution. This supersedes the preparation-only
authorization statements in the older runbooks for this unit. This agent is the
only ryback mutator. Stop at a verified Ubuntu 22.04 milestone or a concrete blocker;
no 24.04, k3s, ingress, application, GitOps, credential or firewall-policy upgrades.
No commits/pushes. Preserve all data and cloud registrations.

Owner has physical access and the backup key, accepts remote lockout risk, and will
prepare recovery USB if necessary; USB is not currently ready. Existing tested
encrypted baseline and clean application checkpoints remain intact. Full Foundry
gameplay and physical rebuild recovery are not claimed as tested.

## Progress

- Read update plan, recovery runbook, dated audit and backup runbook.
- Live preflight: Ubuntu 20.04.5, kernel `5.18.0-051800rc1-generic`, k3s
  `v1.33.11+k3s1`, node Ready, 37 HelmReleases and 6 Kustomizations Ready.
- Fresh apt metadata refresh completed with all six repositories authenticated,
  no signature errors. Reviewing Ubuntu-only prerequisite simulation; Docker 20
  to 28 and Node update excluded from incidental maintenance.
- Root 634 GiB free, /boot 1.3 GiB free. Root/media/boot/EFI UUIDs verified.
- Secure Boot disabled; Intel Alder Lake GPU `8086:4692` uses i915; network RTL8168
  uses r8169. Retain both custom 5.18 kernels, avoid booting installed 5.4.
- Persistent root-owned status: `/var/backups/homelab-upgrade/status.json`.

## Planned deliberate choices

- Narrow fresh encrypted checkpoint: stopped k3s SQLite snapshot with matching
  token, boot/network/package state and private MCP restart/OAuth material.
  Stopping k3s alone does not stop application containers; no claim of new
  application-consistent backups from this narrow checkpoint.
- Temporary third-party repository exclusion, preserving their files/packages.
- Persistent tmux terminal with reviewed configuration prompts; no blanket
  conffile replacement or indiscriminate kernel autoremove.
- Stable `do-release-upgrade` with `Prompt=lts`, no development-release flag.
- Jammy HWE 6.8 distribution-managed kernel selected explicitly after installation,
  with visible GRUB recovery menu and original working kernel preserved.
- Controlled reboot: 10-minute SSH reconnect deadline, stop/escalate for physical
  GRUB fallback if unavailable; no unattended follow-on upgrade.

This document is updated as actual milestones are verified.

## Fresh checkpoint and prerequisite transaction

- Fresh checkpoint `~/homelab-backups/ryback/20261009T063359Z-bb1e3ce0/`:
  `databases-host-preubuntu22.tar.zst.age`, 507,456,563 encrypted bytes;
  complete age authentication/zstd decompression and all 480 file hashes verified.
  Restored k3s SQLite quick_check passed (8 schema objects). Includes matching
  token, k3s binary/credentials/TLS, boot/EFI, network/mount/package/Flux/PV/pod
  inventory, and four private MCP process records plus transient OAuth file.
  Existing broader application backups are intentionally not repeated.
- k3s stopped only for snapshot and restarted in a finally block; node returned
  Ready. App containers kept running; API pause briefly disrupted endpoints and
  caused the CNPG controller to restart. Acceptance is rechecked before transition.
- Apt daily timers temporarily stopped (not disabled) to prevent package races.
  Original third-party repository files copied privately and renamed out of apt's
  active extensions. No Docker/Node packages removed or upgraded.
- Original 5.18 images/modules already manually installed; explicitly confirmed
  retained. No kernel autoremove performed.
- Reviewed Ubuntu-only simulation and actual transaction: 73 upgrades, 5 new,
  **zero removals**, 182 MB download/69.7 MB additional space. Includes Focal
  release upgrader, Pro client, firmware, GRUB, initramfs, DHCP, iptables and UFW
  package revisions; does not enable UFW or change SSH policy. Confirmed `y` in
  persistent root tmux session `ubuntu22`; monitoring configuration prompts.
- Kernel lifecycle reference: https://ubuntu.com/kernel/lifecycle — Jammy HWE 6.8
  standard maintenance through May 2027; install `linux-generic-hwe-22.04` after
  release upgrade. This avoids regression to GA 5.15/5.4 for Alder Lake graphics.

## Supported release upgrade (completed)

- Focal package transaction exited **0**. Ubuntu now 20.04.6; dpkg audit/apt check
  healthy, zero pending Ubuntu updates. Stable upgrader check offered **22.04.5**.
  Pro-client migration completed without a configuration prompt in this transaction.
  Multipath's transient restart warning resolved: service active, no failed
  multipath unit. Only pre-existing fwupd-refresh failure remained.
- Ran `do-release-upgrade -f DistUpgradeViewText` in persistent root tmux `ubuntu22`.
  No `-d`, suite rewriting, noninteractive frontend or blanket config policy.
- Reviewed Details before confirming: **657 upgrades, 116 installs, 5 removals**,
  772 MB. Removed old replacement libraries/tools: `fuse`, `libnfsidmap2`,
  `libsemanage1`, `libtss2-esys0`, `python3-twisted-bin`; Jammy replacements are
  installed where required. No Docker, Node or working custom kernel removal.
- libc restart question: chose **No** to automatic unreviewed service selection;
  reviewed/accepted listed `cron atd` restarts.
- `/etc/systemd/networkd.conf`: reviewed diff, kept existing file (`n`). Old
  local `[Resolve] DNS=10.0.0.1` is not modern networkd syntax; separate cleanup
  deferred rather than combining network edits with this OS transition.
- `/etc/systemd/resolved.conf`: reviewed diff, kept existing file (`n`), preserving
  DNS setting and `DNSStubListener=no`; do not reset working resolver topology.
- After short control-plane pause all active pods became Ready; representative
  Home Assistant, Vikunja and Overseerr HTTPS 200, Plex expected unauthenticated 401.
- Before reboot, temporarily disable k3s autostart (not uninstall/killall), so
  mount UUID/read-write checks occur before application resumption. Restore its
  enabled state and start only after postboot storage checks succeed.
- `/etc/sudoers`: reviewed diff, kept current file (`n`), preserving original
  passwordless sudo access rather than replacing it with Jammy defaults.
- `/etc/sysctl.conf`: reviewed diff, kept current file (`n`), preserving IPv4/IPv6
  forwarding needed by Kubernetes networking.
- Jammy's new tmux client cannot control the still-running Focal tmux server.
  Recovered its original executable from the server's `/proc/<pid>/exe` into
  root-only `/var/backups/homelab-upgrade/tmux-focal`; continued monitoring the
  same upgrade session without interrupting dpkg or restarting terminal server.
- SSH conffile: reviewed full diff, chose **keep local version**, preserving
  existing authentication policy. Fresh independent SSH/sudo session, `sshd -t`
  and `visudo -c` pass after the OpenSSH update.
- Release upgrade exited **0**, optional obsolete cleanup declined (`n`), and
  automatic reboot declined (`n`) until maintained kernel/boot review completed.
- Reviewed/installed `linux-generic-hwe-22.04`: **13 new packages, zero removals**,
  exact kernel `6.8.0-138-generic` (`6.8.0-138.138~22.04.1`); transaction exited 0.
  Acknowledged pending kernel/microcode notices; chose Cancel at needrestart's
  daemon checklist to defer all listed restarts to the imminent controlled reboot.
- Created only new `/etc/default/grub.d/90-homelab-upgrade.cfg`: default entry 0,
  visible 8-second menu, explicit `systemd.unified_cgroup_hierarchy=1`.
  `update-grub` succeeded; actual first entry inspected/asserted to reference
  `/vmlinuz-6.8.0-138-generic` and matching initrd/root UUID, with both custom 5.18
  entries retained. Initial RC choice was highest-version sorting/default 0,
  not an independently edited fixed-kernel custom script; HWE now sorts first.
- Verified HWE i915 PCI alias for `8086:4692`, r8169 module and nonempty boot files.
  k3s binary remains byte-identical to checkpoint, Node remains v22.22.2.
- Preboot: root 630 GiB free, /boot 942 MiB free, EFI 1.1 GiB free. Root/media/
  boot/EFI UUIDs genuinely mounted, original fstab unchanged. Active swap retained;
  no blind swapoff or kubelet option changes.

## Reboot and postboot evidence

- Requested controlled reboot at **2026-10-09T07:00:25Z** with a ten-minute SSH
  deadline. Reconnected to a new boot within the deadline; actual running kernel
  is `6.8.0-138-generic`, Ubuntu **22.04.5 LTS**. No physical intervention required.
- k3s autostart was disabled/stopped before reboot. Verified all **six real,
  read-write UUID mounts** (root/media/boot/EFI/home/root-home) before reenabling
  and starting k3s. Original fstab and media ownership `0:0 0755` preserved.
- `ryback`, `192.168.1.110/24`, gateway `192.168.1.1`, r8169 and SSH unchanged.
  Time synchronized, Europe/Brussels. CPU microcode advanced `0x3a -> 0x3e`.
- Intel `8086:4692` still bound to **i915**; host opens both DRM nodes successfully.
  No extra GPU flags/drivers or BIOS/Secure Boot changes.
- Unified **cgroup2fs**, controllers cpu/cpuset/memory/pids/io available.
  Containerd `SystemdCgroup=true`; live kubelet config `cgroupDriver=systemd`,
  `failSwapOn=false`, empty memorySwap config. Original 8-GiB swap retained
  (zero usage immediately postboot). k3s stays **v1.33.11+k3s1**, bundled
  containerd **2.2.3-k3s1.33**, original binary byte-identical before reboot.
- One actual startup failure: Spottarr's .NET process exhausted the host's
  **128 inotify instances per UID**. Added only
  `/etc/sysctl.d/90-homelab-upgrade-inotify.conf` with
  `fs.inotify.max_user_instances=1024` and applied that file. Kubernetes workloads
  share root UID limits; no manifests/images changed. Spottarr recovered on its
  normal retry, then all **58 running pods** became Ready. No restart increases
  during a further **90-second** observation; no OOM, I/O, ext4 or AppArmor denial
  signatures in current kernel journal.
- All **43 Flux resources Ready**, same application image specifications, no
  missing baseline PV/PVCs. Cluster DNS resolves Kubernetes service to `10.43.0.1`.
  All 22 ingress hostnames resolve to `192.168.1.201`, with no 5xx/TLS failures:
  normal app/login responses or expected protected endpoints (Plex/Sonarr/CouchDB
  401, Radarr login redirect). All three Foundry services reach **`/auth`**, not
  `/license`. Full gameplay, authenticated app writes and downloads not tested.
- No failed systemd units at final validation. SSH/k3s and original apt timers
  enabled, timesync active. Dpkg/apt healthy; **zero pending Ubuntu upgrades**.
  Third-party repositories intentionally remain excluded. Docker/containerd
  preserved at **20.10.18 / 1.6.8**, Node **22.22.2** unchanged.

### Calendar OAuth/MCP recovery finding

- The four preserved process records represent **two npm launchers plus two
  `auth` commands**, not persistent MCP HTTP servers. Replayed the Node commands
  privately as original UID 1000. Both found the saved account tokens,
  **validated authentication successfully and exited 0**; their old callback
  listeners 3500/3502 are therefore not required and were not forcibly recreated.
- As the same user, a separate temporary stdio MCP process successfully completed
  `initialize` and `tools/list`: version **2.6.1**, **13 tools**. Terminated the
  smoke process afterward. No calendar writes, registration changes, new tokens
  obtained through a browser flow, or broad boot-managed services created.
- `/tmp/gcp-oauth.keys.json` did **not** survive reboot. Restored it privately
  from the verified checkpoint, UID/GID 1000:1000, mode **0600**, for compatibility
  with original clients. Additional durable private copy:
  `/home/maarten/.config/homelab-upgrade/gcp-oauth.keys.json` (0600).
  No credential values or raw launch arguments printed.

## Stop / remaining issues for parent review

1. **Plex GPU device authorization:** both `/dev/dri/card0` and `renderD128` exist
   inside the unchanged Plex pod, but root `test -r/-w` and actual `dd count=0`
   opens fail with **Operation not permitted**. Host O_RDWR opens succeed; Plex
   user's video/render groups are present. Pod/container security contexts are
   unchanged/unprivileged. This is a container device-authorization problem,
   consistent with runtime/cgroup filtering—not a missing i915 module or simple
   group mismatch. Preupgrade real hardware-transcode/device-open baseline was
   not established, so do **not** claim that a proven working transcode regressed.
   No privileged-pod patch, device-plugin deployment, runtime override or hot BPF
   exception applied: those require separately reviewed scope. **Hardware
   transcoding is not validated; stop before Noble continuation.**
2. **Dormant Compose v1:** binary/configuration remain, but `docker-compose
   --version` exits 1 with ModuleNotFoundError after Python 3.8 -> 3.10. Docker
   engine/configuration preserved; zero running Docker workloads. Do not silently
   purge it or globally reinstall obsolete Python packages. Occasional use needs
   a separate decision/remediation.
3. Optional 105-package cleanup and obsolete-kernel removal deliberately deferred.
   Retained boot images: HWE **6.8.0-138**, Jammy GA **5.15.0-198**, original custom
   **5.18.0-051800rc1 / 5.18.0-051800**, Focal **5.4.0-216 / 5.4.0-215**. Generated
   default entry 0 selects HWE, menu eight seconds, working RC fallback available.
   There is still no tested USB/full-disk rollback; normal usage/transcode testing
   and a fresh Jammy checkpoint precede any separately authorized Noble unit.

## Evidence locations / handoff

- Root credential-free status: `/var/backups/homelab-upgrade/status.json`, phase
  **`blocked-at-jammy-acceptance`**, with exact versions and both remaining issues.
- Root credential-free validation and installed inventory:
  `/var/backups/homelab-upgrade/postboot-validation.json`, `packages-jammy.txt`.
- Mac checkpoint directory above additionally holds restricted credential-free
  `jammy-status.json`, `jammy-postboot-validation.json`, `jammy-package-inventory.txt`.
- Owned checkpoint plaintext staging was removed only after encrypted verification
  and acceptance comparison. Private root-only MCP recovery records/logs retained
  at `/var/backups/homelab-upgrade/mcp-recovery/`; durable original-user OAuth copies
  restored. Existing baseline/clean app backups untouched.
- New helpers only: `scripts/ubuntu22_checkpoint_remote.py` and
  `scripts/ubuntu22_mcp_restore_remote.py`. No existing helper overwritten, Flux
  files touched, deployment changes, commits or pushes. No 24.04/k3s/chart/image
  upgrade or data cleanup performed.
