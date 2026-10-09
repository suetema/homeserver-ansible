# Homelab modernization plan

- **Prepared:** 2026-10-08.
- **Status (2026-10-09):** Authorized sequential Ubuntu upgrades complete:
  **24.04.5 LTS / maintained 6.8.0-146-generic**, validated after reboot. Storage,
  SSH, 59 pods, 43 Flux resources, ingress, MCP and real Plex hardware transcode
  pass. k3s was then upgraded through Ansible **v1.33.11 → v1.34.12 → v1.35.9+k3s1**.
  See [OS execution record](upgrade-execution-2026-10-09.md) and
  [k3s execution record](k3s-upgrade-execution-2026-10-09.md). Later ingress (1.36),
  app/security upgrades and owner normal-usage acceptance remain separate.
- **Access decision:** User has physical access for emergency recovery but wants
  the agent to perform all planned work remotely. No physical intervention is
  planned; it remains a contingency if the server loses boot/network access.
- **Backup decision:** Use this Mac for configuration/application-state recovery
  backups. Do not back up the entire attached media disk. Any valuable exceptions
  on that disk must be identified and agreed separately.
- **Baseline:** [Live audit](update-audit-2026-10-08.md).
- **Goal:** A supported, recoverable host with controlled updates, without losing
  application state or redeploying the obsolete Compose stack.
- **Owner decisions (2026-10-08):** Sequential in-place `20.04 -> 22.04 -> 24.04`
  accepted. Owner confirms possession of the backup key; a separate off-Mac copy
  was not explicitly confirmed. Owner plans to create recovery USB if needed;
  bootable media has not been prepared/verified. These do not authorize an OS
  upgrade or reboot in the application-recovery test batch.
- **Application-check outcome:** Native Foundry database reads, restored
  Suwayomi/H2 library/native export and Redis restart pass. Full Foundry world
  launch remains unverified because the isolated clone requires license
  validation; owner chose to keep the test offline. Live licenses unchanged.
- **Additional approvals (2026-10-09):** Host upgrades, interruptions and reboots
  authorized; owner requested subagents. Minimal Intel GPU allocation/Plex Flux
  commits and one rollout separately approved and validated. Temporary privileged
  Kubernetes SSH recovery separately approved, completed and jobs removed; no
  password reset, USB use or physical intervention was needed.

## Recommended approach

Keep Ansible responsible for the host and Flux responsible for Kubernetes apps.
Use Ubuntu 24.04 LTS as the conservative OS target, a distribution-managed
kernel, unified cgroup v2 and a supported k3s release. Recheck lifecycle and
compatibility information when selecting exact versions; do not use unpinned
`latest` installers for maintenance.

Prefer an in-place `20.04 -> 22.04 -> 24.04` upgrade **only after** verified
backups and a bootable recovery route exist. If a spare SSD is available, evaluate
a clean installation with the original SSD preserved as an alternative. Neither
route permits formatting or changing the media disk. A spare boot disk alone is
not a complete rollback if applications have since changed databases elsewhere.

### Backup scope agreed so far

The Mac has approximately **144 GiB available**, checked on 2026-10-08. The audit
measured about **31 GiB** across application config and Kubernetes local storage;
allow additional space for database exports, host recovery files, staging and
retention. Recheck space and measured backup size before transfers. This estimate
does not promise unlimited historical backups or space for a full disk image.

Implemented destination: `~/homelab-backups/ryback/`, outside either Git checkout,
with restricted permissions and encrypted backup contents. Pull data through the
existing SSH connection; no new inbound SSH service on the Mac is required.
Keep encryption recovery material separately and verify that it can decrypt the
backup before deleting any staging data. Neither plaintext secrets nor backup
archives belong in Git.

Include:

- `/etc/k8sconfigs`, active configurations under `/etc/dockerconfigs`, and
  `/var/lib/rancher/k3s/storage`, with database-consistent backup methods.
- The consistent k3s SQLite datastore, matching server token, deployment options,
  and Flux/SOPS recovery material.
- Host configuration, boot/network/mount details, installed-package inventory,
  user scripts, cron jobs and required files outside the standard app paths.

Exclude by default:

- Bulk media/download contents and a full copy of `/mnt/volume1`.
- Container image caches, old build artifacts and a full boot-disk image.

User approved `/mnt/volume1/books` and `/mnt/volume1/k8s-books` as small exceptions
on 2026-10-08 (approximately 20 MiB total when measured). They and consistent
Calibre SQLite metadata snapshots are now included. The rest of the media disk
remains excluded; do not silently broaden this scope.

The attached disk remains mounted/preserved in place, identified by UUID, with
no formatting, partition changes or content cleanup. Excluding it from backups
means its hardware failure or accidental content loss cannot be recovered from
this config backup. The resulting OS fallback is a documented rebuild and app
restore, not an instant full-system image rollback. The Mac is a separate-device
backup, but not an off-site copy if it stays in the same location.

Do not combine OS, k3s, ingress, firewall and application upgrades into one event.
This is a single-node cluster: an OS reboot interrupts all hosted applications.

### Remote-first execution policy

Perform planned maintenance through SSH with agent-monitored reconnect and
acceptance checks. Before disruptive work, confirm off-host backups, recovery
instructions and the ability to intervene physically if remote access is lost.
An existing out-of-band console would improve recovery but is not mandatory if
the owner accepts that physical recovery may become necessary.

Use persistent remote terminal sessions for release upgrades, preserve a second
SSH connection for access-policy changes, and use tested timed rollback for
network/firewall changes where practical. Explicitly review configuration prompts;
do not substitute blanket noninteractive acceptance for that review. Set a
reconnection deadline and stop/escalate if it is missed. Bootloader fallbacks and
rollback timers do not guarantee recovery from a failed boot.

Do not schedule unattended follow-on steps while the host is rebooting. Verify
one reboot/upgrade fully before proceeding. Firmware flashing stays deferred
unless separately justified and authorized with an appropriate recovery method.

## Phase 0 — Agree on recovery and downtime

**No service changes.**

- [x] Select this Mac as the separate-device config/application-state backup
      destination; exclude a full copy of the attached media disk.
- [x] Verify the encrypted backup location, available space and any small
      irreplaceable exceptions on the excluded disk.
- [x] Physical access is available for emergency recovery; remote-first work is
      preferred and physical intervention should not be part of the normal plan.
- [ ] Confirm usable recovery equipment/media, an escalation procedure and a
      maintenance window; accept the residual lockout risk before OS/boot changes.
- [x] Choose sequential in-place upgrade versus spare-SSD rebuild. No full
      boot-disk image is currently planned; document the rebuild/restore fallback.
- [ ] Identify must-not-lose state: Foundry worlds, Obsidian/CouchDB, Home Assistant,
      Vikunja, fitness/workout data, books and application configurations.
- [ ] Establish a baseline checklist: expected hostname/IP, disk UUIDs/mounts,
      GPU device, k3s options, Ready workloads, important URLs and app checks.
- [ ] Finalize restart requirements for host Node apps and occasional Docker use.
      Ports 3500/3502 are Google Calendar MCP processes launched in user login
      sessions, not identified system services; automatic reboot recovery remains
      unproven. Raw launcher commands/selected environment and their `/tmp` OAuth
      client file are now in a verified encrypted host addendum. Cron/systemd
      inventories are encrypted in the baseline backup.

**Exit gate:** Backup location, recovery route, residual remote lockout risk and
acceptable downtime agreed.

## Phase 1 — Make this repository safe and testable

**Host-only default is read-only.** Local validation and check/normal preflight
runs against ryback passed with 15 tasks, zero changes and zero failures. No
package, service, deployment, network or boot change is included in that playbook.

- [x] Create a named inventory for ryback with explicit SSH user and current IP.
- [x] Separate host configuration from the obsolete Docker/Compose deployment.
      Default entry point must not start old applications or remove their data.
- [x] Retain historical deployment files intentionally; do not delete unfamiliar
      files or rewrite Git history as cleanup.
- [x] Add an isolated, pinned Ansible environment compatible with the current
      host's Python and the intended target OS; pin collection requirements.
- [x] Add syntax/lint checks and document supported OS versions.
- [ ] Design host roles for packages, working time synchronization, storage
      assertions, backups/monitoring and explicit update/reboot policy.
- [ ] Replace legacy key management/global pip patterns where still needed;
      make Docker optional rather than a required Kubernetes dependency.
- [ ] Expand preflight beyond validated exact disk UUID/mount checks to include
      explicit ownership expectations before any mutating host roles.
      No partitioning, formatting, recursive cleanup or automatic reboots.
- [ ] Prepare secret handling and a rotation checklist without printing values.

**Exit gate:** Reviewed changes pass local validation; host-only scope is clear.
Check mode is an additional review aid, not a guarantee of safe execution.

## Phase 2 — Implement and prove recovery

**Backup creation authorized on 2026-10-08.** Initial online baseline completed
and verified; see [backup runbook](backup-runbook.md). All six PostgreSQL exports
were fully restored/read/index-checked, all four CouchDB databases started/read
in isolation, and clean Foundry/Suwayomi plus book snapshots verified. The user
approved the narrow temporary pause/resume commits; all four apps are Ready again.
Suwayomi application/H2 and Redis restart checks now pass. Full Foundry gameplay
is deliberately deferred under the owner's offline-only decision; native stores
pass but the clone reaches a license screen. Rebuild validation and bootable
equipment confirmation remain. Owner confirms key possession. Broader software
upgrades and live restoration are not authorized.

- [x] Configure encrypted off-host backups using pinned age/zstd, separate UTC
      archives and private keys outside Git. Scheduling, alerts and retention
      remain separate work; restic is not required for this manual first baseline.
- [x] Back up host/network/mount/boot configuration, k3s configuration and token,
      Flux/SOPS recovery material and host scripts/cron jobs.
- [x] Cover `/etc/k8sconfigs`, the still-used `/etc/dockerconfigs`, and
      `/var/lib/rancher/k3s/storage`. The audit measured roughly 31 GiB across
      those locations before retention, deduplication and other content.
- [x] Exclude bulk `/mnt/volume1` content. Inventory small irreplaceable exceptions
      such as books and their metadata, and obtain a decision before including or
      excluding them. Leave existing retained media rollback backups untouched.
- [x] Create application-consistent database backups: native PostgreSQL exports,
      appropriate CouchDB backups, SQLite backup operations or stopped-app
      copies with WAL handling. Never rely on a live recursive database copy.
- [x] Create a consistent k3s SQLite recovery backup and retain the matching
      server token securely. `etcd-snapshot` is not the right mechanism here.
- [x] For any necessary application quiescing, prepare an explicit maintenance
      procedure consistent with Flux ownership; record original settings and
      restoration steps. Stopping k3s does not stop its application containers.
- [x] Restore representative database and file backups into isolated locations
      and check integrity. Mac-held key decrypts successfully; independent
      owner-held key copy is still unconfirmed.
- [ ] Prepare and validate the config/application-state rebuild procedure before
      an in-place OS upgrade: recovery boot/install instructions, preserved media
      disk UUID, host provisioning, exact k3s version/options, matching token and
      datastore, application-state restore and GitOps access. A full boot-disk
      image is outside the currently selected backup scope. If practical, rehearse
      software restoration in an isolated VM; this does not prove hardware boot
      or GPU recovery on ryback.
- [ ] Add backup failure alerts and retention; verify the first scheduled run.

**Exit gate:** A verified encrypted backup exists on the Mac, a restore test passes,
exclusions are understood and the rebuild recovery procedure is usable. Do not
proceed on backup-job success alone. Keep the Mac available through maintenance.

## Phase 3 — Update the host, one LTS transition at a time

**Completed and validated on 2026-10-09.** See the dated
[Jammy](ubuntu-22-upgrade-2026-10-09.md) and
[Noble](ubuntu-24-upgrade-2026-10-09.md) execution evidence. Broad package/kernel
cleanup and a normal owner usage cycle are deliberately not claimed complete.

**Agent-monitored remote maintenance with physical recovery available only as a
contingency; separate from k3s upgrades.**

### 3A. Prepare Ubuntu 20.04

- [x] Refresh package metadata after approval; inspect a simulated upgrade and
      package removals before applying anything.
- [x] Resolve package/configuration prompts, including the held-back Ubuntu Pro
      client. Do not globally force replacement of locally modified configs.
- [x] Decide how to exclude or handle obsolete Docker and other third-party
      packages; a blanket upgrade may restart services and change firewall rules.
- [x] Check free boot space, dpkg health, third-party repositories and release
      upgrader configuration. Record network and bootloader configuration.
- [x] Review the original kernel workaround and a hardware-compatible transition
      kernel. Avoid blindly selecting the installed 5.4 fallback. A transitional
      Focal kernel is not the long-term supported solution.

### 3B. Upgrade 20.04 to 22.04

- [x] Take fresh consistent recovery backups and establish the application
      maintenance state before the upgrade.
- [x] Perform the supported release upgrade remotely with a resilient terminal
      session and a prepared recovery route. Preserve/review local configuration
      deliberately; monitor reconnection after each reboot.
- [x] Ensure GRUB explicitly selects the new Ubuntu-managed kernel, not the old
      5.18 release candidate. Keep a known-working fallback initially.
- [x] Check cgroup/runtime/driver and swap configuration before reboot; make any
      necessary transition changes explicit and reversible.
- [x] Reboot and run technical acceptance checks. GPU blocker on Jammy resolved
      through separately approved device allocation and a real transcode test.
- [x] Take a new verified recovery checkpoint before the next transition; resolve
      the Jammy GPU issue rather than using Noble to hide it.
- [ ] Owner normal-usage cycle and full gameplay acceptance remain untested.

### 3C. Upgrade 22.04 to 24.04

- [x] Repeat preflight, backup, release upgrade, boot selection and acceptance.
- [x] Verify `/sys/fs/cgroup` reports `cgroup2fs`, the runtime and kubelet use
      compatible cgroup drivers, and the swap policy is intentional.
- [ ] Remove obsolete kernels only after successful boot/hardware validation and
      confirmation that recovery no longer depends on them.

**Exit gate:** Ubuntu 24.04 and a maintained kernel boot reliably; applications,
storage, GPU and unified cgroups work. Keep k3s/app versions unchanged where
compatible during this phase to isolate failures.

## Phase 4 — Bring k3s onto a supported branch

- [ ] Select exact k3s versions and check controller/chart/API compatibility.
      A supported 1.36 release is a candidate, not a pre-approved version choice.
- [ ] Preserve existing configuration and installer flags; do not rerun a generic
      installation command that might restore unwanted default components.
- [ ] Upgrade sequentially: `1.33 -> 1.34 -> 1.35 -> selected supported branch`.
      Version 1.34 is a stepping stone, not the final destination.
- [ ] Take a recovery checkpoint before each step and verify after each step.
      Unified cgroup v2 must be working before the 1.35 step.
- [ ] Validate cluster networking, local volumes, Flux, ingress, DNS, GPU and apps.
- [ ] Document the tested version and a deliberate future upgrade cadence.

**Rollback:** Restore the matching binary/configuration and datastore recovery
checkpoint according to k3s guidance; do not assume downgrading a binary reverses
datastore changes. Restore affected application data when required.

## Phase 5 — Replace retired ingress through Flux

Preparation can happen earlier, but cutover gets its own change window.

- [ ] Inventory nginx annotations, certificates, external-dns, redirects,
      WebSockets, uploads and authentication requirements.
- [ ] Choose a maintained controller or Gateway API implementation based on those
      requirements; do not choose solely because k3s bundles a particular option.
- [ ] Deploy alongside the old controller with a separate ingress class/address.
      Git changes, reconciliation and any commit/push require approval.
- [ ] Test one low-risk hostname, then important services and TLS renewal.
- [ ] Migrate routes in small batches; preserve a per-route rollback path.
- [ ] Remove the old controller only after every required route is verified.

**Exit gate:** All required access works on a maintained ingress implementation.

## Phase 6 — Security, cleanup and steady-state maintenance

These are separate reviewed changes, not an automatic cleanup script.

- [ ] Rotate exposed/reused credentials and remove plaintext secrets from active
      configuration. Do not rewrite Git history without an explicit decision.
- [ ] Verify a second SSH key session, then apply key-only SSH policy and intentional
      root/sudo access. Keep a recovery session during access-policy changes.
- [ ] Audit router forwarding and IPv6 exposure. Restrict Kubernetes management,
      kubelet and Flannel traffic to trusted networks while preserving required
      MetalLB/cluster/application traffic; do not blindly enable UFW.
- [ ] If confirmed unused, disable Docker in a separate reversible step, validate
      Kubernetes networking and reboot behavior, then remove obsolete packages
      later. Never remove the still-used app configuration directories.
- [ ] Repair fwupd checks; review motherboard firmware separately. Flashing BIOS
      requires its own justification, recovery plan and attended window.
- [ ] Introduce reviewable image/chart updates, version/digest tracking, database
      migration notes and rollback backups instead of uncontrolled mutable tags.
- [ ] Configure security-update, disk-health, service-health and backup alerts;
      monthly update reviews and scheduled reboot windows. Do not enable
      unattended major OS or Kubernetes upgrades.

## Acceptance checklist after every disruptive step

- [ ] SSH and console access; expected hostname, address and default route.
- [ ] Correct kernel, time synchronization and expected cgroup mode.
- [ ] All expected disk UUIDs mounted; `/mnt/volume1` is the actual media disk,
      not an empty directory on the root filesystem; ownership preserved.
- [ ] k3s node Ready, expected workloads/PVCs present, Flux Ready; no new persistent
      crash loops, failed migrations or unexplained restart increases.
- [ ] DNS, representative HTTPS URLs, certificates and external access work.
- [ ] Plex library access and a real hardware-transcode test.
- [ ] Sonarr/Radarr library and download-client connectivity; a representative
      download/import when authorized, with no unintended profile changes.
- [ ] Home Assistant/database, Foundry world, Obsidian sync and Vikunja read checks;
      targeted write tests only when approved.
- [ ] Host Node apps restart as intended; scheduled backups and alerts still work.

## Stop and rollback rules

Stop on lost access, missing storage, database errors, a non-Ready cluster or
critical application regression. Diagnose the current step before advancing.
OS recovery under the selected backup scope means rebuilding and restoring the
saved configuration/state, not downgrading Ubuntu packages or restoring a full
disk image. Database rollback requires a compatible data backup, not just
an older container image. Account for writes since the checkpoint; avoid running
old and restored application instances simultaneously against the same data.

## First actionable batch

Completed: safe host-only preflight, encrypted baseline, clean paused-app/book
checkpoint, and isolated PostgreSQL/CouchDB restores. See
[rebuild/recovery procedure](recovery-runbook.md) and the backup runbook.

Next:
1. Confirm independent key storage, bootable recovery equipment and upgrade route.
2. Confirm Google Calendar MCP restart procedure and application restore checks.
3. Review a refreshed apt simulation. Existing metadata currently proposes 79
   upgrades plus seven new packages, including Docker 20 → 28, Node, GRUB and
   firewall/runtime packages; no removals. Do not apply a blanket upgrade.
4. Authorize/schedule the reviewed host package preparation batch, then the
   separately gated OS transition.

No package updates or reboots are included in that first batch.
