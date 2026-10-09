# K3s version research — 2026-10-09

Read-only public documentation/API research for the parent upgrade planner. No SSH, cluster operations, backups, deployment, existing-file changes, or Git operations were performed. This new research document is the only authored file. Host/controller facts supplied by the parent are assumptions, not independently audited here.

## Recommendation and verified publication evidence

Recommend **`v1.36.5+k3s1`**, conditional on the live controller compatibility audit and separately approved prerequisites. It is the actual K3s `stable` channel value observed, whereas `latest` is `v1.37.1+k3s1`. Pin versions; do not install from floating channels. Kubernetes 1.36 has five patch releases and roughly five months of upstream history, versus the newly released 1.37 branch. It offers substantially more remaining upstream support than 1.35 without adding another minor hop.

Preferred ladder:

`v1.33.11+k3s1 → v1.33.13+k3s2 → v1.34.12+k3s1 → v1.35.9+k3s1 → v1.36.5+k3s1`

The same-minor first hop follows Kubernetes' optional recommendation to update the current branch to its most recent patch before a minor upgrade. It is **not mandatory**: `v1.33.11+k3s1 → v1.34.12+k3s1` does not skip a minor and is permissible under the documented upgrade order. Omitting the patch-only stop trades away preparatory fixes for one fewer service restart/backup/acceptance cycle; make that an explicit planning decision. Never jump directly from 1.33 to 1.35/1.36.

| Minor | Newest published non-prerelease K3s tag verified | GitHub `published_at` (UTC) | Upstream Kubernetes lifecycle on research date | Planned role |
|---|---|---|---|---|
| 1.33 | `v1.33.13+k3s2` | 2026-08-04T19:40:10Z | EOL 2026-06-28 | Optional preparatory patch, not destination |
| 1.34 | `v1.34.12+k3s1` | 2026-09-30T16:09:32Z | Maintenance since 2026-08-27; EOL 2026-10-27 | Transit only |
| 1.35 | `v1.35.9+k3s1` | 2026-09-30T16:09:21Z | Maintenance starts 2026-12-28; EOL 2027-02-28 | Transit or explicitly approved interim destination |
| 1.36 | `v1.36.5+k3s1` | 2026-09-30T16:10:03Z | Maintenance starts 2027-04-28; EOL 2027-06-28 | Conservative target; observed K3s `stable` |
| 1.37 | `v1.37.1+k3s1` | 2026-09-30T16:10:38Z | Maintenance starts 2027-08-28; EOL 2027-10-28 | Available, but not recommended for this change |

These are **upstream Kubernetes dates**, not a promised separate SUSE/Rancher commercial support contract. Published K3s builds can exist after upstream Kubernetes EOL; their existence does not extend upstream support.

Evidence was fetched on **2026-10-09**, approximately **09:39–09:42 UTC**. The GitHub HTTP `Date` for the exact-tag/checksum fetch was **Fri, 09 Oct 2026 09:40:32 GMT**. Each exact release returned HTTP 200, `draft=false`, `prerelease=false`. The newest-per-minor results from the releases listing agree with the channel API and K3s release-note tables. These dates/tags are observed public responses, not extrapolated future numbers. Kubernetes' scheduled October 13 patches are not published K3s upgrade pins as of this research.

### Exact release and checksum sources

| Tag | Official release | Published amd64 `k3s` SHA-256 |
|---|---|---|
| `v1.33.13+k3s2` | https://github.com/k3s-io/k3s/releases/tag/v1.33.13%2Bk3s2 | `1572f0f23bd5a844bd405b71875877aacacc7ab79e279d3d73735654c37c7735` |
| `v1.34.12+k3s1` | https://github.com/k3s-io/k3s/releases/tag/v1.34.12%2Bk3s1 | `ef1df26b26276c0f6d962391c94e12f9362d1f1e30ec7a7926e9ddb84b0d66ce` |
| `v1.35.9+k3s1` | https://github.com/k3s-io/k3s/releases/tag/v1.35.9%2Bk3s1 | `897acb21cca57d477a211102251a6591450ce767344a9faaa121a1007ca9fa9a` |
| `v1.36.5+k3s1` | https://github.com/k3s-io/k3s/releases/tag/v1.36.5%2Bk3s1 | `d73847bcd3c5fccef0115b372e2f9a91f3032dc84bbf71518a4617565294d313` |
| `v1.37.1+k3s1` | https://github.com/k3s-io/k3s/releases/tag/v1.37.1%2Bk3s1 | `92b94582eb7b34a8cf532e6006842b9ed215a6783cf56a3dd6271fd35243b2c0` |

For each tag, the exact API URL is `https://api.github.com/repos/k3s-io/k3s/releases/tags/<URL-encoded-tag>` and the checksum URL is `https://github.com/k3s-io/k3s/releases/download/<URL-encoded-tag>/sha256sum-amd64.txt`. All five checksum text files were fetched successfully; their `k3s` entries were valid 64-character hex digests and agreed with GitHub asset `digest` fields. This verifies **published checksum metadata**, not a locally downloaded binary: no binary was downloaded or executed. At execution time, verify the actual architecture-specific binary against its release checksum again.

Discovery sources:

- https://api.github.com/repos/k3s-io/k3s/releases?per_page=100
- https://update.k3s.io/v1-release/channels (HTTP Date 2026-10-09 09:39:57 GMT)
- https://kubernetes.io/releases/
- https://kubernetes.io/releases/patch-releases/
- https://docs.k3s.io/release-notes/v1.34.X
- https://docs.k3s.io/release-notes/v1.35.X
- https://docs.k3s.io/release-notes/v1.36.X
- https://docs.k3s.io/release-notes/v1.37.X

## Skew, service interruption, and installation preservation

Official K3s manual upgrades explicitly prohibit skipping intermediate Kubernetes minors, require servers before agents, and support either installer re-run or binary replacement. Kubernetes explicitly requires sequential apiserver upgrades **even for single-instance clusters**. K3s upgrades its bundled components together; do not try to replace the bundled kubelet/containerd independently.

- Kubelet/kube-proxy cannot be newer than the apiserver; current versions allow them up to three minors older. This is **not permission to skip control-plane minors**.
- Controller-manager/scheduler/cloud-controller-manager should match the apiserver and may be at most one minor older during upgrades.
- `kubectl` is supported within one minor either side of the apiserver. Prefer the target's bundled `k3s kubectl` for acceptance; a workstation kubectl pinned at 1.33 becomes outside supported skew at 1.35. Other controllers have their own support matrices; do not equate kubectl skew to controller compatibility.
- General Kubernetes skew documentation says to drain before a kubelet minor upgrade. K3s-specific manual upgrade documentation says containers continue running with K3s stopped and it is generally safe to restart without drain/cordon. Record this distinction rather than claiming all upstream tooling universally supports in-place kubelet upgrades. For this one-node cluster, draining means application downtime with no other scheduling destination and may hit PDB/local-storage constraints. Choose the documented K3s path and interruption policy explicitly; do not hide a forced drain inside the procedure.
- A K3s service upgrade normally needs **no Ubuntu host reboot**. The one API server is unavailable while stopped/restarting, scheduling and reconciliation pause, and application/container interruptions are possible. Continuing existing containers does not guarantee zero application downtime or validate that newly created containers work.
- Allow a maintenance window measured in minutes, not a guaranteed three-second restart. An operational estimate is tens of seconds to several minutes for API/runtime recovery **after service start**, plus however long deliberate backup/offhost transfer and workload recovery take. No measured duration is available from this research. A 30–60 minute per-hop window is a planning allowance, not a downtime guarantee.

Prefer the official **binary-only upgrade path** to avoid rewriting the already recovered systemd service: download the exact tag's binary, verify SHA-256, retain the old exact binary, replace the actual service binary using an appropriate staged/atomic installation procedure, and restart the existing service. This describes future approved execution only.

If using the installer instead, explicitly pin `INSTALL_K3S_VERSION` and reproduce **all** existing `INSTALL_K3S_EXEC`, `K3S_*` environment values and trailing arguments. K3s warns that omitted values are lost when the unit/environment file is regenerated. Preserve `server`, `--disable=traefik`, `--disable=servicelb`, data-dir, node/network/DNS/TLS/registry/encryption settings, service environment/drop-ins, and anything else found by the separate audit; do not assume the three known flags are the complete configuration. `/etc/rancher/k3s/config.yaml` is not managed by the installer, but migration of flags to that file is a separate change and must not be bundled casually.

Sources (retrieved 2026-10-09; K3s pages report last updated 2026-10-07):

- https://docs.k3s.io/upgrades/manual
- https://kubernetes.io/releases/version-skew-policy/
- https://docs.k3s.io/advanced#configuring-containerd

## Runtime and minor-change review

### Pinned runtime transitions

| K3s pin | Embedded containerd | Embedded runc | Kine / SQLite | Flannel |
|---|---|---|---|---|
| Installed `v1.33.11+k3s1` release metadata | `v2.2.3-k3s1.33` | `v1.4.2` | `v0.14.16` / 3.51.3 | `v0.28.4` |
| `v1.33.13+k3s2` | `v2.2.5-k3s1.33` | `v1.4.2` | `v0.16.3` / 3.53.2 | `v0.28.4` |
| `v1.34.12+k3s1` | `v2.2.7-k3s1` | `v1.4.2` | `v0.16.5` / 3.53.4 | `v0.28.4` |
| `v1.35.9+k3s1` | `v2.2.7-k3s1` | `v1.4.2` | `v0.16.5` / 3.53.4 | `v0.28.4` |
| `v1.36.5+k3s1` | `v2.3.4-k3s1.36` | `v1.4.2` | `v0.16.5` / 3.53.4 | `v0.28.4` |
| Optional `v1.37.1+k3s1` | `v2.3.4-k3s1` | `v1.4.2` | `v0.17.1` / 3.53.4 | `v0.28.4` |

The notable runtime minor transition is **containerd 2.2 → 2.3 at the 1.36 hop**, not 1.x → 2.x (already completed), and not a new runc major/minor at these pins. Sources are the embedded-component tables in exact GitHub releases and official K3s release-note tables. The September backport bullet lists mention Kine 0.17.1 / etcd 3.7.1 even on branches whose embedded tables still say Kine 0.16.5 / etcd 3.6.14; that is a documentation inconsistency. Use actual installed component reporting for final verification; do not infer a SQLite-to-etcd conversion from those bullets.

K3s renders containerd configuration under the actual data-dir's `agent/etc/containerd/`. Existing `config-v3.toml.tmpl` and legacy `config.toml.tmpl` must be audited, not replaced with copied generated TOML. K3s documents v3 templates and legacy-v2 compatibility. Its **exact v1.36.5 source still renders `version = 3`**, even though upstream containerd 2.3 introduces configuration v4 and automatically migrates prior configuration on load. Do **not** require a speculative `config-v4.toml.tmpl` migration or manually upgrade config to v4 during this change; that would narrow rollback compatibility. Preserve templates, registry authentication/mirror configuration, `SystemdCgroup`, runtime classes and any CDI configuration.

Containerd 2.3's documented breaking concerns include old NRI plugin protocol and OCI-hook owner names containing commas. Containerd 2.3.4 disables experimental checkpoint restore through CRI CreateContainer by default. These are conditional audit items, not evidence this Plex device-plugin deployment uses NRI/checkpointing. Deprecated registry settings/CNI `bin_dir`/`enable_cdi` have future removal targets (2.4), not an invented removal in 2.3. Test image pull and newly created sandboxes after 1.36.

Runtime sources, retrieved 2026-10-09:

- https://github.com/k3s-io/k3s/releases/tag/v1.33.11%2Bk3s1 (published 2026-04-27T22:21:29Z)
- https://github.com/k3s-io/k3s/blob/v1.36.5%2Bk3s1/pkg/agent/templates/templates.go
- https://github.com/containerd/containerd/blob/v2.3.4/RELEASES.md
- https://github.com/containerd/containerd/releases/tag/v2.3.0 (published 2026-04-30T19:35:05Z)
- https://docs.k3s.io/advanced#configuring-containerd

### Kubernetes 1.34

- Removed kubelet `--cloud-config` and `--register-schedulable`; explicitly configured obsolete flags would be startup blockers.
- Static Pods referencing API resources are rejected by the kubelet. K3s does not use kubeadm's static control-plane pod deployment, but user static workloads still require review.
- `KubeletCgroupDriverFromCRI` graduates to GA; containerd 2.x provides RuntimeConfig RPC. The supplied cgroup v2/SystemdCgroup state is compatible; preserve it.
- DRA core reaches GA (`resource.k8s.io/v1`); old resource alpha APIs and kubelet DRA v1alpha4 RPC are removed. DRA admin-access label changes. These concern DRA claims/drivers, not automatic removal of ordinary Device Plugin resource requests.
- **`DevicePluginCDIDevices` feature gate is removed because the functionality is GA**, not because CDI is removed. An explicitly retained gate argument must be removed separately before this hop.
- `MultiCIDRServiceAllocator` is locked on and `DisableAllocatorDualWrite` enabled by default. Service allocator storage changes reinforce the requirement for a pre-hop datastore rollback point. API-server metric labels also change; compare dashboards/alerts rather than only process health.

### Kubernetes 1.35

- `failCgroupV1` defaults true: kubelet refuses cgroup v1 by default. The supplied Ubuntu 24.04/kernel 6.8/cgroup v2/SystemdCgroup baseline already meets this gate. This is a default refusal with a temporary override, not a claim every fallback has already been deleted.
- **Removed kubelet `--pod-infra-container-image`**; a custom `kubelet-arg` passing it is a hard startup blocker. K3s `--pause-image` is a different setting and must not be removed by name confusion.
- Feature-gate dependencies validated at startup; explicit incompatible `AllAlpha`/disabled dependency combinations can prevent startup. DRA core is locked on. Removed StrictCostEnforcement gate overrides must not remain in custom arguments.
- `storagemigration.k8s.io/v1alpha1` removed for v1beta1; old alpha resources need migration/removal only if used. Alpha partitionable DRA ResourceSlices change incompatibly across 1.34/1.35.
- `KubeletEnsureSecretPulledImages` beta defaults on: verify private-registry credentials and an actual new pull/start; cached running images alone are insufficient evidence.
- IPVS proxy mode is deprecated, **not removed**; it does not require conversion of an existing iptables setup. In-place resize is stable, but enabling/changing app resources is not part of this upgrade.

### Kubernetes 1.36

- `StrictIPCIDRValidation` defaults on: review noncanonical/leading-zero IPs and CIDRs in manifests before writes/reconciliation. This is more relevant than assuming Ubuntu's iptables-nft frontend is itself incompatible.
- `.spec.externalIPs` on Services is **deprecated with warnings, not removed at 1.36**. Official migration guidance puts disablement at 1.40 at the earliest and complete removal at 1.43 at the earliest. Do not confuse it with Node ExternalIP addresses or the EXTERNAL-IP display of a LoadBalancer Service.
- DRA granular ResourceClaim-status authorization becomes beta: DRA controllers/drivers need binding/driver-specific RBAC if used. Existing conventional Intel Device Plugin extended-resource requests are not automatically converted to DRA.
- MutatingAdmissionPolicy reaches v1 GA/enabled default; old alpha Workload scheduling API and WebhookAdmissionConfiguration are removed, and in-tree Portworx removed. These are conditional blockers only where actually configured. Local-path storage is not Portworx.
- Volume error and etcd bookmark metrics renamed; removed legacy metrics/gate overrides require monitoring/config review. Pod-level in-place resize beta is enabled, while MemoryQoS remains alpha in 1.36; do not enable it during this change.
- No documented requirement was found to change the Flannel backend, iptables alternatives, host kernel, or ingress API solely to make 1.36 start. Preserve the audited network configuration and validate DNS, Service/ClusterIP, NodePort/external exposure, ingress, network policy and PVC access after every hop.

### Candidate Kubernetes 1.37 — researched, defer

- SELinuxMount GA/on can break conflicting volume sharing **on SELinux-enabled clusters**; ordinary Ubuntu AppArmor is not synonymous with SELinux.
- `scheduling.k8s.io/v1alpha2` removed for v1alpha3; old alpha objects require cleanup/migration if used.
- Kubelet `eventRecordQPS: 0` now really means unlimited; effective kubelet config is logged (restrict node-log access).
- Many old cAdvisor flags removed; a custom obsolete flag becomes a kubelet startup blocker. More GA feature-gate overrides disappear.
- Proxy mode should be explicitly configured ahead of a future default transition; **iptables is still the default in 1.37**, not already forcibly replaced by nftables.
- This adds another hop, newer release/default behavior and controller uncertainty without being needed to reach a maintained stable-channel destination.

Exact upstream change sources (retrieved 2026-10-09, HTTP 200; inspect each minor's v1.x.0 urgent notes and full change list, plus intervening patches):

- https://github.com/kubernetes/kubernetes/blob/master/CHANGELOG/CHANGELOG-1.34.md#v1340
- https://github.com/kubernetes/kubernetes/blob/master/CHANGELOG/CHANGELOG-1.35.md#v1350
- https://github.com/kubernetes/kubernetes/blob/master/CHANGELOG/CHANGELOG-1.36.md#v1360
- https://github.com/kubernetes/kubernetes/blob/master/CHANGELOG/CHANGELOG-1.37.md#v1370
- https://kubernetes.io/blog/2026/05/14/kubernetes-v1-36-deprecation-and-removal-of-service-externalips/ (published 2026-05-14)
- https://kubernetes.io/blog/2026/10/06/kubernetes-cgroups-v2-shift/ (published 2026-10-06; its prose still calls 1.36 current, so use releases/API evidence for current release state)
- https://docs.k3s.io/known-issues (old iptables versions 1.8.0–1.8.4 flagged; not proof this Ubuntu host is affected)

## Ingress and Intel GPU compatibility gates

### ingress-nginx

Official retirement notice, published **2025-11-11**, says best-effort maintenance ends March 2026, no further fixes/security updates, and **existing deployments continue functioning**. This is a serious security/lifecycle issue, not a binary runtime stop-date.

The official project README's E2E-tested compatibility table, retrieved 2026-10-09, lists:

| ingress-nginx series | Kubernetes versions listed | Consequence for this ladder |
|---|---|---|
| 1.13.x (through 1.13.9) | 1.29–1.33 | 1.34 is outside documented tested range |
| 1.14.x (through 1.14.5) | 1.30–1.34 | 1.34 within range; 1.35 outside |
| 1.15.x (through 1.15.1) | 1.31–1.35 | 1.34/1.35 within range; 1.36 outside |

**No table entry supports 1.36 or 1.37.** Await the audit agent's exact deployed controller/image/chart version; do not infer it from the current Kubernetes version.

- Replacement need not precede the 1.33 patch or first minor hop solely because of March retirement. If the deployed version is in the next hop's listed range and an explicit short-lived security-risk decision is made, migration can be a separate follow-up within that range.
- For a conservative **documented-support-only** plan, a supported ingress replacement must be separately approved and completed **before the first hop outside that deployed controller's range**, and in any case before 1.36 with ingress-nginx. An approved controller update to another retired version may extend the tested range, but is still a separate change and does not make the project maintained.
- An outside-range controller may function; this research has **not proved a hard API incompatibility** or proved it safe. Proceeding without replacement is an untested-version exception requiring explicit approval and rehearsal/route/webhook testing, not an unconditional green gate.
- K3s bundled Traefik chart-v40 provider-name warning is irrelevant while Traefik remains disabled. It becomes relevant if a separately approved migration chooses that integration. Do not re-enable Traefik as a hidden side effect of the K3s installer.

Sources:

- https://kubernetes.io/blog/2025/11/11/ingress-nginx-retirement/
- https://github.com/kubernetes/ingress-nginx/blob/main/README.md
- https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/README.md

### Intel GPU

The **exact v0.37.1** Intel Device Plugin README lists release-0.37 for Kubernetes 1.37, but explicitly explains newer device-plugin releases should work with older Kubernetes because of the stable Kubernetes v1 API, with operator CRDs a possible exception. This supports keeping the supplied working **0.37.1 GPU DaemonSet and Plex image/resource request unchanged**, rather than introducing another upgrade. It is not a complete empirical certification of this homelab's combination.

Its GPU README says containerd supports CDI since 1.7 and enables it by default since 2.0; Kubernetes device-plugin CDI support is default since 1.29. DRA GA does **not** compel replacing the traditional Device Plugin deployment. Preserve the working device allocation mode, `/dev/dri` access, cgroup driver and GPU request. Check registration/allocatable GPU count, pod allocation and actual sustained VAAPI transcode after every hop. A existing running container passing a transcode does not alone test post-upgrade container creation/device injection.

Sources, retrieved 2026-10-09 09:41:07 GMT:

- https://github.com/intel/intel-device-plugins-for-kubernetes/blob/v0.37.1/README.md
- https://github.com/intel/intel-device-plugins-for-kubernetes/blob/v0.37.1/cmd/gpu_plugin/README.md
- https://github.com/intel/intel-device-plugins-for-kubernetes/releases/tag/v0.37.1

## Consistent SQLite rollback points — future plan requirements

Official K3s backup guidance: copy the actual data-dir's **`server/db/` directory** and preserve **`server/token`**; the token encrypts confidential bootstrap data and must match the restored datastore. This cluster uses SQLite, so `k3s etcd-snapshot` is not its backup method. A running plain file copy of only `state.db` is not a sufficient consistency procedure.

For each separately approved hop:

1. Inventory/preserve the exact old binary/version, service/unit/drop-ins/environment, `/etc/rancher/k3s/` configs/kubeconfig/registries, containerd templates, and custom manifests. Preserve `server/tls/`, `server/cred/` including any encryption configuration/keys, token and relevant node identity material (including `/etc/rancher/node/` if present). Include independently protected SOPS/age/GPG decryption keys and GitOps bootstrap credentials; a Git repository alone does not recreate secrets. Never publish secrets in the plan or checksum report.
2. After stopping the K3s service, verify the server/Kine/SQLite writer has actually exited and no other server process accesses the datastore. Do **not** assume `systemctl stop k3s` stops application containers: official docs say they continue running. Avoid `k3s-killall.sh` for a mere datastore backup; it is much more disruptive.
3. While the datastore is quiescent, capture the **whole paired DB directory and token**, retaining any WAL/SHM/journal files as one consistent set rather than combining files copied at different times. Preserve ownership/modes. Do not delete WAL files or hand-edit the database. A properly coordinated SQLite online backup is an alternative, but should not be improvised for this maintenance.
4. Copy the protected backup off-host, verify archive/checksum/readability/completeness and that the recovery operator can access it before replacing the binary. Local-only backups cannot cover disk/host loss. An offline integrity test must operate on a backup copy, not mutate the live datastore.
5. Record version, capture time and restore pairing. Refresh the backup immediately before **each** hop so rollback returns to the preceding accepted version, rather than losing all changes since the initial 1.33 point.

K3s datastore backup restores Kubernetes state, **not application/PVC data**. Running applications can keep writing while K3s is stopped. If the chosen rollback promise includes app-data consistency, application-aware dumps/snapshots/quiescence and corresponding PV recovery are separate prerequisites needing approval. Do not label a K3s DB copy a consistent Plex/app-volume backup.

Official rollback guidance requires **binary downgrade plus datastore restoration**, with a pre-upgrade datastore copy from the minor being restored. **If the database cannot be restored, minor rollback is not available.** Never promise that putting the old binary over a migrated datastore is safe. Preserve matching token/config/TLS/encryption material and old runtime configuration; application shutdown/recovery must be explicit before any forceful cleanup. Containerd storage formats are not guaranteed downgrade-compatible by upstream; a Kubernetes SQLite backup alone is not evidence every migrated runtime state can be downgraded safely. Validate the rollback approach, avoid voluntary config-v4 conversion, and preserve/rehearse the runtime recovery option rather than inventing a supported binary-only downgrade.

Rollback loses Kubernetes changes after the snapshot and does not undo PVC writes; GitOps can reconcile again when restarted. Treat it as a recovery operation, not a casual reverse hop.

Sources (retrieved 2026-10-09; K3s pages last updated 2026-10-07):

- https://docs.k3s.io/datastore/backup-restore
- https://docs.k3s.io/upgrades/roll-back
- https://docs.k3s.io/upgrades/manual
- https://github.com/containerd/containerd/blob/v2.3.4/RELEASES.md#not-covered

## Acceptance, soak, and stop criteria for parent plan

These are **proposed operational criteria**, not a vendor-mandated soak interval or tests executed here.

Before each hop: compatible controller/chart ranges verified against the separate live audit; obsolete flags/gate/API use cleared; approved prerequisites complete; fresh verified off-host paired recovery point; exact artifact checked; no active recovery/backup/upgrade competing with this operation. Keep Flux/app/GPU controller versions and manifests fixed where compatible. Any prerequisite update, ingress replacement, feature-gate change or test deployment needs its own approval.

After each hop, require:

- Intended exact K3s and bundled runtime versions, unchanged disabled Traefik/ServiceLB/data-dir/other service settings, API readiness and node Ready without pressure conditions.
- All expected long-running workloads Ready; baseline 59 pods and 43 Flux resources used as a comparison, not an invariant raw count (completed Jobs/new bundled pods may change counts). No unexplained Pending/CrashLoop/ImagePull/sandbox/mount errors or continually rising restart/OOM counts.
- Flux sources/controllers/Kustomizations/HelmReleases Ready over multiple actual reconciliation cycles; no failing admission webhook or newly rejected resource/API/gate.
- DNS, ClusterIP and required external/NodePort/ingress HTTPS routes work, including authentication, uploads/WebSockets and certificate behavior where used; storage/PVC mounts and application reads/writes work.
- GPU plugin registers expected allocatable resources, Plex still requests/receives the GPU and its actual VAAPI pipeline/transcode completes under representative load. With approval, test a newly created or safely restarted GPU container as well as a surviving one to exercise the new runtime.
- Review service/runtime/kubelet/controller logs and events for datastore/TLS/CNI/RBAC/API/schema/metrics regressions; verify dashboards still monitor what matters.

Suggested pacing: **at least 30–60 minutes of stable observation per hop**, enough for multiple real reconciliation cycles and representative app/GPU/network activity; preferably stage minor hops on separate days when normal-use observation is feasible. Final target: **24–48 hours including a normal playback/transcode and scheduled-job cycle** before declaring the change fully accepted. Short intermediate checks are smoke tests only, not evidence of a full normal-use soak. Exact waits must reflect configured Flux intervals/CronJobs and operator availability.

Stop further hops on any unverified backup/checksum, config drift, unsupported prerequisite without approval, node/API instability, missing expected GPU, failed sustained transcode, Flux/webhook/API failures, PVC/app corruption or unexplained persistent network/restart regressions. Investigate at the current version first; if rollback is chosen, execute the approved matching-binary/consistent-DB/token recovery, not an improvised downgrade. If ingress cannot yet meet the 1.36 documented-support gate, 1.35 is an explicitly temporary, maintained holding point with EOL 2027-02-28—not permission to declare the full 1.36 goal complete.
