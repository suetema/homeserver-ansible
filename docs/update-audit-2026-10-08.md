# Homelab update audit — 2026-10-08

## Scope and conclusion

Read-only investigation of this Ansible checkout and the live server, `ryback`
(`192.168.1.110`). No packages installed, repositories refreshed, services
restarted, workloads changed, credentials rotated, or upgrades performed. No
commit/push. This document is a local investigation report, not a deployment plan
approved for execution.

The Ansible repository was last committed on 2022-09-11. The server is **not
entirely frozen at its original installation**: automatic security updates run,
and applications have migrated to k3s/Flux. However, the OS, booted kernel, and
unused Docker installation need substantial attention. Do not rerun the old
playbook against the current server.

## Verified live state

| Component | Observed state | Assessment |
| --- | --- | --- |
| OS | Ubuntu 20.04.5 LTS | Standard support ended May 2025; no Ubuntu Pro subscription attached |
| Running kernel | `5.18.0-051800rc1-generic` | Unsigned, manually installed 2022 mainline release candidate, outside Ubuntu's normal kernel update stream |
| Boot selection | GRUB default entry explicitly boots the same release candidate; hidden menu, zero timeout | A reboot alone will not move to a maintained kernel |
| Installed distro kernel | `linux-generic` / `5.4.0-216-generic` | Installed security kernels are not the running kernel; HWE metapackage absent |
| Uptime | 232 days | Plan an attended reboot with recovery access, not a blind remote reboot |
| Automatic updates | apt timers and unattended-upgrades enabled and active | Security origins allowed; general `focal-updates` and Docker updates are not automatically covered by the observed origin policy |
| Pending packages | 79 upgrades in existing apt metadata | Not a freshly refreshed repository assessment; no explicit apt holds returned |
| Update blocker | Ubuntu Pro client upgrade requires a conffile decision | Unattended-upgrades logs repeatedly keep its related package back |
| k3s | `v1.33.11+k3s1`; node Ready | Upstream Kubernetes 1.33 reached EOL on 2026-06-28 |
| k3s runtime | Bundled `containerd://2.2.3-k3s1.33` | Separate from Docker's old host containerd; no external Docker/runtime endpoint observed in k3s unit |
| Resource management | Hybrid cgroup layout with resource controllers on v1; root reports `tmpfs` | Not unified cgroup v2; must address before Kubernetes 1.35+ defaults |
| Flux | 37 HelmReleases and 6 Kustomizations, all Ready | No broad deployment failure observed; applications belong to `../homelab-flux`, not this Compose file |
| Sonarr / Radarr | API versions `4.0.17.2952` / `6.1.1.10360`, both queues empty | Old repository pins 3.0.9 / 4.1.0 do not describe live applications |
| Plex | Running image `plexinc/pms-docker:1.43.4.10903-e5521bd8c` | Old repository pin 1.28.2 does not describe live Plex |
| Ingress | Community `ingress-nginx`, image v1.15.1, 25 Ingress resources overall | Upstream announced retirement after March 2026; plan migration rather than relying on a version bump |
| Docker | Engine 20.10.18, host containerd 1.6.8, bundled runc 1.1.4 | Old, still-running daemon; zero running Docker containers, three exited containers |
| Compose | Python-based v1.29.2; no `docker compose` plugin | Legacy Compose; current Ansible collection removed its v1 module |
| Clock | Synchronized via enabled `systemd-timesyncd`, `ntp.ubuntu.com` | Working; old `ntp` service is masked and package removed |
| Firmware | ASRock H610M-HVS BIOS 2.01, dated 2021-12-09 | Review vendor updates and changelogs; no latest-version comparison or flashing performed |
| Firmware tooling | `fwupd-refresh.service` failed repeatedly | Repair tooling/metadata checks before assessing supported device firmware updates |

Installed OpenSSH, OpenSSL and Intel microcode packages include later Ubuntu
security revisions. Do not infer an unfixed vulnerability solely from an old
upstream version string: Ubuntu backports fixes. Conversely, an unattached ESM
subscription and an unmanaged booted kernel leave real maintenance gaps.

## Priorities

### 1. Establish recoverable backups before maintenance

No scheduled host backup job was found in the checked timers, backup-named units,
cron locations, or root/user crontabs. The two Kubernetes CronJobs are dashboard
seeding and Recyclarr, not backups. Home Assistant's CNPG cluster has no backup
configuration/plugins and no ScheduledBackup resources were present. Off-host or
manually maintained backups remain unverified; confirm with the owner.

The k3s datastore is SQLite (`state.db`, WAL and SHM), **not embedded etcd**. Do
not assume `k3s etcd-snapshot` protects this installation. Back up a consistent
datastore and the server token, keeping the token encrypted and out of reports.

Required recovery coverage:

- `/var/lib/rancher/k3s/server/db` and `/var/lib/rancher/k3s/server/token`.
- k3s configuration/service options, Flux bootstrap access, and SOPS/age recovery
  credentials stored securely.
- `/var/lib/rancher/k3s/storage` — approximately 16 GiB. Local PVs include Foundry
  worlds, Home Assistant PostgreSQL, Vikunja data/database and a Plex PVC.
- `/etc/k8sconfigs` — approximately 7.2 GiB, including application databases.
- `/etc/dockerconfigs` — approximately 7.7 GiB; still used by Kubernetes Heimdall
  and Overseerr. Follow-up backup verification confirmed Plex's active `/config`
  is its local PVC, not the declared legacy hostPath. Legacy Plex state is retained
  too; the directory is not disposable.
- Application-consistent PostgreSQL dumps/backups, CouchDB backup, SQLite backups
  or quiesced copies with WAL handling, plus any other irreplaceable app state.
- Host scripts, user cron jobs, SSH/network/storage configuration, and the
  relevant content under `/mnt/volume1` (including books and retained media
  rollback backups). GitOps does not recreate database contents or local volumes.

Keep a verified copy on a separate device/location and test restoration of a
representative database. A same-disk copy is not sufficient protection for an OS
rebuild. A k3s service stop alone does not stop application containers.

### 2. Move to a supported OS and distribution-managed kernel

Recommended conservative target: Ubuntu 24.04 LTS with its maintained kernel and
unified cgroup v2. Ubuntu 26.04 LTS is another target to evaluate for supported
k3s/hardware combinations and longer support; it is not required merely to get
off 20.04.

For an in-place upgrade, use supported sequential LTS transitions:
`20.04 -> 22.04 -> 24.04`, validating and rebooting between stages; optionally
continue to 26.04 after a separate compatibility decision. Do not rewrite apt
sources to skip releases. A clean rebuild on a spare SSD could provide a cleaner
rollback boundary but requires a tested data/cluster restoration procedure.

Before selecting the route:

- Confirm console access, boot/recovery media, downtime tolerance and backups.
- Review why the original mainline kernel was installed. The server has an
  Intel i5-12400 / Alder Lake GPU using `i915`; hardware support may have motivated
  it, but that is not verified. Do not blindly boot the old 5.4 fallback.
- Choose and verify a maintained kernel and explicit GRUB boot entry; retain a
  known-working fallback until testing succeeds.
- Preserve mounts, UID/GID mappings and `/dev/dri` access. Validate networking,
  DNS, disks, k3s readiness and actual Plex hardware transcoding after reboot.
- Inventory the two host Node processes listening on ports 3500/3502 and their
  restart mechanism; they are outside the Kubernetes workload inventory.
- Review active swap (8 GiB, approximately 3.5 GiB used) and the kubelet swap
  policy as part of the cgroup migration, rather than changing it blindly.

If the migration must be delayed, Ubuntu Pro/ESM is an interim mitigation for
covered OS packages, not a fix for the unmanaged kernel or obsolete Kubernetes.

### 3. Upgrade k3s after resolving cgroups; plan ingress replacement

Select a supported k3s minor and compatible controllers/charts, then advance one
minor at a time (`1.33 -> 1.34 -> 1.35 -> ...`). Upstream 1.34 reaches EOL on
2026-10-27, so it is an intermediate step, not a sensible long-term destination.

Kubernetes 1.35 defaults `failCgroupV1` to true. Migrating the host to unified
cgroup v2 before that step avoids a kubelet startup failure. Preserve the
existing k3s configuration: blindly rerunning its installer without original
options can lose settings. Take fresh recovery backups before each upgrade and
validate Flux, DNS, ingress, storage, GPU access and applications after each step.

Replace community ingress-nginx through the Flux repository using a maintained
Ingress controller or Gateway API implementation. Inventory annotations, TLS,
external-dns, redirects, WebSockets and any authentication/mTLS requirements
before choosing a replacement. Do not confuse this project with similarly named
NGINX controllers maintained by other vendors.

### 4. Retire unused Docker or modernize it if still needed

The live k3s workloads use their own containerd. No running Docker workloads were
found, and the three exited containers have no mounts. Confirm occasional build
or scripting dependencies before deciding to retire Docker, its host containerd,
Compose v1, old bridges and images. Do not delete app configuration directories.

If Docker remains necessary, install a supported Engine and Compose plugin for
the target OS; use scoped signing keys and an OS-derived apt repository suite.
Account for Docker's firewall interactions with Kubernetes. Updating Docker is
not how the k3s runtime is upgraded.

### 5. Improve security and maintenance policy

- SSH password authentication and X11 forwarding are enabled; root key login is
  permitted. After verifying alternate access, define a key-only SSH policy and
  intentional root/sudo access. The user has unrestricted passwordless sudo and
  Docker group membership, both effectively root-level access.
- UFW is disabled; host INPUT/FORWARD policies are ACCEPT with Kubernetes chains.
  Listeners include SSH, Kubernetes API/kubelet, RPCbind, Plex and the two host
  Node apps. Router forwarding, IPv6 reachability and actual Internet exposure
  were not audited. Restrict management and Flannel ports to trusted networks;
  do not enable UFW blindly on a working k3s/MetalLB node.
- The tracked legacy Compose file contains a plaintext NZBGet password. Treat it
  as exposed, rotate it if still used/reused, and move secrets out of plaintext
  Git. A history rewrite or live credential rotation requires separate approval.
- Resolve the held-back Pro client configuration decision; define regular
  package/application reviews, reboot windows, backup checks and notifications.
- Many live images use mutable `latest`, `preview` or major-only tags. Inventory
  resolved versions/digests and introduce reviewable updates with database
  rollback plans; the declared tag alone cannot prove currency.

## Ansible changes needed before reuse

| File | Problem / proposed direction |
| --- | --- |
| `hosts` | Stale `10.0.0.219`; define named host at `192.168.1.110` and explicit connection variables |
| `homeserver.yaml` | Always deploys Docker and old Compose apps; separate host provisioning from Flux-managed applications and make obsolete deployment opt-in/archival |
| `roles/docker/vars/main.yaml` | Hardcodes Ubuntu `focal`, x86_64 and Compose 1.28.2 download; derive suite/architecture and reconsider whether Docker is required |
| `roles/docker/tasks/main.yaml` | Legacy `apt_key`, global pip installation, duplicate Docker-group task and undefined `user` in task label; use scoped keyring, supported packages, explicit variables and idempotent tasks |
| `roles/compose/tasks/main.yaml` | Installs Python Compose v1 and invokes removed `community.docker.docker_compose`; archive if unused, otherwise use plugin plus `docker_compose_v2`. Global pip conflicts with externally managed Python on newer Ubuntu |
| `roles/compose/files/docker-compose.yaml` | 2022 image pins, plaintext credential, divergent download paths. It must not be treated as the live desired state or redeployed over active app data |
| `roles/common/tasks/ntp.yaml`, `group_vars/all.yaml` | Old NTP daemon/time-source config does not match functioning timesyncd; rerun would try starting a masked service. Manage one deliberate time service |
| `roles/common/tasks/dns.yaml` | Disabled today; its raw sed command is non-idempotent and unsafe to revive without checking resolv.conf and cluster DNS requirements |
| `roles/common/tasks/powertop.yaml` | Blanket auto-tune is active; review hardware-specific policy and ensure daemon reload occurs before starting changed unit files |
| `roles/nfs-client/` | Unused by the playbook; current media disk is local ext4, not an NFS mount. Retain/archive intentionally rather than assume it is required |
| Repository tooling | No pinned Ansible/collection requirements, lint/test configuration or documented supported OS. Local ansible-playbook and ansible-lint are absent; syntax/lint execution was not performed |

Keep the modernization focused on host configuration, backups, security,
storage, supported kernel and deliberate runtime lifecycle. Leave application
deployment ownership in `homelab-flux`.

## Lower-priority observations and limits

- Root has approximately 632 GiB free; `/boot` approximately 1.3 GiB free; media
  disk approximately 8.3 TiB free. No capacity-driven replacement is indicated.
- Both disks report SMART PASSED with zero reallocated/pending/uncorrectable
  sectors in the checked attributes. The media HDD has approximately 35,305
  power-on hours. This is not a guarantee against failure; no self-tests run.
- Geo Activity Playground has 12,151 historical restarts but has been running
  since August 14. Its recorded last failure was a missing executable, not a
  current crash loop. Review separately; do not describe all Ready apps as broken.
- Other controllers have historical restart counts. Current Ready status does
  not establish full end-to-end application health or latest-version compliance.
- Full firmware comparison, package vulnerability scanning, router rules,
  off-host backup verification and exhaustive app-by-app upgrade compatibility
  are outside this first pass.

## Recommended next decision

Confirm existing off-host backups and available recovery/downtime access, then
choose an in-place sequential OS upgrade versus spare-SSD rebuild. Prepare the
backup/restore and host-only Ansible changes for review before any execution.

### Backup follow-up, 2026-10-08

The first encrypted database archive has been verified on the Mac. Both current
PVC-backed Plex databases passed native integrity checking. A retained legacy
Plex library database under `/etc/dockerconfigs` reported malformed entries;
do not substitute that old database for the active PVC-backed state during
recovery. The complete encrypted baseline subsequently finished successfully.
The user then separately authorized legacy Plex cleanup: the admin tools were
updated, stale GitOps/Compose references removed, and the old directory deleted
after a further full encrypted archive and exact file-hash comparison. 3.81 GiB
reclaimed; active PVC, owner/Kids libraries and tools verified afterwards. The
legacy database is now retained only in the encrypted recovery archives.
See [backup runbook](backup-runbook.md) for results and remaining recovery gates.

## Lifecycle and migration references

- [Ubuntu lifecycle data](https://endoflife.date/ubuntu) (secondary source; Canonical pages returned HTTP 503 during this audit).
- [Kubernetes 1.33 EOL](https://kubernetes.io/releases/1.33/).
- [Supported Kubernetes releases](https://kubernetes.io/releases/).
- [cgroup v2 migration and 1.35 startup behavior](https://kubernetes.io/blog/2026/10/06/kubernetes-cgroups-v2-shift/).
- [Ingress NGINX retirement](https://kubernetes.io/blog/2025/11/11/ingress-nginx-retirement/).
- [k3s SQLite backup and token requirements](https://docs.k3s.io/datastore/backup-restore).
- [k3s upgrade sequencing and configuration preservation](https://docs.k3s.io/upgrades/manual).
- [Removed Ansible Compose v1 module](https://docs.ansible.com/ansible/latest/collections/community/docker/docker_compose_module.html).
