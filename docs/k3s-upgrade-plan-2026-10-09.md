# k3s upgrade plan — 2026-10-09

**Status: COMPLETE through v1.35.9+k3s1, deployed and validated via Ansible.** Owner explicitly
requested starting k3s upgrades and required changes applied via an Ansible
playbook for reproducibility/redeployment. Preparation, consistent checkpoint
and drift gates still precede every binary change; authorization is not evidence
that a release is already installed. Execution scope ends at 1.35.9, before the
separate ingress/Flux decisions for 1.36. The Sonarr/Radarr repair is deployed and
validated on LAN; real phone/Tailscale verification remains manual.

## Accepted execution outcome

Both adjacent hops passed, each with a fresh stopped-SQLite checkpoint encrypted
and fully verified on the Mac, functional validation and at least 30 real minutes
of observation. Checkpoints: `k3s-20261009T131032Z-2f1aa6ae` and
`k3s-20261009T135422Z-6756f9d6`. Coordinator independently reconfirmed actual
`v1.35.9+k3s1`, active service and root phase `validated-k3s-1.35`, with no active
command. See `docs/k3s-upgrade-execution-2026-10-09.md` for detailed evidence.

- 59 pods / 43 Flux resources Ready, seven original Bound PVCs, six UUID mounts
  RW, all 22 DNS/TLS/HTTP ingress checks pass; accepted app code unchanged.
- Real Plex hardware transcode passed on both hops, with owned sessions stopped.
- Image update automation restored via approved narrow commit `e809c42`; pins
  retained and temporary checkpoint safeguards removed.
- 59 tests pass, syntax/lint pass; installed/default-target normal and check
  convergence both changed zero. Version/checksum/rebuild configuration is in
  `k3s.yaml`, `roles/k3s/` and production inventory; local Ansible changes remain
  uncommitted, not automatically synchronized to another machine.
- No reboot, ingress replacement, Flux version update or k3s 1.36 upgrade.
  Next upgrade stage still requires separately approved ingress/Flux work.
- Full fresh-host/whole-machine restore, adversarial timeout recovery, Foundry
  gameplay and normal owner/off-LAN phone usage remain unclaimed/manual.

The remaining sections preserve the planning, blocked-attempt and clearance
history; their older current-version/status statements are historical.

Actual release remains **v1.33.11+k3s1**. Implemented `k3s.yaml` / `roles/k3s`
passed syntax/lint and 42 tests; current-version convergence changed nothing.
The first-hop guard found **16 unpinned Always references (13 unique images)**
and **33 broad chart constraints**. That blocked attempt performed no binary
change, checkpoint, restart, Flux suspension or reboot. Owner then selected
**"Pin and resume"**, approving narrow current-version image/chart GitOps pins,
commits/pushes and necessary rollouts, including sidecars/init containers and
Tailscale components. The same sole live operator is now executing that isolation
and will resume already-authorized Ansible hops after validation. Execution record:
`docs/k3s-upgrade-execution-2026-10-09.md`.

## Verified starting point

- One node: ryback, Ubuntu 24.04.5, maintained kernel 6.8.0-146-generic.
- k3s v1.33.11+k3s1; SQLite datastore, not embedded etcd. Its containerd is
  independent from the dormant Docker engine's host runtime.
- Unified cgroup v2, matched systemd drivers; intentional swap policy retained.
- 59 running pods and 43 Flux resources Ready at final OS acceptance.
- Intel GPU device allocation is now explicit. Native device opens and a real
  Plex VAAPI decode/encode pipeline passed after the Noble reboot.
- Existing encrypted checkpoints are on this Mac, but each Kubernetes hop needs
  its own fresh, consistent recovery checkpoint before changing the binary.

These are the completed OS acceptance facts. The planning audit must reconfirm
current readiness and relevant configuration before selecting upgrade pins.

## Proposed sequence

1. **Version and dependency review.** Verify exact stable release tags/support
   dates and installed Flux, ingress, cert-manager, MetalLB, Tailscale, CNPG,
   GPU plugin and CRD compatibility. Treat nginx retirement separately from a
   proven version incompatibility. Decide whether any prerequisite must be
   updated/replaced before a particular Kubernetes hop.
2. **Select a supported, mature target.** Recommended exact ladder below targets
   the observed stable 1.36 release, with adjacent minor steps. The preparatory
   current-minor patch is recommended but optional, not a skew requirement.
3. **Prepare one-hop maintenance.** Record current binary checksum, service
   arguments/config/environment sources, live image IDs, PVC identities and
   expected readiness. Review automated updates and mutable-image/wide-chart
   drift risks. Do not indiscriminately rewrite all application manifests.
4. **Create the recovery checkpoint.** Capture consistent k3s SQLite state with
   matching token, binary, configuration/TLS and deployment/PVC inventory;
   encrypt and verify off-host. Stopping k3s alone does not quiesce applications;
   do not label unrelated hot file copies as consistent application backups.
5. **Upgrade exactly one minor.** Verify the chosen binary/checksum/provenance;
   preserve custom flags and disabled bundled components. Do not run an unpinned
   generic installer that resets service options. Keep apps/ingress versions
   unchanged during the Kubernetes step except separately reviewed prerequisites.
6. **Validate and pause.** Verify storage, cluster/controllers/CRDs, network/DNS/
   TLS, app/PVC identities, GPU allocation and a bounded real Plex transcode.
   Observe restart/error trends and allow meaningful usage before the next hop.
7. **Repeat with a new checkpoint.** Do not run a second minor upgrade to hide
   a failure from the first one. Stop after the chosen target's acceptance.

## Downtime and recovery

Single-node k3s restart interrupts the API/controllers and can affect workloads;
do not promise uninterrupted streaming. **A host reboot is not normally required
for a k3s binary upgrade**, unlike the completed OS upgrades. Any newly necessary
host/kernel change gets its own review, not an incidental reboot.

Stop on missing mounts/PVCs, persistent non-Ready node/controllers, API/database
errors, broken DNS/TLS or GPU/transcode failures. Rollback requires the matching
previous binary **and** compatible consistent datastore/token/configuration,
following the exact k3s recovery procedure. Merely downgrading the binary is not
proof that database migrations reverse. Account for writes after the checkpoint.

Never restore legacy Docker Plex state or point apps at empty root directories
when the media disk is missing. Avoid unapproved account/licensing/sharing changes.
Maintain SSH and read-only Kubernetes recovery access; no standing privileged
recovery workloads are left by the earlier OS repair.

## Remaining planning outputs

- `docs/k3s-upgrade-preflight-2026-10-09.md`: fresh read-only live compatibility
  audit, written by its dedicated agent.
- `docs/k3s-version-research-2026-10-09.md`: verified official release/lifecycle
  research, written by a separate agent.
- Final exact release ladder, prerequisite order, acceptance/rollback commands
  and owner-approved execution window after those findings are reviewed.

The initial request was planning-only. Owner subsequently explicitly requested
execution through Ansible (see authorization below). Prior OS/GPU approvals and
this Kubernetes authorization do not silently authorize ingress replacement,
Flux upgrades or unrelated application changes.

## Execution authorization and ownership

Owner: **"no start upgrading k3s, make sure the changes are applied via the ansible
playbook so the server re-deployable"**. This rejects the coordinator's proposed
prepare-only pause and authorizes starting the already reviewed Kubernetes work.

- Sole live operator: delegated Ansible/k3s implementation agent. No concurrent
  host mutator, manual one-off binary replacement or generic installer command.
- Implement an explicit mutating playbook/role with exact version/checksum,
  preserved service options, prerequisite/storage checks, checkpoint gating,
  bounded restart/readiness validation and idempotence tests. Keep default
  `homeserver.yaml` preflight read-only; historical unsafe roles stay uninvoked.
- Required adjacent minors: **v1.34.12+k3s1 → v1.35.9+k3s1**. The preparatory
  1.33 patch is optional and may be omitted per official upgrade guidance.
- Fresh matching consistent encrypted/off-host verified SQLite/token/binary /
  configuration checkpoint before each hop. Preserve application/PVC data and
  distinguish k3s consistency from application backup consistency.
- Minimal maintenance/drift controls must preserve GitOps ownership, accepted
  app code and previous automation state. Do not use Ansible as a second app
  deployment authority or silently update mutable images. Report a concrete
  unresolved safety gate rather than bypass it merely to start the binary change.
- No host reboot, ingress replacement, Flux upgrade, application downgrade,
  unrelated app rollout, destructive storage operation or new privileged recovery
  job is authorized. Subsequent isolation approval permits narrow Flux commits /
  pushes and necessary **same-code** image-pin rollouts, not newer app releases
  or unrelated local changes. Host changes remain Ansible-owned, apps Flux-owned.
- Stop after validated **1.35.9**; 1.36 remains gated on separately approved
  ingress migration and Flux review. Stop earlier on any acceptance failure.

Execution evidence belongs in `docs/k3s-upgrade-execution-2026-10-09.md`. Ansible
must make the host installation/version reproducible; recovery of the existing
datastore, token, PVC/application data and GitOps secrets remains the separately
documented restore procedure, not something a fresh install magically recreates.

An independent **read-only local code review** is checking the newly written
checkpoint/upgrade/acceptance paths while the live operator prepares Flux pins.
Resolve material findings before the first k3s service pause/binary promotion;
this review is not a second live mutator or a new general permission request.

### Independent review findings before first pause

Read-only reviewer identified two material control-flow issues (not observed
production failures). Live operator was instructed to fix/test both and hand
back for re-review **before any k3s service pause/binary promotion**:

1. Synchronous checkpoint copy/service start/restart could bypass the intended
   readiness deadlines by waiting indefinitely; controller-side restart cleanup
   cannot run if SSH is lost. Add bounded capture/service operations and an
   Ansible-managed host-local safeguard to restart the unchanged checkpoint
   binary. Verify/cancel that safeguard before any new binary promotion; never
   use it as a binary-only cross-minor rollback.
2. Plex GPU probe could report success while its own stream cleanup failed.
   Require verified owned-session termination in both helper success and Ansible
   acceptance. Never terminate unrelated streams.

Current-version pins may proceed while these code fixes are made. Passing fixture
tests alone does not establish production timeout/unreachable recovery; record
the code fixes, negative tests and bounded end-to-end acceptance separately.

### Isolation completed; re-review requested

Sole operator handed back after approved Flux commits `fc10bcc`, `8715c31`,
`f5358ec`, `5ec9996`, `00dd898`, `c9050a9`: current chart/image pins, including
init/sidecar and Tailscale operator/proxy images. Render review reports no
non-image PodSpec changes. Guard now reports **zero unpinned Always references /
zero broad chart constraints**, with 59 pods / 43 Flux resources / seven PVCs /
22 ingress routes healthy and accepted image digests unchanged.

ImageUpdateAutomation `flux-system/apps` is temporarily suspended by GitOps;
restore its recorded prior state after Kubernetes acceptance. Original Flux
checkout/unrelated work was preserved using a clean detached worktree.

Both reviewer findings have implementation/test fixes (58 tests total), but no
service pause/checkpoint/promotion has occurred. A fresh `k3s_code_review_cleared`
gate remains false pending independent re-review. At owner request, the live
operator and reviewer models are now **DeepSeek V4.1 Flash via OpenRouter**.
No background host mutator is active during re-review; actual k3s is 1.33.11.

Independent re-review returned **YES**, 58 tests pass, no remaining material
finding. Coordinator explicitly cleared the sole operator to run each authorized
hop with `-e k3s_code_review_cleared=true`, preserving the false default. Live
checkpoint/service/timer/crypto deadlines remain unrehearsed until actually run;
any failure must stop progression rather than waive a gate. Operator has resumed
through Ansible; no completed hop is claimed in this coordination record yet.
Restore recorded temporary image-automation state after final acceptance without
undoing immutable pins; retain/describe any unsafe restoration blocker honestly.

## Verified release recommendation

Official release/channel/checksum metadata researched as of 2026-10-09;
see `docs/k3s-version-research-2026-10-09.md` for exact sources and publication dates.

| Stage | Exact K3s pin | Role |
| --- | --- | --- |
| Current | v1.33.11+k3s1 | Installed, upstream minor EOL |
| Preparatory patch | v1.33.13+k3s2 | Recommended, optional extra restart/checkpoint |
| First minor | v1.34.12+k3s1 | Transit only; Kubernetes EOL 2026-10-27 |
| Second minor | v1.35.9+k3s1 | Transit; Kubernetes EOL 2027-02-28 |
| Target | v1.36.5+k3s1 | Observed K3s stable; Kubernetes EOL 2027-06-28 |

1.37.1+k3s1 is published/current latest, but adds another hop and is not the
recommended target for this change. Recheck exact versions/checksums at execution
time, not blindly use floating stable/latest channels.

### Dependency/runtime gates to resolve before execution

- **Ingress:** retired ingress-nginx is not automatically incapable of running,
  but its documented tested Kubernetes ranges end at 1.33/1.34/1.35 depending
  on controller branch, and none lists 1.36. After the live version audit, plan a
  separately approved maintained replacement **before crossing its tested range**,
  unless the owner deliberately accepts an untested-version exception. Do not
  claim an unproven hard runtime incompatibility.
- **Startup configuration:** audit explicit removed kubelet flags/feature gates,
  notably `DevicePluginCDIDevices` at 1.34 and `--pod-infra-container-image` at
  1.35. The host's existing cgroup v2 satisfies 1.35's default startup requirement.
- **Runtime:** selected 1.36 introduces containerd 2.2 → 2.3. Preserve existing
  config templates; exact K3s 1.36.5 still renders containerd config version 3,
  so no speculative v4-template migration. Validate actual fresh pull/start and
  GPU allocation, not just containers that survived the daemon restart.
- **Recovery:** preserve the consistent whole SQLite DB directory and matching
  token/binary/configuration; rollback across minors requires datastore restore.
  This remains separate from application/PVC backup consistency.
- **Observation:** allow 30–60 minutes per hop and several controller cycles,
  rather than equating one Ready snapshot to acceptance; 24–48 hours final normal
  usage is recommended. These are planning windows, not guaranteed downtime.

## Fresh live audit findings

Read-only audit: `docs/k3s-upgrade-preflight-2026-10-09.md`.

- **59/59 active pods Ready, 43/43 Flux resources Ready, 7/7 PVCs Bound**.
- Same k3s/SQLite/bundled runtime and disabled Traefik/ServiceLB; no custom
  containerd templates or observed automatic k3s upgrade controller.
- 52 CRDs established, no observed stored-version migration backlog, webhook
  endpoints Ready. This does not prove every target-minor/controller combination.
- Actual ingress-nginx **1.15.1 / chart 4.15.1**, Flux **2.8.6**, MetalLB **0.14.9**,
  cert-manager **1.21.2**, Tailscale **1.102.4**, CNPG **1.30.1 / chart 0.29.1**.
  Chart minima alone are not supported-version matrices; follow-up official
  release-specific support check is required before final prerequisite ordering.
- **Upgrade isolation gate:** Flux image automation and broad chart ranges are
  active. Sonarr/Radarr and other apps use mutable images with `Always`. Recreated
  pods can fetch new code while manifest image specifications appear unchanged.
  Plan separately approved temporary automation controls and immutable image /
  chart pins where needed; do not silently disable everything or globally mutate
  app settings. Compare actual digests and application versions before/after.
- Sonarr/Radarr prompts on `sonarr.suetens.cc` / `radarr.suetens.cc` were traced
  to reboot-triggered mutable-image updates and changed app proxy-trust behavior.
  Do not attribute them to k3s: no k3s upgrade has run. See the diagnosis and
  separately approved repair scope below.

## Controller support and final proposed order

Official evidence appended to the preflight document:

| Component currently installed | Target-minor support evidence |
| --- | --- |
| Flux 2.8.6 | Exact tests through 1.35; 1.36 testing not established |
| ingress-nginx 1.15.1 | Tested 1.31–1.35; no listed 1.36 testing |
| cert-manager 1.21.2 | Supported/tested 1.33–1.36 |
| CNPG 1.30.1 | Supported 1.34–1.36 |
| external-dns 0.23.0 | Compatibility covers ≥1.33 |
| MetalLB 0.14.9 / Tailscale 1.102.4 | Exact target-minor matrices unverified; no proven incompatibility |
| Intel GPU plugin 0.37.1 | Newer-plugin/older-Kubernetes policy supports retaining it |

No mandatory removed-API/CRD migration blocker was demonstrated for the unchanged
controllers. This does not turn unverified combinations into certified support.

**Recommended staged order:**

1. Resolve the Sonarr/Radarr user-facing auth regression and record an accepted
   actual-image baseline. Approve drift controls: suspend relevant image updates,
   pin chart versions and lock mutable images to accepted digests. Digest pinning
   itself can roll workloads and needs explicit approval; suspending Flux image
   automation alone does not stop `latest`/Always from pulling different code.
2. Optional 1.33 patch, then **1.34.12 → 1.35.9**, each with independent recovery
   checkpoint, acceptance and observation. These hops are conditionally compatible;
   no execution before owner approval, auth baseline and drift controls.
3. Pause on supported 1.35. Plan separately approved ingress migration before
   1.36. **Envoy Gateway 1.9** explicitly tests 1.33–1.36, allowing staging without
   a circular Kubernetes prerequisite; exact plugin/Gateway API release pins and
   route/annotation/certificate migration are a separate plan. Standalone Traefik
   is another candidate, but exact target-minor testing was not established.
4. Separately review/pin **Flux 2.9.x** for its explicit 1.36 coverage. It removes
   image/notification v1beta2 APIs; observed manifests/stored versions already
   use successors, but verify the actual rollout/CRD migration before proceeding.
5. Finish **1.36.5**, validate runtime 2.3/new sandbox/image pull/GPU/networking,
   then observe normal use. No automatic 1.37 or app/security follow-on.

Retired ingress replacement and Flux updates are **not silently authorized** by
the current planning request. Reaching 1.35 first is a deliberate intermediate
milestone, not permission to ignore its February 2027 support deadline.

### Confirmed Sonarr/Radarr regression

`docs/arr-auth-diagnosis-2026-10-09.md` confirms first OS reboot pulled new app
code through mutable `latest` tags: Sonarr **4.0.17.2952 → 4.0.20.3014**, Radarr
**6.1.1.10360 → 6.4.4.10685**. Password/auth settings unchanged; new proxy-trust
rules prevent the existing LAN UI bypass when nginx forwarding headers arrive.
Current runtime/image drift is therefore a proven risk, not just hypothetical.
Owner chose passwordless **LAN and their Tailscale devices**, confirmed no public
exposure, and separately approved deployment of current app image/chart pins,
shared nginx `externalTrafficPolicy: Local` and narrow proxy trust. The dedicated
repair agent deployed and validated that limited GitOps fix through commits
`109aa59` and `2d922f7`. LAN roots now return 200; protected APIs remain 401 and
controlled public-source UI tests remain Basic 401 / Forms login redirect.
All 22 ingress routes and 59 pods / 43 Flux resources remain healthy. Existing
Basic/Forms, credentials, app versions and actual imageIDs are unchanged.
See `docs/arr-private-access-fix-2026-10-09.md`; real off-Wi-Fi phone/Tailscale
access remains an owner check. Proxy trust is deliberately `/32` and fails closed
if ingress is rescheduled to another IP: include re-verification in each hop's
acceptance, and obtain approval for any required override update. Other mutable
apps/chart automation still require separate drift controls before k3s execution.
