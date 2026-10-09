# k3s upgrade preflight — 2026-10-09

**Read-only planning audit; no upgrade authorized or performed here.** Checks
against ryback ran **09:38:48–09:44:20 UTC**, after completed Noble acceptance.
Only this new local document was written. No host files/status, packages,
services, workloads, backups, GitOps files, commits or pushes were changed.
No subagents or recovery jobs were created. Existing unrelated work in both
checkouts remains untouched.

## Outcome and gates for the coordinator

- Current cluster is healthy: **one Ready node, 59/59 active pods Ready,
  37/37 HelmReleases and 6/6 Kustomizations Ready, 7/7 PVCs Bound**; `/readyz`
  returns `ok`. There are 61 total pods, including two completed job pods.
- No observed live API/storage migration defect prevents preparing the first
  minor hop. This is **not** certification for Kubernetes 1.34/1.35/1.36.
  Exact patches, supported destination and controller support matrices remain
  the separate version/lifecycle research agent's responsibility.
- **Important isolation gap:** Flux chart upgrades and image automation are
  active, and several applications use `latest` with `imagePullPolicy: Always`.
  A runtime/container restart can therefore introduce application changes even
  with unchanged manifest image strings. Agree and authorize a narrow GitOps
  maintenance/drift-control method before promising a k3s-only change.
- Existing ingress-nginx retirement is an independent maintenance/security
  concern. Its healthy current admission endpoint and permissive chart minimum
  do not prove support for the chosen target. Get release-specific evidence;
  where absent, use a separately approved ingress/controller change window
  before the unsupported hop, not an implicit replacement during k3s upgrade.
- Execution still needs explicit authorization, a fresh verified consistent
  **matching SQLite/token/binary/config checkpoint before each hop**, reviewed
  rollback procedure and acceptance/stop deadlines. None was started here.

## Evidence sources and limits

Read `upgrade-execution-2026-10-09.md`, `ubuntu-24-upgrade-2026-10-09.md`,
`update-plan.md`, `recovery-runbook.md`; also the Flux checkout's `AGENTS.md`,
`CLAUDE.md`, task index and `docs/tasks/recovery-checkpoints.md`.

Live evidence used existing key-authenticated SSH to **192.168.1.110** and
`sudo -n`: service/config metadata, selected safe configuration fields,
Kubernetes GET/list/discovery/configz/metrics and controller image/status fields.
Packaged chart `Chart.yaml` and template API tokens were inspected in memory
from the **existing source-controller artifacts**, without extraction or writes.
No remote exec inside pods, new DNS probe workload, raw Secrets/ConfigMaps,
Helm values dumps, token contents, kubeconfig contents or OAuth contents were
displayed. Credential files were inspected by metadata only. No official web
version/lifecycle research was duplicated.

Current DNS/TLS/HTTPS and real GPU functionality are established by the earlier
dated Noble acceptance record, not repeated functional tests in this audit.
This audit reconfirmed ready DNS/webhook endpoints, certificates and allocation.

## Installation and configuration to preserve

| Item | Live evidence |
| --- | --- |
| k3s | **v1.33.11+k3s1**, commit `c532325b`, Go `go1.25.9` |
| Executable | `/usr/local/bin/k3s`, root-owned 0755, **78,205,112 bytes**; not owned by dpkg |
| Binary SHA-256 | `4b9201557bdca116d5d26ed70a38698e2667ac15655efe73f802119af80285fd` |
| Unit | `/etc/systemd/system/k3s.service`, enabled/active, no drop-ins |
| Exact safe ExecStart | `/usr/local/bin/k3s server --data-dir /var/lib/rancher/k3s --disable=servicelb --disable=traefik` |
| Unit behavior | `Type=notify`, `KillMode=process`, `Delegate=yes`, `Restart=always`, `RestartSec=5s`, `TimeoutStartSec=0` |
| Installer layout | `k3s-install.sh`, `k3s-killall.sh`, `k3s-uninstall.sh` present; saved installer contains normal `INSTALL_K3S_EXEC`, version, skip-start and service-generation mechanisms |
| Environment | Unit references optional `/etc/default/%N`, `/etc/sysconfig/%N`, `/etc/systemd/system/k3s.service.env`; first two k3s files absent, service env file root-owned 0600 and **empty** |
| Additional configuration | `/etc/rancher/k3s/config.yaml` and `config.yaml.d` absent |
| Kubelet configuration | Only `/var/lib/rancher/k3s/agent/etc/kubelet.conf.d/00-k3s-defaults.conf`; no custom additional file observed |
| Containerd templates | Neither `config.toml.tmpl` nor `config-v3.toml.tmpl` exists |

The installation is consistent with the standard binary/installer layout; the
historical installer invocation itself was not recovered. `/proc` command title
is rewritten to `k3s server`; exact options above came from the installed unit,
not a misleading process-title reconstruction. No other ExecStart flag names
were present.

**Future method recommendation, not an execution command:** select a verified,
exact amd64 release binary and use the documented manual-binary upgrade method
with the existing unit/config retained. If choosing the installer instead,
review/pin it and explicitly preserve all existing server arguments; it generates
service configuration, so a generic/default invocation must not re-enable
Traefik or ServiceLB. Preserve/review unit helper files and enabled state as
part of the checkpoint. Do not invoke uninstall/killall as routine upgrade steps.

## Runtime, CNI and single-node interruption

- Actual OS **Ubuntu 24.04.5**, kernel **6.8.0-146-generic**, amd64; Noble boot ID
  `a4bc2e89-da1a-43a8-ad20-9fba8daac1f9`. Node has no taints or pressure conditions.
- Bundled runtime **containerd v2.2.3-k3s1.33** and **runc 1.4.2**
  (`v1.4.2-0-gc241c0b`, OCI spec 1.3.0, libseccomp 2.6.0).
  These are not the separate host Docker/containerd packages.
- Generated containerd config is **format 3**, `SystemdCgroup=true`.
  Live kubelet configz confirms **cgroupDriver=systemd**, **failSwapOn=false**,
  `memorySwap={}`, no explicit featureGates, runtime endpoint
  `unix:///run/k3s/containerd/containerd.sock` and static pod path
  `/var/lib/rancher/k3s/agent/pod-manifests`.
- Intentional **8 GiB host swap** remains; do not silently disable it or claim
  `failSwapOn=false` proves that pods use swap. Check target kubelet swap/default
  behavior and CRI/cgroup-driver changes for each exact hop. Unified cgroup v2
  was already functionally accepted after Noble; no second hardware audit needed.
- CNI is bundled **Flannel VXLAN**, not Calico/Cilium: `10-flannel.conflist`,
  backend `vxlan`, cluster pod network **10.42.0.0/16**, node **10.42.0.0/24**,
  IPv6 disabled; node public IP **192.168.1.110**.
  DNS **10.43.0.10**, domain `cluster.local`; service network was not separately
  re-derived here. Bundled Flannel/CNI library release numbers were not verified.
- Existing bundled manifest names are ccm, runtimes, rolebindings, local-storage,
  coredns and metrics-server; no Traefik or ServiceLB manifest observed.

Expect a **single-node control-plane interruption for each k3s restart**, not a
default full OS reboot. `KillMode=process` means stopping k3s is not equivalent
to stopping every application container or quiescing application databases.
Bundled runtime/CNI/CoreDNS/provisioner versions can change with the k3s release;
do not promise zero pod restarts. Device-plugin registration/socket recovery
and immutable image IDs need acceptance after each restart. Do not force a
drain/eviction without a separate single-node/local-storage assessment.

## Datastore, storage and recovery material

Live k3s has open descriptors to **SQLite `state.db`, `state.db-wal`,
`state.db-shm`**. At 09:39 UTC:

| Path under `/var/lib/rancher/k3s/server/` | Bytes | Metadata |
| --- | ---: | --- |
| `db/state.db` | 89,571,328 | root:root 0644 |
| `db/state.db-wal` | 78,395,392 | root:root 0644; changing live |
| `db/state.db-shm` | 163,840 | root:root 0644 |
| `token` | 86 | root:root **0600**, present; contents unread |

`server/db/etcd` exists but contains only a `name` entry at this directory level;
its existence and the installed EtcdSnapshotFile CRD **do not make this an etcd
cluster**. Do not use etcd-snapshot instructions or copy live SQLite sidecars as
the consistent recovery method. Size observations are not database integrity
checks. Use the reviewed stopped-service/SQLite-backup procedure when authorized.

There are **7 local-path PVs/PVCs**, all Bound, provisioner
`rancher.io/local-path`, `WaitForFirstConsumer`, reclaim policy **Delete**.
Paths are under `/var/lib/rancher/k3s/storage`; contents were not traversed.
Preserve all claim/PV UIDs and mappings; deleting/recreating claims is not upgrade
maintenance. Root has **672,775,655,424 bytes available** at 09:44 UTC.

| Claim | PVC UID |
| --- | --- |
| `foundryvtt/data-foundryvtt-0` | `9ee2dc2a-7f09-4440-a118-f6f540dd4256` |
| `foundryvtt-hans/data-foundryvtt-hans-0` | `111e90cc-4c35-49c3-af98-0fafbe97d1e9` |
| `foundryvtt-rogier/data-foundryvtt-rogier-0` | `3d8b616b-f4d2-45f6-850a-392f096607a9` |
| `homeassistant/homeassistant-home-assistant-cnpg-main-1` | `5cafa088-d15c-46d7-b704-bc8b5a713ffb` |
| `plex/pms-config-plex-plex-media-server-0` | `9b023257-f570-4fd0-bbb6-b37ac6e5aa6f` |
| `vikunja/vikunja-data` | `87d1bb26-70d7-4501-92e0-781ef643d3b2` |
| `vikunja/vikunja-database` | `d0fbff12-541b-4b8d-94c7-cc4b07149632` |

Other applications also use hostPath storage outside this claim inventory.
Preserve the already validated six UUID mounts, especially root
`badcfde0-9b10-4f96-8684-f2baba24b223` and media
`8bf25db0-ca04-4c96-b91e-07d3458f4021` at `/mnt/volume1`. A k3s datastore rollback
does not roll application files/databases back to the same time.

Root-only `/var/backups/homelab-upgrade` and `mcp-recovery` directories are 0700;
existing private recovery OAuth/process records are 0600/root-owned and present.
They were not read or altered. Existing encrypted Mac baseline/clean/pre-Noble
checkpoints are documented in the recovery records; none is a fresh per-hop
checkpoint. Keep the matching token privately encrypted, never in this report.
Do not restore retired `/etc/dockerconfigs/plex`, replace MCP registration/files
or treat deferred offline Foundry gameplay as a passed check.

## Actual controller and chart inventory

All listed running controllers are Ready. Chart minima below are **packaged Helm
metadata**, not an upstream support matrix or verified maximum Kubernetes version.

| Component | Live chart / running version | Packaged `kubeVersion` / target-specific follow-up |
| --- | --- | --- |
| Flux bootstrap | controller labels **v2.8.6**, static bootstrap deployments; no Flux Operator deployment/CRD observed | Verify Flux 2.8.6 support for every selected minor; no operator migration inferred |
| Flux helm-controller | **v1.5.4** | HelmRelease v2 |
| Flux source-controller | **v1.8.3** | Source CRDs v1 |
| Flux kustomize-controller | **v1.8.4** | Kustomization v1 |
| Flux notification-controller | **v1.8.4** | Notification v1/v1beta2/v1beta3 CRDs |
| Flux image controllers | automation **v1.1.2**, reflector **v1.1.1** | Automation objects stored at v1 |
| ingress-nginx | chart **4.15.1**, controller **v1.15.1**, digest `594ceea76b01c592858f803f9ff4d2cb40542cae2060410b2c95f75907d659e1` | `>=1.21.0-0`; retirement/support and target API behavior remain release-specific gates |
| MetalLB | chart/images **0.14.9**, FRR **9.1.0** | `>=1.19.0-0`; chart constrained to `0.14.x`, so no automatic newer-minor migration; verify controller/conversion support |
| cert-manager | chart and three images **v1.21.2** | `>=1.22.0-0`; verify actual supported Kubernetes range and webhook behavior |
| external-dns | chart **1.23.0**, image **v0.23.0** | No kubeVersion declared; EndpointSlice/Ingress and provider compatibility checks |
| Tailscale | chart/operator/proxies **1.102.4** | No kubeVersion declared; verify operator, CRDs and existing ingress/funnel behavior |
| CloudNativePG | chart **0.29.1**, operator **1.30.1** | `>=1.29.0-0`; support matrix/webhooks must be checked; do not combine database upgrade |
| Intel GPU plugin | standalone **v0.37.1** per approved provenance; digest `004641b2547d58f1eadce58473fa160ad71377de1eb588cf1f82832387bf3e33` | No operator chart/CRDs; check device-plugin API/registration and allocation after runtime restart |
| Sonarr/Radarr + generic apps | app-template **5.2.1**, common library **5.2.1** | Top chart `>=1.28.0-0`, **common `>=1.31.0-0`**; proposed 1.34+ meet declared minima, not runtime certification |
| Plex | pinned chart **1.9.0**, image **1.43.4.10903-e5521bd8c** | No kubeVersion declared; preserve request/limit `gpu.intel.com/i915: 1`, image and claim |
| Foundry x3 | chart **15.2.4** (chart appVersion 14.368.0, not proof of running core version) | No kubeVersion declared; no application migration in this unit |
| Vikunja | chart **2.4.0**, chart appVersion **2.7.0** | `>=1.19`, common library `>=1.22.0-0`; current constraint `*` is a drift risk |
| Bundled CoreDNS | **1.14.2** | Delivered by selected k3s release |
| Bundled local-path-provisioner | **v0.0.35** | Preserve existing volume mappings and policy |
| Bundled metrics-server | **v0.8.1** | Aggregated API available; verify after hop |

CNPG has **one instance**, `homeassistant-home-assistant-cnpg-main`,
`Cluster in healthy state`, readyInstances=1; image
`ghcr.io/cloudnative-pg/postgresql:18.3-system-trixie`. Do not infer HA from an
operator-managed database on this one node.

Sonarr image is `lscr.io/linuxserver/sonarr:latest`, current resolved SHA-256
`f247545d23ba8b233d6604575347e48a623fe6ad75dda02348bf81917f3b5c06`.
Radarr image is `lscr.io/linuxserver/radarr:latest`, current resolved SHA-256
`7dfd049e79c00b16fbc29c3f5d96a9e7b9e73a23930b4c5b3c4541d60b366814`.
Both pull **Always**; their actual application versions were not queried.
Plex resolves to SHA-256
`e0ab27395614a8e1a4fdf84c6bc60ac664915cfdde70c52d030c7728a1c48e14`.

## API/CRD and admission findings

**52 CRDs**, all Established; every CRD's `status.storedVersions` contains only
its currently served storage version. No old stored-version migration backlog
was observed. All aggregated APIServices are Available.

- Flux HelmRelease is **v2 only**; Kustomization and Source CRDs **v1**. Live
  releases/reconciliation use those APIs. Image CRDs serve v1 and v1beta2,
  store v1. Alerts/providers serve v1beta2/v1beta3, store v1beta3; receivers v1.
- cert-manager/ACME, CNPG, k3s addons/snapshot files and bundled helm.cattle.io
  CRDs serve/store **v1**.
- MetalLB CRDs mostly serve/store **v1beta1**. BGPPeer serves v1beta1/v1beta2,
  stores **v1beta2**, uses **Webhook conversion**. That custom beta version is
  not itself a removed Kubernetes built-in beta API. Preserve conversion service
  availability through any separately approved MetalLB upgrade.
- Tailscale and external-dns custom APIs serve/store **v1alpha1**. These are
  custom API versions, not evidence of Kubernetes removing them in the next hop.
- Built-in discovery used stable `apps/v1`, `batch/v1`, `networking.k8s.io/v1`,
  `policy/v1`, `autoscaling/v1`/`v2`, `admissionregistration.k8s.io/v1`,
  `apiextensions.k8s.io/v1`, `flowcontrol.apiserver.k8s.io/v1` and other stable
  core groups. The metrics aggregated API is `metrics.k8s.io/v1beta1`.
- Postboot `apiserver_requested_deprecated_apis` reports only core **Endpoints
  v1**, with **empty removed_release**. This short observation window is not a
  complete future-removal audit or historical client-usage inventory.
- Existing chart templates contain stable APIs plus optional/conditional legacy
  fallback and Gateway/monitoring/other integration APIs. Text occurrence of
  `policy/v1beta1`, `autoscaling/v2beta2` or optional Gateway APIs is **not proof
  of an active removed-API object**. Render selected charts for each target
  Kubernetes version, safely suppressing values/Secret output, before execution.
  App-template uses a library-driven API selector; do not conclude compatibility
  solely from the top-level chart minimum.

Admission uses **admissionReviewVersions=[v1]**. ingress-nginx validates
`networking.k8s.io/v1` Ingress CREATE/UPDATE with **failurePolicy=Fail**;
cert-manager and CNPG have Fail validating/mutating hooks; MetalLB has Fail
validating hooks. All four webhook service EndpointSlices currently have ready
endpoints. A bad controller/webhook can block Flux writes even while the API
server itself is Ready. A read-only endpoint check is not a TLS/admission
transaction test; no server-side dry-run write/admission probe was performed.

Current ingress inventory is **25 networking/v1 objects**: **22 nginx** and
**3 Tailscale Foundry**. Nginx LoadBalancer address remains **192.168.1.201**.
All **22 cert-manager Certificates** are Ready; nearest reported expiry is
2026-11-13. Earlier Noble DNS/TLS/HTTPS acceptance remains the functional baseline.

## Automation: distinguish k3s from application/package updates

- **No system-upgrade-controller workload** in the deployment/daemonset/statefulset
  inventory; **no `upgrade.cattle.io` API group/Plan CRD**. No k3s upgrade timer
  appeared in all-timer inventory. Passive small-file scans of cron directories,
  root/user crontabs and direct systemd unit files found no k3s upgrade scheduler
  references. This is scoped evidence, not proof against every possible external
  automation system or opaque script.
- k3s binary is not a dpkg package; Ubuntu apt timers do not upgrade that binary.
- **Ubuntu automatic package updates are enabled**, not absent:
  apt-daily and apt-daily-upgrade timers enabled/active from Noble acceptance,
  `APT::Periodic::Unattended-Upgrade "1"`, Ubuntu base/security/ESM origins.
  No active automatic reboot setting was found in apt config files inspected.
  At 09:44 UTC both apt services were inactive, no apt/dpkg lock holder, and
  unattended-upgrades PID 1070 was the **shutdown helper waiting for a signal**,
  not an active package transaction. Plan protection against timer/package races
  during execution; nothing was disabled here.
- **Flux image automation IS active**: `flux-system/apps`, unsuspended, 10-minute
  interval, Setters path `./apps/prd`, observed policies foodbot/wrenchmate;
  last reported push 2026-09-24T14:40:58Z. Do not claim all updates are disabled.
- All 37 HelmReleases and all 6 Kustomizations are unsuspended. Broad chart
  constraints include app-template `>=4.6.0`, CNPG `>=0.22.1`, ingress
  `>=4.11.2`, cert-manager `1.x`, Tailscale `1.x`, Vikunja `*`; only Plex is
  exact-pinned here and MetalLB stays within `0.14.x`. Source refresh plus
  resumed reconciliation can upgrade these without a Git change.
- Mutable `latest`/Always examples: Sonarr, Radarr, NZBGet, Overseerr, Heimdall,
  Calibre-Web, Endurain, Spottarr, geo-activity-playground, VeloMate ingestor and
  protonmail socat sidecar. Protonmail bridge itself uses a **local latest image
  with pullPolicy Never**: preserve its local availability; do not prune caches.
- Existing CronJobs are Heimdall seeding and Recyclarr; neither is an observed
  k3s updater. Both completed jobs have active=0; no recovery job remains.

Apps/infra Kustomizations currently apply approved GPU revision
`402d5b676dde3d08dae82a645a3ce7f00b609d61`; separate manual-Ducati Kustomization
still reports its earlier successful revision. Do not treat that legitimate
per-source revision difference as a reconciliation failure.

## Candidate dependency order and acceptance checklist

1. Merge the separate official-version research with this **actual** inventory.
   Choose exact sequential 1.34, 1.35 and destination patches; decide the endpoint
   from currently supported releases, not the historical plan's placeholder.
   Check upstream controller matrices, k3s bundled runtime/CNI release notes,
   kubelet swap/CRI behavior, API removals and target-version chart rendering.
2. Resolve a concrete unsupported controller/API gate **before the affected
   hop**, in a separately approved GitOps window. Do not gratuitously upgrade
   every healthy app/controller or couple ingress cutover with the k3s restart.
   Retired ingress still needs a maintained replacement plan independent of
   whether the first hop is technically compatible.
3. Obtain execution/downtime approval and a narrowly authorized drift-control
   policy. Preserve unrelated local Flux edits; no blanket commit/push. Decide
   what happens to image automation and semver chart updates during each window.
4. Before **each hop**, capture/verify fresh matching consistent SQLite, token,
   current binary/unit/runtime configuration and credential-free image/PVC/Flux
   baseline off-host. Confirm restore instructions, encryption key and physical
   escalation route; backups must be verified before disruptive work.
5. Perform only that approved k3s hop, preserving options; default to service
   restart, not full OS reboot. Observe a defined API recovery deadline. Stop
   on access loss, missing mounts, database errors, non-Ready workloads or critical
   application changes; never stack the next hop on an unresolved failure.
6. Acceptance after every hop:
   - fresh SSH/sudo; expected unit flags/data directory/version and enabled state;
   - API `/readyz`, sole node Ready/no pressure, expected runtime/cgroup/swap config;
   - actual UUID mounts, 7 Bound claims with **same UIDs/paths**, no accidental
     default Traefik/ServiceLB or new empty application storage;
   - expected active pods/controllers Ready and restart counts settle; distinguish
     version-bundled system image changes from forbidden application drift;
   - 37 HR/6 KS Ready at intended revision; charts/images/CRDs unchanged except
     explicitly approved changes; webhook/conversion endpoints recover;
   - CoreDNS/cluster DNS, nginx **192.168.1.201**, 22 DNS/TLS/HTTPS routes and three
     Tailscale Foundry paths; preserve external-dns/cert renewal functionality;
   - CNPG sole instance healthy; read-only HA/arr/library/Vikunja/Obsidian/Foundry
     and other agreed app checks; writes/download/imports require authorization;
   - Intel plugin Ready, node i915 allocatable=1, Plex request/limit=1 and original
     claim/image/identity; actual Noble nodes **card1/renderD128**, not hardcoded
     card0. Approve bounded real VAAPI acceptance separately from this read-only
     audit; static probe repair is a local follow-up, not hardware failure;
   - existing MCP integration remains untouched; no reason to recreate OAuth or
     reboot merely for a k3s binary hop. Full Foundry gameplay remains the owner's
     deliberately deferred offline-only check, not a prerequisite secretly passed.
7. Advance only after acceptance and a fresh next-hop checkpoint. If rollback is
   needed, use the **matching binary/config/datastore** recovery unit with server
   stopped; a binary-only downgrade is not a demonstrated datastore rollback.
   Account for post-checkpoint application/GitOps writes before restoring state.

**Next action:** coordinator combines these findings with official support
research and writes the proposed plan. This document grants no mutation authority
and remains local/uncommitted.

## Additional official support checks — retrieved 2026-10-09

**Web/local-only follow-up.** No further SSH/API/pod operations, backups or
deployment writes were performed. Only this author's document was appended.
The parent's Sonarr/Radarr authentication investigation was not duplicated.
The current app/auth baseline must be accepted by the coordinator before any
upgrade or digest-pin rollout; this support research does not resolve it.

### Installed versions against the proposed minor ladder

Legend: **Yes** = explicit official range covers the minor; **U** = exact
version/minor testing or support is unverified, **not a demonstrated runtime
failure**. Range statements are not empirical tests of ryback or every exact
Kubernetes patch. All source URLs below were retrieved on **2026-10-09**.

| Installed component | 1.34 | 1.35 | 1.36 | Exact official evidence and interpretation |
| --- | --- | --- | --- | --- |
| Flux **2.8.6** / previously listed controller set | Yes | Yes | U | Archived 2.8 docs list `1.33 >=1.33.0`, `1.34 >=1.34.1`, **“v1.35 and later >=1.35.0”**. However, 2.8.0 release's explicit table ends at 1.35; **exact 2.8.6 conformance workflow** tests Kubernetes 1.33.0/1.34.1/1.35.0 and k3s 1.33.7/1.34.3/1.35.0, **not 1.36**. Do not turn “and later” into exact 1.36 test certification. The 2.8.6 release confirms the audited component versions. |
| ingress-nginx **1.15.1 / chart 4.15.1** | Yes, tested | Yes, tested | U/outside table | Official README row explicitly lists **1.31–1.35**, describes this as passing E2E tests. No 1.36 row. Retirement notice explicitly says existing deployments are not broken; lifecycle/security debt still applies. |
| cert-manager **1.21.2** | Yes, tested | Yes, tested | Yes, tested | Supported Releases table: **1.21 supported/tested 1.33–1.36**, EOL at release of 1.23. Policy supports only latest patch in branch; official releases listing shows **1.21.2** is newest 1.21 final patch (2026-09-11). No controller upgrade needed for these minors. |
| CNPG **1.30.1 / chart 0.29.1** | Yes | Yes | Yes | Versioned 1.30 support table and release notes explicitly list **1.34, 1.35, 1.36**; 1.33 is “tested, but not supported”. Release notes' newest patch is **1.30.1**, 2026-09-23; policy supports newest branch patch. Table gives approximate Dec 2026 operator EOL: this does **not** inherit Kubernetes 1.36's June 2027 EOL. PostgreSQL 18 remains supported; do not change the running 18.3 image just because docs' default is 18.4. |
| MetalLB **0.14.9** | U | U | U | Exact-tag website source states **Kubernetes 1.13.0 or later**; packaged chart says >=1.19. These are minima, not a tested upper range. Exact-tag CI has an oldest-Kubernetes test at **1.27.1**, but no target-minor support matrix was found in official docs/CI inspected. No evidence found of a hard 1.34–1.36 API break. |
| Tailscale operator/proxies **1.102.4** | U, minimum met | U, minimum met | U, minimum met | Official compatibility policy states **earliest supported Kubernetes v1.23.0**, with no upper/version-specific E2E matrix. Same operator/proxy version is recommended and already present; proxies up to four older minors supported, newer proxies unsupported. Exact 1.102.4×1.34/35/36 testing remains unverified. |
| Intel standalone plugin **0.37.1** | Backward-compatibility policy | Backward-compatibility policy | Backward-compatibility policy | **Exact-tag README** maps release-0.37 to Kubernetes 1.37, but explicitly says newer plugin releases should work on older Kubernetes via stable Kubernetes v1 API; operator CRDs are the stated possible exception, **not used here**. Keep working digest/allocation, not a gratuitous plugin downgrade. This is policy evidence, not an exact E2E certification of each hop. |
| external-dns **0.23.0** | Yes, range policy | Yes, range policy | Yes, range policy | **Exact-tag README** compatibility table marks **Kubernetes >=1.33** compatible with external-dns **>=0.18.x**. 0.18 switched to EndpointSlices; 0.10 switched to networking Ingress. No forced provider/CRD migration identified for the current deployment. |

**Flux-specific prerequisite if choosing documented tested support for 1.36:**
separately approve a pinned maintained **Flux 2.9.x** update while on accepted
1.34/1.35, before the 1.36 hop. Official **2.9.0** release explicitly lists
**1.34 >=1.34.1, 1.35 >=1.35.0, 1.36 >=1.36.0**; the current installation page
also gives that range. This is an optional conservative support-evidence
resolution, not proof Flux 2.8.6 breaks on 1.36. The parent must select/check the
exact 2.9 patch, migration and controller changes; none was installed here.

Official sources and exact proof:

- Flux archived version docs: <https://v2-8.docs.fluxcd.io/flux/installation/>
  (Prerequisites table; archived documentation, not current 2.9 page).
- Flux 2.8.6: <https://github.com/fluxcd/flux2/releases/tag/v2.8.6>
  and <https://api.github.com/repos/fluxcd/flux2/releases/tags/v2.8.6>
  (component changelog agrees with installed helm 1.5.4, kustomize/notification
  1.8.4, source 1.8.3, image automation 1.1.2).
- Exact Flux test matrix:
  <https://raw.githubusercontent.com/fluxcd/flux2/v2.8.6/.github/workflows/conformance.yaml>.
- Flux release tables/migrations:
  <https://api.github.com/repos/fluxcd/flux2/releases/tags/v2.8.0>,
  <https://api.github.com/repos/fluxcd/flux2/releases/tags/v2.9.0>,
  <https://fluxcd.io/flux/installation/>.
- ingress-nginx exact version/chart row and retirement wording:
  <https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/README.md>.
- cert-manager supported/tested/policy table: <https://cert-manager.io/docs/releases/>;
  patch publication: <https://api.github.com/repos/cert-manager/cert-manager/releases?per_page=15>.
- CNPG version-specific matrix:
  <https://cloudnative-pg.io/docs/1.30/supported_releases/>;
  patch/release change notes:
  <https://cloudnative-pg.io/docs/1.30/release_notes/v1.30/>.
  The old `/documentation/1.30/supported_releases/` address returned 404; the
  `/docs/1.30/` pages above succeeded. Do not interpret that redirect/path issue
  as missing support evidence.
- MetalLB exact-tag requirements:
  <https://raw.githubusercontent.com/metallb/metallb/v0.14.9/website/content/_index.md>;
  exact-tag CI:
  <https://raw.githubusercontent.com/metallb/metallb/v0.14.9/.github/workflows/ci.yaml>.
- Tailscale compatibility policy (page last validated 2026-06-05):
  <https://tailscale.com/docs/kubernetes-operator/reference/compatibility>.
- Intel exact-tag compatibility and GPU/CDI documentation:
  <https://raw.githubusercontent.com/intel/intel-device-plugins-for-kubernetes/v0.37.1/README.md>,
  <https://raw.githubusercontent.com/intel/intel-device-plugins-for-kubernetes/v0.37.1/cmd/gpu_plugin/README.md>.
- external-dns exact-tag compatibility table:
  <https://raw.githubusercontent.com/kubernetes-sigs/external-dns/v0.23.0/README.md>.

### Hard API/CRD changes versus support gaps

**No new demonstrated hard Kubernetes API/CRD migration blocker was identified
for the unchanged audited controllers.** The parent's exact k3s/Kubernetes
change analysis is in `k3s-version-research-2026-10-09.md`; it is not repeated
as a new live check here. The existing audit found no custom kubelet flags/gates,
no cgroup-v1 baseline, no DRA resource API group and no stored-version backlog.
Traditional Intel extended-resource allocation is not a DRA migration.
Ingress networking/v1, stable webhook AdmissionReview v1 and established custom
beta/alpha APIs are not automatically removed by these k3s minor upgrades.

Conditional changes **if choosing a prerequisite controller update**:

- **Flux 2.9 removes `image.toolkit.fluxcd.io/v1beta2` and
  `notification.toolkit.fluxcd.io/v1beta2`.** The audited image CRDs already
  store v1, notification alerts/providers store v1beta3, receivers v1. A local
  top-level API scan finds all five image-automation manifests use v1 and no
  notification API manifest match. Thus no known stored-object blocker, but
  check external clients/generated manifests before removing served versions.
  The 2.8.6 notes also warn a GCR Receiver `audience` becomes mandatory in 2.9;
  no claim was made that such a receiver exists or is absent live.
- CNPG **in-tree Barman Cloud removal is planned for operator 1.31**, explicitly
  deferred from 1.30. It is not forced by upgrading Kubernetes with 1.30.1 held.
  Do not auto-follow broad CNPG chart constraints into that migration.
- MetalLB's **ConfigMap-to-CR migration began at 0.13**; this deployment already
  uses established CRDs. A newer MetalLB chart can change default backend from
  FRR sidecars to FRR-K8s and auto-upgrade CRDs. Its current FRR sidecars make
  this a real review item **if** an update is proposed, not a mandatory network
  conversion during k3s upgrade. Source: <https://metallb.io/installation/>.
- For cert-manager, Tailscale and the standalone GPU plugin, no required
  controller/CRD migration was found solely for 1.34→1.35→1.36. MetalLB/Tailscale
  missing exact test matrices remain uncertainties, not fabricated hard blocks.

### Ingress timing and bounded replacement options

**Reasonable phased choice:** reach accepted **1.35.9+k3s1**, then hold there
for a separately approved ingress replacement and, if desired for explicit
test coverage, Flux 2.9.x update; continue to **1.36.5+k3s1** only after those
gates and per-hop recovery/acceptance. ingress-nginx 1.15.1 is explicitly tested
on both transit minors. This gets off EOL 1.33 without making 22-route conversion
a prerequisite to the first restart. The interim security/lifecycle risk must
be expressly accepted and migration scheduled; 1.35 is not the final June-2027
destination. No assumption of an automatic March-retirement runtime failure.

**Alternative:** migrate before the first hop if the owner prioritizes retiring
nginx immediately and accepts a larger prerequisite window. It reduces time on
retired ingress but delays leaving EOL Kubernetes and adds route/API change
risks before the initial k3s-only acceptance. Stage alongside, use a separate
class/MetalLB address, test/cut over deliberately; do not change k3s disabled
bundled-component flags to deploy a replacement accidentally.

Bounded official-fit comparison, **not a selected design or deployment**:

- **Envoy Gateway 1.9** explicitly tests **Kubernetes 1.33–1.36**, so it can be
  staged on the **current** cluster or the 1.35 holding point; matrix EOL
  **2027-02-14** means it will need its own later maintenance before June 2027.
  Matrix pairs it with **Gateway API 1.6.1** and Envoy Proxy **1.39.x**.
  Official quickstart currently uses **1.9.2** and recommends a LoadBalancer
  implementation such as MetalLB. This offers the strongest explicit tested
  range found here, but converts routes to Gateway/HTTPRoute/policies and adds
  CRDs; existing nginx annotations are not inherently preserved. Current Noble
  does not introduce a documented additional requirement in these sources;
  no Ubuntu-specific certification is claimed.
  Sources: <https://gateway.envoyproxy.io/news/releases/matrix/>,
  <https://gateway.envoyproxy.io/v1.9/tasks/quickstart/>.
- **Standalone Traefik** has an official Ingress-NGINX provider/migration guide
  that supports many nginx annotations and existing Ingress TLS references,
  potentially reducing conversion work. Official chart README requires
  **Kubernetes >=1.25.0**; fetched chart metadata is **41.7.0 / Traefik 3.7.14**
  with the same minimum, so current 1.33 meets that requirement. However, an
  exact 3.7.14×1.33–1.36 test matrix was **not found**, and annotation support is
  not complete. Official caveats include auth behavior, per-Ingress timeouts,
  path/regex handling and unsupported auth annotations. Use the already known
  22-route annotation audit and parent auth findings; do not assume a drop-in
  match or re-investigate application login here. Keep bundled Traefik disabled;
  any separate chart deployment requires its own approved configuration/class/IP.
  Sources: <https://raw.githubusercontent.com/traefik/traefik-helm-chart/master/README.md>,
  <https://raw.githubusercontent.com/traefik/traefik-helm-chart/master/traefik/Chart.yaml>,
  <https://doc.traefik.io/traefik/migrate/nginx-to-traefik/>,
  <https://doc.traefik.io/traefik/reference/install-configuration/providers/kubernetes/kubernetes-ingress-nginx/>,
  <https://doc.traefik.io/traefik/reference/routing-configuration/kubernetes/ingress-nginx/>.

Neither option is yet authorized or route-validated. Their own support lifespan
must be managed independently of the Kubernetes endpoint.

### Minimal drift-control proposal requiring separate owner approval

Prefer a reviewed **GitOps-only maintenance lock**, delivered/accepted before
the first k3s restart, rather than stopping Flux controller services or pausing
application replicas:

1. Temporarily suspend **only `ImageUpdateAutomation/flux-system/apps`** through
   its Git manifest and agree no unrelated deployments/main-branch updates during
   each maintenance window. This alone does **not** freeze charts or mutable tags.
2. Pin broad Helm chart constraints to the **currently accepted installed chart
   versions** listed above (or, if an explicitly temporary maintenance design is
   preferred, GitOps-suspend those HelmReleases). Exact chart pins allow normal
   Flux reconciliation/acceptance without pulling a new semver-selected chart.
   Verify chart/artifact revisions and safe rendered diffs before application.
3. Lock mutable application images to their **accepted current immutable digests**,
   including init containers/sidecars, not just main containers. Changing image
   references usually rolls workloads: this is a separate approved preparation
   rollout with image/PVC/auth/GPU acceptance and a **new** baseline afterward.
   Preserve the locally built Protonmail `Never` image/cache separately; a
   registry-resolvable digest must not be invented for it.
4. Keep Flux controllers running and existing app data/replicas unchanged. Record
   originals and an explicit resume/unpin decision after accepted maintenance.
   Do not sweep unrelated Flux work into commits. Check freeze behavior again
   if a separately approved Flux upgrade happens at the 1.35 holding point.

If the owner declines digest-pin rollouts, a chart/Git automation freeze still
leaves `latest`/Always pull drift on container recreation. Record that as an
explicit isolation-risk exception; changing Always to IfNotPresent, suspending
Flux or relying on running image IDs does **not** provide an immutable-image
guarantee. Do not silently call that fallback a k3s-only zero-app-change plan.

### Per-hop planning decision summary

- **Optional 1.33.13+k3s2:** no new controller range conflict found, but remains
  EOL Kubernetes; adds one recovery/restart cycle. No obligation inferred.
- **1.34.12+k3s1:** conditional planning **GO** once auth baseline, approval,
  drift control and fresh matching recovery point are accepted. Flux, nginx,
  cert-manager, CNPG and external-dns explicitly cover this minor. MetalLB and
  exact Tailscale testing are U; approve/validate those uncertainties, not an
  automatic controller upgrade. Intel backward-compatibility policy applies.
- **1.35.9+k3s1:** same conditional planning **GO**, with prior-hop acceptance.
  A practical maintained interim holding point for separate ingress work.
- **1.36.5+k3s1:** **HOLD for the conservative documented-tested plan** while
  nginx 1.15.1 remains the ingress implementation. Replace ingress separately,
  or explicitly approve a outside-tested-range exception with rehearsal/route/
  webhook validation; no hard runtime failure is asserted. Resolve Flux 2.8.6's
  exact-test gap via separately approved 2.9.x or a documented exception. Keep
  cert-manager 1.21.2/CNPG 1.30.1/GPU unchanged where accepted; address remaining
  MetalLB/Tailscale uncertainties deliberately. Recheck all matrices at actual
  execution time and do not promise controller support until June 2027 merely
  because the target Kubernetes minor has that lifecycle.
