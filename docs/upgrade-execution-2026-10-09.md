# Authorized host upgrade execution — 2026-10-09

## Authorization and scope

The owner explicitly requested starting upgrades, accepts service interruptions
and reboots, and requested subagents so the coordinating agent remains available
for status questions. This supersedes older preparation documents saying host
upgrades were not yet authorized.

Accepted route: **Ubuntu 20.04 → 22.04 → 24.04**, one transition at a time, with
recovery checkpoints and validation between transitions. Kubernetes, ingress,
application migrations and security changes are not combined with this OS unit.

Owner confirms possession of the backup key and emergency physical access.
Recovery USB is planned if needed, not currently prepared/verified. Loss of boot
or SSH access requires stopping remote follow-on work and escalating to physical
recovery. Existing encrypted backups are on the Mac, not a full boot-disk image
or full media-disk backup. Full Foundry gameplay recovery remains unverified:
owner chose to keep isolated tests offline rather than validate clone licensing.

## Delegated work

| Responsibility | Scope | Initial state |
| --- | --- | --- |
| Host upgrade agent | Supported sequential Ubuntu upgrades, reviewed package/config decisions, checkpoints, reboot and acceptance | Completed validated Ubuntu 24.04.5 / 6.8.0-146; stopped after OS acceptance; no longer mutating |
| Recovery/compatibility review agent | Independent offline/official-documentation review for boot/runtime risks and Noble transition | Completed; no blanket Noble/i5-12400/current-k3s incompatibility found; findings forwarded to executing agent |
| Plex GPU agent | Diagnose, then deploy separately approved minimal GPU device allocation and validate real hardware transcoding | Completed deployed fix and real VAAPI transcode acceptance; no rollback needed; no longer mutating |
| SSH recovery agent | Explicitly approved emergency Kubernetes jobs: inspect SSH, start service if safe, verify fresh SSH and remove jobs | Completed: fresh SSH/sudo passed, both jobs removed, zero recovery pods/jobs left; no longer mutating |
| Coordinating agent | User communication, milestone review, authorization tracking and decisions on continuation | Available for status questions |

The executing agent stops at the verified Ubuntu 22.04 milestone or a concrete
blocker. The coordinator reviews the results before continuing to 24.04 under
the same owner authorization. Do not run a second host mutator concurrently.

**Current outcome: the sequential OS upgrade is complete. All subagents have
finished; no follow-on k3s/application/ingress upgrade is running.**

## Progress sources

- `docs/ubuntu-22-upgrade-2026-10-09.md`: executing agent's local progress/evidence.
- `/var/backups/homelab-upgrade/status.json` on ryback: credential-free phase
  status, maintained by the executing agent once established.
- `docs/upgrade-recovery-review-2026-10-09.md`: independent review findings.

Respond to owner-requested status checks using actual current evidence. Do not
equate agent launch, package download, or a still-running release upgrader with
successful completion. If SSH is unavailable during the planned reboot, report
that state and the reconnection deadline rather than claiming success.

Independent review completed: see `docs/upgrade-recovery-review-2026-10-09.md`.
Priority handoff covers actual GRUB selection, media mount identity, k3s service
stop versus running containers, intentional cgroup/swap behavior, Jammy GPU/HWE
validation, and Noble SSH socket activation/service restarts. This is a
compatibility-review result, not evidence that packages or Ubuntu changed yet.

## Verified Jammy milestone and hold

Executing agent completed Ubuntu **22.04.5 LTS**, then installed/booted maintained
HWE **6.8.0-138-generic**. SSH reconnected within the monitored deadline. Existing
k3s **v1.33.11+k3s1** is unchanged; all **58 running pods** and **43 Flux resources**
Ready, six real UUID mounts verified, unified cgroup v2 and drivers validated.
MCP OAuth authentication and a stdio initialize/tools-list check passed. Earlier
ports 3500/3502 were authentication callbacks, not persistent MCP HTTP services.

Actual prerequisite/release transactions and reviewed configuration decisions
are recorded in `docs/ubuntu-22-upgrade-2026-10-09.md`. Narrow inotify adjustment
resolved Spottarr startup exhaustion without manifest/image changes. Fresh
verified encrypted checkpoint: `~/homelab-backups/ryback/20261009T063359Z-bb1e3ce0/`.

**Hold before Ubuntu 24.04:** Plex GPU nodes exist, and host opens succeed, but
opens inside its pod fail with `EPERM`. Preupgrade hardware-transcode functionality
was not directly established; call this an acceptance blocker, not a proven
working-transcode regression. Dedicated diagnostic agent is collecting evidence
without a privileged-pod patch, blanket AppArmor/cgroup disabling or GPU driver
changes. A required GitOps/device-policy fix must be reviewed/authorized before
deployment. Dormant Compose v1's Python migration failure is separately recorded;
Docker engine, configurations and data remain preserved.

No 24.04/k3s/app upgrade is claimed. Parent will review diagnostic findings, get
approval for any out-of-scope deployment change, and resume the already authorized
Noble transition only after resolving or explicitly deferring this acceptance gate.

## GPU fix approval and execution

Diagnosis established container-scope cgroup-v2 DRM-device denial, not missing
i915 or incorrect file groups. `/dev/dri` hostPath visibility alone is not a
Kubernetes device allocation. See `docs/plex-gpu-diagnosis-2026-10-09.md`.

Owner answered **"do it"** to the explicit proposal to commit/push and deploy
the narrow Flux fix, preserving Plex data and keeping Plex unprivileged:

1. Deploy reviewed standalone Intel GPU plugin **v0.37.1**, ryback only.
2. After GPU resource discovery, pin Plex's existing chart **1.9.0** and add
   `values.pms.resources` request/limit **gpu.intel.com/i915: 1**.
3. Validate native opens, unchanged image/PVC/server identity and a short real
   hardware transcode; preserve sharing, account settings and cloud registration.

This authorizes only the required plugin/Plex manifest commits/pushes and the
normal Plex rollout, not unrelated Flux working-tree changes or privilege/security
workarounds. The agent stops at verified GPU acceptance (or a concrete blocker).
The parent then reviews results and resumes the already authorized Ubuntu 24.04
transition; the GPU agent does not simultaneously mutate the OS.

### GPU acceptance passed; Noble continuation launched

GPU agent completed the approved fix. Plugin commit
`bd92dcda9b3425fc297a5708841cc2f4f66fbc5e` and Plex allocation/chart-pin commit
`402d5b676dde3d08dae82a645a3ce7f00b609d61` are pushed/reconciled. All eight native
device-open checks pass; OCI allocates DRM 226:0 and 226:128. A real PMS HLS
transcode generated 985,496 bytes and reported VAAPI decode **and** encode,
`transcodeHwFullPipeline=1`; only the owned test stream was stopped afterward.
Same Plex image, active PVC/UID and server identity verified. All **59 running
pods** and **43 Flux resources** Ready; no rollback needed.

The parent reviewed `docs/plex-gpu-fix-2026-10-09.md` and resumed the OS agent
under the original owner authorization for **22.04 → 24.04**. Fresh narrow
encrypted checkpoint, reviewed stable release upgrade, actual GRUB/SSH checks,
controlled reboot and storage/runtime/app/GPU acceptance are required. No Noble
completion is claimed until that agent reports verified evidence. It stops at
Noble acceptance and does not automatically upgrade k3s/apps/ingress afterward.

## Current blocker: SSH lost during Noble installation

Noble agent stopped at **2026-10-09T08:21:03Z** after both SSH ports 22/1022
remained unavailable beyond the ten-minute deadline. k3s 6443 and Plex 32400
are reachable; this is not evidence the machine is dead or successfully rebooted.
Noble completion, SSH failure cause, boot selection and acceptance remain
unverified. No reboot requested and no further mutator is running.

Fresh verified checkpoint before packages:
`~/homelab-backups/ryback/20261009T075949Z-b6d955cb/`. Working Jammy kernel builds
protected; persistent root upgrade terminal is `ubuntu24`. Remote status JSON is
stale at `noble-release-packages` because SSH is unavailable. Current full handoff
is `docs/ubuntu-24-upgrade-2026-10-09.md`.

Ask the owner to log in at the existing local console and run
`sudo systemctl start ssh.service`. If unsuccessful, inspect
`sudo systemctl status ssh.service ssh.socket --no-pager` and attach with
`sudo /var/backups/homelab-upgrade/tmux-jammy attach -t ubuntu24`.
Do not reboot, kill apt/dpkg, reset packages or accept configuration prompts
blindly. After owner reports restored access, resume the existing monitored
transaction and SSH/boot review; do not launch a new concurrent upgrader.

### Owner cannot log in; alternate recovery authorized

Owner reports forgetting the server user's password. Do not initiate a password
reset/reboot while the persistent package transaction may be active. Independent
read-only access check established existing private Mac kubeconfig works against
the k3s API using client-certificate auth, CA and hostname verification. Node
reports Ubuntu 24.04.5 userspace on the old running kernel; this still does not
prove package completion, boot selection or acceptance.

Owner explicitly answered **yes** to one-time temporary **privileged hostPID /
host-root recovery jobs**, acknowledging full host-root authority, to inspect SSH
and start `ssh.service` if safe, then delete only those owned jobs. This is a
narrow emergency direct-Kubernetes exception to normal GitOps policy. No RBAC
changes, password reset, reboot, package interruption, permanent security-policy
changes or unrelated workload edits are approved in that recovery unit.

The SSH recovery agent alone executes this action, checks fresh key login/sudo,
verifies owned privileged job/pod cleanup, and returns. Parent then resumes the
original OS agent to review the existing upgrade terminal—not start a second
upgrader. See `docs/ssh-recovery-access-2026-10-09.md` for inspected proposal and
subsequent evidence. Do not claim SSH restored until actual verification.

### SSH recovered; original Noble transaction resumed

Recovery agent verified fresh public-key login and sudo after the narrow service
start. SSH service/socket were loaded, inactive and unmasked; no configuration,
network or password change was needed. Both jobs exited zero, and independent
API cleanup check found **zero** owned recovery jobs/pods. The privileged recovery
exception is not a persistent workload. See
`docs/ssh-recovery-execution-2026-10-09.md`.

Recovery did not touch dpkg, packages or the upgrade terminal and did not reboot.
Ubuntu 24.04.5 userspace on the old running kernel is verified, but package
completion and Noble acceptance are not. Parent handed sole mutation authority
back to the original OS agent to review **existing** root tmux `ubuntu24`, finish
the transaction and perform reviewed boot/SSH/storage/app/GPU validation. No
second upgrader or additional concurrent host mutator is authorized.

## Final outcome — validated Noble

Original OS agent finished the existing transaction, reviewed sudoers/sysctl/SSH
configuration, then rebooted at **09:18:32 UTC** and regained fresh key/sudo SSH
at **09:21:00 UTC**. No second SSH recovery or physical intervention required.

- **Ubuntu 24.04.5 LTS**, actual kernel **6.8.0-146-generic**; exact working Jammy
  fallback kernel/initrd preserved. Package transaction and dpkg/apt health pass.
- All six UUID filesystems genuinely mounted writable before k3s resumed.
  Media ownership, original fstab, application images and PVC UIDs preserved.
- k3s unchanged **v1.33.11+k3s1**, unified cgroup v2/systemd drivers, intentional
  swap retained. **59 pods / 43 Flux resources Ready**, cluster DNS and all
  **22 ingress** DNS/TLS/HTTPS checks pass.
- GPU native opens and real PMS VAAPI decoding/encoding pass after reboot;
  Intel driver now enumerates **card1**, not card0. Plugin correctly allocates
  it. All owned transcode streams stopped, no watch-state/account changes.
- Both same-user MCP stdio checks pass (version 2.6.1, 13 tools each). Private
  OAuth file restored to `/tmp` from the durable 0600 copy; no new registration.
- Noble **ssh.socket enabled/active**, ssh.service socket-triggered; syntax,
  fresh key login and sudo pass. Temporary privileged recovery jobs remain gone.
- Root phase **validated-noble**, final evidence alongside verified checkpoint
  `~/homelab-backups/ryback/20261009T075949Z-b6d955cb/`. Owned checkpoint plaintext
  and failed initial staging removed after verification/acceptance.

Details: `docs/ubuntu-24-upgrade-2026-10-09.md`. Nonblocking follow-ups are dormant
Compose v1's Python import failure, excluded third-party repositories, three
temporary Jammy fallback holds, deferred obsolete-package/kernel cleanup, and
the old probe's hardcoded card0 assumption. Owner normal usage/full Foundry
gameplay and whole-machine USB/rebuild remain untested. Local docs/helpers are
uncommitted; only the separately approved Plex GPU manifests were pushed. No
automatic k3s, ingress, application or security continuation was performed.

## Follow-up correction: unchanged image specs were not unchanged app code

Owner subsequently reported new Basic/login prompts at Sonarr/Radarr hostnames.
Read-only historical/current comparison established an unintended first-reboot
image update through `latest` / `Always`: Sonarr **4.0.17.2952 → 4.0.20.3014** and
Radarr **6.1.1.10360 → 6.4.4.10685**. Manifest image strings remained unchanged,
but actual image digests/code did not. The earlier coordinator description of
unchanged application versions was therefore inaccurate; readiness and protected
HTTP responses alone did not prove an unchanged user experience.

Stored credentials/auth settings and ingress image stayed unchanged. New app
proxy-trust behavior breaks the previous LAN bypass behind nginx; UI authentication
is now an unresolved owner-facing acceptance issue. See
`docs/arr-auth-diagnosis-2026-10-09.md`. No app downgrade is authorized. K3s is
still unchanged; its separate plan now requires approved immutable image/chart
drift controls before further restart/upgrade.

### Separately approved private-access repair

Owner selected passwordless **LAN and their Tailscale devices**, confirmed no
public port-forward/tunnel for these apps, and explicitly approved commit/push /
deployment of the narrow repair. Sole live operator is the arr repair agent:

- Pin current Sonarr/Radarr images and chart versions; do not upgrade/downgrade
  code or migrated databases and do not touch unrelated Flux work.
- Preserve client IPs by changing shared nginx Service policy to
  `externalTrafficPolicy: Local`, with validation of all 22 ingress resources.
- Configure narrow current nginx proxy trust; retain Basic/Forms, passwords,
  API authentication and nonlocal/public-source UI authentication.
- Retain Tailscale routing/SNAT/ACLs unchanged. Owner explicitly trusts permitted
  Tailscale clients; their masked source is not a reason to broaden public trust.

Deployment completed through approved Flux commits `109aa59` and `2d922f7`.
LAN roots return 200; protected APIs still require authentication, and controlled
public-source requests still receive Basic 401 / Forms login redirect. All 22
ingress routes, 59 pods and 43 Flux resources validated; credentials, app versions
and imageIDs unchanged. Only Sonarr/Radarr rolled. See
`docs/arr-private-access-fix-2026-10-09.md` for exact pins and evidence.

Controlled forwarded-source tests are not an actual external/phone access test;
off-Wi-Fi phone/Tailscale verification remains manual. Narrow nginx proxy trust
fails closed if its pod IP changes; future restarts/migrations must re-verify it.
No k3s upgrade, ingress replacement, global authentication disable or other app
rollout was performed or authorized by this repair approval.

## Boundaries and stop rules

### Accepted k3s outcome

The authorized Ansible hops **1.33.11 → 1.34.12 → 1.35.9+k3s1** have completed,
with verified encrypted matching stopped-SQLite checkpoints before each binary
promotion and at least 30 real minutes of observation after each hop. Coordinator
independently reconfirmed installed 1.35.9, active service and root phase
`validated-k3s-1.35`, no active command. Details and receipt IDs:
`docs/k3s-upgrade-execution-2026-10-09.md`.

Final evidence: 59 Ready pods, 43 Ready Flux resources, seven original Bound PVCs,
six RW UUID mounts, 22 DNS/TLS/HTTP routes, unchanged accepted app code, and real
Plex hardware transcode with owned-session cleanup on both hops. Automation
restored via Flux commit `e809c42`; temporary safeguards removed. 59 tests and
syntax/lint pass; desired-version normal/check convergence made zero changes.
Ansible role/playbook/inventory are local/uncommitted. No host reboot, 1.36,
ingress replacement or Flux upgrade occurred. Full rebuild/restore, adversarial
recovery and normal owner/phone usage remain unclaimed; later paragraphs retain
earlier execution chronology, not the current completion state.

### Subsequent k3s authorization

After the completed private-access repair, owner explicitly requested starting
k3s upgrades and required all host upgrade changes applied through Ansible so
the installation is reproducible. The delegated Ansible/k3s agent is the sole
live operator. Scope is checkpointed adjacent upgrades **1.34.12 → 1.35.9** with
preserved host/service/storage configuration and application versions, not an
unreviewed 1.36 ingress/Flux migration. No host reboot is planned. Fresh recovery
and drift gates apply before binary changes; no successful hop is claimed here.

See `docs/k3s-upgrade-plan-2026-10-09.md` for authorization/stop boundaries and
`docs/k3s-upgrade-execution-2026-10-09.md` for the delegated execution record.
Default host preflight remains read-only; explicit mutating Ansible automation
must capture version/checksum/configuration and pass check/idempotence tests.

The delegated first-hop run has now completed **blocked before the first service
pause** at the image/chart isolation gate: 16 unpinned Always references and 33
broad chart constraints. Actual k3s remains **v1.33.11+k3s1**, cluster healthy
(59 Ready pods / 43 Ready Flux resources / seven Bound PVCs). No binary change,
checkpoint, restart, Flux suspension, reboot, commit or push occurred. Only the
root status phase changed through Ansible, retaining Noble history. The new role
and playbook passed syntax/lint and 42 tests; current-version check and normal
convergence made zero changes. Post-gate upgrade/bootstrap paths are not yet
production-validated. No background mutator remains active.

Owner then explicitly selected **"Pin and resume"**: narrow current-version
GitOps image-digest / installed-chart pins, commits/pushes and necessary rollouts
for remaining apps, init containers, sidecars and Tailscale components are now
authorized. No newer application code/settings are allowed. The same delegated
agent resumed as sole live mutator; a separate read-only local reviewer examines
new Ansible upgrade/checkpoint code before the first k3s service pause. Host
changes stay Ansible-managed and application specs stay Flux-managed. The prior
blocked attempt remains historical, not a claim that an upgrade has now succeeded.

Independent local review then found unbounded synchronous service/capture waits
and a Plex cleanup-success gap. Sole live operator has been instructed to fix
both, add negative regression tests, and return for re-review before the first
k3s pause/promotion. App pinning remains authorized. The findings are code-derived,
not evidence of any production failure or a completed Kubernetes upgrade.

Approved application isolation has now completed in Flux commits `fc10bcc`,
`8715c31`, `f5358ec`, `5ec9996`, `00dd898`, `c9050a9`. Accepted code/digests stay
unchanged; 59 pods / 43 Flux resources / seven PVCs / 22 routes validated, and
the image/chart guard reports zero remaining isolation violations. Image update
automation is temporarily suspended and must be restored after acceptance.

The operator fixed/tested both review findings (58 tests pass) and handed back
before any k3s pause/checkpoint/promotion. Independent re-review is running with
DeepSeek V4.1 Flash, as requested by owner to conserve OpenAI usage. The execution
agent also uses DeepSeek; no second host mutator or new model-independent
authorization is implied. Actual k3s remains 1.33.11 pending review clearance.

Independent re-review subsequently returned **YES** (58 tests, no remaining
material finding); coordinator cleared execution with explicit
`k3s_code_review_cleared=true`. Sole DeepSeek operator resumed checkpointed
Ansible hops 1.34.12 → 1.35.9. This clearance is not evidence of a completed
hop; execution details/actual acceptance belong in the delegated k3s record.

- Preserve media UUID/mount, application/PVC data, existing k3s configuration and
  unrelated repository work. No disk formatting, broad cleanup or Git pushes.
- Review major third-party Docker/Node changes and local configuration prompts.
  Do not apply an unreviewed blanket upgrade or indiscriminate autoremove.
- Retain the known-working kernel fallback; explicitly review booting a maintained
  hardware-compatible kernel instead of the pinned 5.18 release candidate.
- Privately preserve the MCP OAuth file currently under `/tmp` before reboot;
  restore the existing integrations without displaying credentials or imposing
  an unrequested startup-service design.
- Stop on lost access, missing storage, database errors, non-Ready cluster or
  unexplained critical regression. Do not stack another upgrade on a failure.
- Actual kernel, GPU, cluster, application and MCP checks must be reported with
  their limits; HTTP 200 is not proof of gameplay or hardware transcoding.
