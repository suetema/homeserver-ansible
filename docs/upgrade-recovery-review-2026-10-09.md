# Ubuntu upgrade recovery/compatibility review — 2026-10-09

## Outcome and scope

**No documented blanket boot/runtime incompatibility found between Ubuntu 24.04,
Intel i5-12400/Alder Lake-S, and the existing k3s `v1.33.11+k3s1`.** Proceed to
Noble only after the executing agent validates the Jammy reboot. The important
hazards are boot selection, real storage mounts, cgroup/swap policy, SSH socket
activation and service restarts during package transactions—not a requirement to
upgrade Kubernetes or replace the Intel driver first.

Independent offline/read-only review. No SSH, host changes, package operations,
backups, test containers, deployment changes, credential decryption, agents or
Git commits/pushes performed. Only this new document was written. The separate
sole-mutator agent owns actual upgrades/reboots. This review does **not** attest
to its current progress or any post-upgrade host state.

The owner's 2026-10-09 authorization supersedes older documents' statements that
OS upgrades/reboots are unauthorized. Physical emergency access and residual
remote recovery risk are accepted; USB is planned **if needed**, not ready.
Backup key possession is confirmed. These are acknowledged limitations, not a
reason to restart the preparation process or demand deferred Foundry licensing
tests now.

## HIGH-priority handoff to the executing agent

| Hazard | Required action / stop condition |
| --- | --- |
| **Pinned/custom GRUB entry can keep booting 5.18 RC despite an OS upgrade.** The original audit records an explicit unmanaged entry, hidden menu and zero timeout. | Inspect the generated entry actually selected, kernel/initramfs and mounted `/boot`/EFI filesystems before each reboot. Merely installing `linux-generic` or setting `GRUB_DEFAULT=0` does not establish which kernel a custom first entry boots. Keep the working Jammy kernel and a usable console fallback through Noble acceptance. **Stop before reboot** if the selected entry or boot files are missing/ambiguous; stop before Noble if Jammy did not boot the intended maintained kernel. Do not remove the only known-working fallback at the upgrader's obsolete-package prompt. |
| **Missing media mount can silently redirect hostPath writes onto root.** There is no bulk-media backup. | Root UUID `badcfde0-9b10-4f96-8684-f2baba24b223`; media UUID `8bf25db0-ca04-4c96-b91e-07d3458f4021` must remain genuinely mounted at `/mnt/volume1`. Preserve UUID-based mounting and ownership, not `/dev/sda`/`sdb` identities. **Stop app resumption and further upgrades** on wrong/missing/read-only storage or filesystem errors. Do not format, repartition, scan empty library paths or initialize replacement databases to make checks pass. |
| **Noble changes OpenSSH to socket activation.** Existing connections surviving the upgrade do not prove the next connection/reboot works. | Review SSH conffile/snippet prompts, validate syntax and effective listening address/port, and inspect both `ssh.socket` and `ssh.service` plus any local drop-ins. Noble's generator reads `sshd_config`; stale socket overrides or a bind to an unavailable address can interfere. Test a **fresh independent login** before reboot. **Stop before reboot** if a fresh login fails; do not combine this with key-only SSH/firewall hardening. [1, 2] |
| **Noble `needrestart` automatically restarts affected services at the end of APT transactions, even noninteractively.** | Account for restarts of host daemons/user sessions during the maintenance state; whether k3s is selected depends on the actual processes/libraries. A stopped service is not the same as stopped containers. Maintain the executing agent's chosen quiescence/reconciliation policy and verify it after transactions. Explicitly review restart handling rather than rely on Focal/Jammy prompting behavior. **Pause if apps resume while their state is being checkpointed/restored.** No blanket permanent disabling of security restarts is recommended. [1, 3, 8] |
| **cgroup v2 plus swap changes effective resource behavior.** | Confirm unified `cgroup2fs`, available CPU/cpuset/memory/pids controllers, compatible kubelet/runtime drivers and intentional swap policy after reboot. Review any explicit v1 boot flags or custom containerd/kubelet overrides; an OS upgrade need not erase them. Keep k3s version/options fixed. **Stop progression** on startup errors, missing controllers, repeated OOM/eviction or persistent non-Ready workloads; do not use the next OS upgrade to hide a Jammy failure. [4–6] |
| **Google Calendar MCP is not a boot-managed service, and its OAuth client file is in `/tmp`.** | Ensure the verified encrypted addendum is retained before reboot; do not assume `/tmp` survives boot or listeners 3500/3502 auto-start. Recreate privately from saved launcher/environment records after confirming a compatible Node runtime, ideally with credentials in durable user configuration, mode 0600. Never print raw saved commands/environment or OAuth contents. Loss of automatic startup is recoverable, but loss of the only credential copy would be a stop. |

## Compatibility details and uncertainties

### Kernel / Intel GPU

- Jammy Server's GA kernel is **5.15**; Noble's GA kernel is **6.8**. Actual
  installed/selected GA or HWE packages must be reported by the executing agent,
  not inferred from the OS version. [1, 7]
- Upstream Linux 6.8's `i915` PCI table includes Alder Lake-S, whose device
  descriptor does not require `force_probe`. Intel's media-driver explicitly
  supports ADL-S/P/N. There is no evidence here that this i5-12400 needs a
  mainline RC, out-of-tree GPU driver, `xe` switch or BIOS flash. [9, 10]
- Intel documents ADL-S/P HuC loading from kernel 5.17, contingent on firmware.
  Therefore a move from the old 5.18 RC to Jammy GA 5.15 can change a media
  feature even if basic `/dev/dri` graphics works. This is a **validation point**,
  not proof that 5.15 cannot boot or use the GPU. If Jammy shows a reproducible
  regression, consider its maintained HWE kernel rather than blindly selecting
  the old Focal 5.4 fallback. Noble 6.8 is a reasonable supported target.
- Check `i915` binding, firmware errors, render-node existence and actual device
  permissions inside the current Plex pod. Container VAAPI/media libraries are
  supplied by its image; updating host userspace packages alone does not upgrade
  them. A Ready Plex pod or a host `vainfo` result does not prove hardware
  transcoding. Preserve UID/GID access and validate a real `(hw)` transcode;
  do not preemptively add force-probe/GuC flags or install replacement drivers.
- Exact BIOS/Secure Boot state, old i915 tweaks and post-upgrade behavior were
  not inspected live. Keep signed distro kernels available; the old unsigned
  RC is not a reliable fallback if Secure Boot is enabled later.

### k3s / containerd / cgroups / swap

- The exact official k3s release lists bundled **containerd 2.2.3-k3s1.33 and
  runc 1.4.2**. Docker's older host containerd/runc are **not** the production
  k3s runtime. No Docker upgrade/reinstallation is needed to provide the k3s
  runtime for Noble. Avoid changing runtime sockets or running an unpinned k3s
  installer during this OS transition. [5]
- Kubernetes supports cgroup v2 with kernel >=5.8, containerd >=1.4 and matched
  systemd drivers; Jammy and Noble satisfy the documented baseline. The exact
  k3s tag detects unified/v1/hybrid controllers and selects systemd for both
  its generated containerd configuration and kubelet under appropriate systemd
  conditions. **Inspect overrides/templates rather than assume automatic
  detection won.** Do not hand-edit generated `config.toml`. [4, 5]
- Important distinction: upstream kubelet's default rejects active swap, but
  **this exact k3s tag sets `FailSwapOn: false` by default**. Existing active
  8-GiB swap is not by itself proof that k3s will fail. Actual explicit overrides
  remain unknown. Kubernetes 1.33 defaults workloads to `NoSwap`; cgroup-v2
  enforcement can expose prior dependence on swapping and increase memory
  pressure. Do not blindly `swapoff` the previously used ~3.5 GiB during a
  busy upgrade, nor silently enable `LimitedSwap` as an OS-upgrade side effect.
  Review free RAM and post-start OOM/eviction behavior. [5, 6]
- Changing hierarchy/drivers with old live containers is not a hot migration.
  The attended reboot provides a clean recreation boundary. Stopping only
  `k3s.service` leaves application containers running. `k3s-killall.sh` also
  resets runtime/network state and is not a harmless read-only acceptance
  check; use only within the sole-mutator's deliberate shutdown plan. [8]
- Kubernetes 1.33's EOL is a separate lifecycle follow-up. It does not establish
  a Noble runtime incompatibility or require simultaneous Kubernetes upgrades.
  Resolve cgroup v2 before the later separately planned 1.35 step.

### Noble-specific AppArmor/network/package considerations

- Noble restricts unprivileged user namespaces. Root-run systemd k3s is not
  automatically a rootless workload, but browser sandboxes/rootless utilities
  can be affected. Diagnose actual AppArmor `DENIED` messages if Suwayomi/browser
  or other sandboxed functions regress; do not globally disable AppArmor or
  browser sandboxing as preparation. [1]
- Noble's release notes still mention the historical runc signal-denial bug.
  Its linked master bug **2065423 is Fix Released for Noble**, and the exact
  k3s containerd fork's profile template already allows signals from `runc`.
  **Not a blanket stop or justification to disable AppArmor.** Locally installed
  custom profiles may still differ; `unable to signal init: permission denied`
  or persistent terminating pods warrants diagnosis before further reboots. [11]
- Preserve current iptables alternatives, forwarding and working CNI/DNS
  behavior; do not flush rules, enable UFW, reinstall Docker or switch nft/legacy
  modes during the upgrade just because versions change. K3s documents bugs in
  iptables 1.8.0–1.8.4, not a general Noble prohibition. [12]
- Review proposed removals and third-party packages/repositories. Release
  upgrades disable external repositories; do not indiscriminately re-enable
  Focal/Jammy suites on Noble. Protect boot/network access and existing k3s
  files/options. Host Node/npm, native addons and Python/Compose scripts need
  targeted restart checks; container application dependencies generally remain
  in their unchanged images. Do not rerun the obsolete Compose playbook. [2]

## Practical Noble-stage sequence (executing agent only)

1. Finish Jammy reboot acceptance: fresh SSH, intended maintained kernel,
   correct disks, cgroup/runtime mode, node/Flux/app readiness and GPU access.
   Resolve any critical regression **on Jammy** before proceeding.
2. Take the planned fresh consistent off-host checkpoint with matching k3s
   token/config/binary and recoverable app state. Verify completion, not a
   `.partial` file. Preserve the MCP addendum. This reviewer starts no backup.
3. Finish reviewed Jammy updates/dpkg health and required reboot(s). Use the
   supported stable `do-release-upgrade` path to 24.04 in a persistent monitored
   terminal—not suite rewriting, `-d`, or simultaneous k3s/app upgrades. Review
   conffile/restart/removal decisions explicitly. [2]
4. Before Noble reboot: validate boot target/initramfs, retained fallback,
   SSH syntax/new login/socket state, mount configuration, cgroup overrides,
   swap policy and the intended service maintenance/resumption state.
5. After reconnect: verify Noble and its actual kernel, UUID mounts, unified
   controllers, unchanged k3s version/runtime, all expected workloads/PVCs and
   Flux readiness. Check DNS/representative HTTPS, key app/database reads and
   real Plex hardware transcode; recover MCP privately. Stop on disk/database
   errors, lost access or persistent runtime/app failures before cleanup.

If boot/SSH fails, stop follow-on automation and ask for physical-console
recovery using the retained kernel; prepare USB only if needed. A retained
kernel is a **boot fallback, not an Ubuntu package downgrade**. Rebuild, if
necessary, targets only the boot SSD and preserves the media UUID. There is no
SSD image or bulk-media archive; application restoration follows
`docs/recovery-runbook.md`, not a blind `/etc` or live-database overlay.

## Evidence boundaries

Reviewed the four requested runbooks/audit, maintenance-preparation report and
plaintext non-secret reports in both existing `~/homelab-backups/ryback/` runs.
The successful PostgreSQL/CouchDB report confirms six restored PG dumps with
readable tables/index checks and four readable CouchDB databases. The quiesced
checkpoint reports 4,805 verified files, no missing/changed/skipped paths; the
MCP addendum reports four captured processes, client config present, and three
hash-verified files. Application summary records 83 Foundry stores/38,711 records,
Suwayomi/H2 reads/export and Redis startup passing, **Foundry full world launch
explicitly deferred**. No archive or secret was decrypted by this reviewer.

Historical `upgrade_ready: false` records are not newly failed tests and do not
override the owner's subsequent authorization. They accurately preserve the
unrehearsed whole-host/CNPG/GPU/MCP recovery limits. Current Jammy acceptance,
fresh checkpoint, kernel selection, custom runtime profiles and exact workload
behavior require the executing agent's evidence; none is assumed here.

## Official sources checked on 2026-10-09

1. [Canonical Ubuntu 24.04 release notes](https://documentation.ubuntu.com/release-notes/24.04/) — kernel, SSH generator, AppArmor and needrestart changes.
2. [Canonical Ubuntu Server release-upgrade procedure](https://documentation.ubuntu.com/server/how-to/software/upgrade-your-release/) and [Canonical SSH socket-activation announcement](https://discourse.ubuntu.com/t/sshd-now-uses-socket-based-activation-ubuntu-22-10-and-later/30189) — sequencing, repositories, configuration and listening behavior.
3. [Canonical needrestart behavior explanation](https://discourse.ubuntu.com/t/needrestart-changes-in-ubuntu-24-04-service-restarts/44671) — APT-triggered automatic restarts.
4. [Kubernetes cgroup v2 requirements](https://kubernetes.io/docs/concepts/architecture/cgroups/) — supported kernel/runtime/driver baseline.
5. [Exact k3s release](https://github.com/k3s-io/k3s/releases/tag/v1.33.11%2Bk3s1); exact-tag source: [kubelet defaults](https://github.com/k3s-io/k3s/blob/v1.33.11%2Bk3s1/pkg/daemons/agent/agent.go), [Linux kubelet driver](https://github.com/k3s-io/k3s/blob/v1.33.11%2Bk3s1/pkg/daemons/agent/agent_linux.go), [containerd driver detection](https://github.com/k3s-io/k3s/blob/v1.33.11%2Bk3s1/pkg/agent/containerd/config_linux.go), [templates](https://github.com/k3s-io/k3s/blob/v1.33.11%2Bk3s1/pkg/agent/templates/templates.go).
6. [Version-1.33 Kubernetes swap documentation](https://github.com/kubernetes/website/blob/release-1.33/content/en/docs/concepts/cluster-administration/swap-memory-management.md) — NoSwap versus LimitedSwap and cgroup v2.
7. [Canonical Ubuntu 22.04 release notes](https://documentation.ubuntu.com/release-notes/22.04/) — Server GA 5.15 and HWE distinction.
8. [K3s stopping behavior](https://docs.k3s.io/upgrades/killall) — service stop versus killall/runtime/network cleanup.
9. [Upstream Linux 6.8 i915 PCI source](https://github.com/torvalds/linux/blob/v6.8/drivers/gpu/drm/i915/i915_pci.c) — Alder Lake-S device support.
10. [Intel media-driver documentation](https://github.com/intel/media-driver/blob/master/README.md) — supported platforms, iHD and HuC requirements; not proof of the current Plex image's exact build.
11. [Canonical master AppArmor signal bug 2065423](https://bugs.launchpad.net/ubuntu/+source/containerd/+bug/2065423), linked from [2063099](https://bugs.launchpad.net/ubuntu/+source/docker.io/+bug/2063099); [exact bundled containerd AppArmor template](https://github.com/k3s-io/containerd/blob/v2.2.3-k3s1.33/contrib/apparmor/template.go) — released fix and signal allowance.
12. [K3s known issues](https://docs.k3s.io/known-issues) and [requirements](https://docs.k3s.io/installation/requirements) — iptables version caveats and modern Linux baseline; not a certification of this individual upgraded host.
