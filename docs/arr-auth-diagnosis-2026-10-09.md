# Sonarr/Radarr HTTPS authentication regression — 2026-10-09

## Outcome and boundary

**High-confidence cause: the first Ubuntu maintenance reboot unexpectedly updated
both applications through mutable `latest` images / `imagePullPolicy: Always`.
The newer applications no longer automatically trust private-network reverse
proxies. Their existing LAN authentication bypass therefore stops working through
nginx ingress. Authentication settings and stored credentials did not change.**

Read-only diagnosis only. No API writes, configuration edits, authentication
changes, password resets, pod mutations, upgrades, commits or pushes. Only this
local document was added; unrelated work, including Recyclarr configuration, was
left untouched. Loaded `arr-admin` and `diagnose`; read the Flux guidance and
Overseerr, Plex-notification and Sonarr-import briefs.

The user confirmed the affected URLs are `https://sonarr.suetens.cc` and
`https://radarr.suetens.cc`. This finding does not assume the user previously
knowingly logged in. It explains how previously passwordless LAN access can
regress despite identical authentication settings.

## Deterministic reproduction

Unauthenticated GETs, with redirects disabled and no cookies/credentials:

| Access path / one-variable probe | Sonarr root | Radarr root |
| --- | --- | --- |
| Actual HTTPS hostname, from Mac LAN | 401, `Basic realm="Sonarr"` | 302, `/login` |
| Same HTTPS hostname, from ryback | same | same |
| Direct Service ClusterIP | 200 | 200 |
| Direct service + same hostname in `Host` | 200 | 200 |
| Direct service + `Host` + `X-Forwarded-For: 192.168.1.110` | 401 Basic | 302 |
| Direct service + `Host` + TEST-NET public `X-Forwarded-For` | 401 Basic | 302 |
| Direct service + `Host` + `X-Real-IP` alone (LAN or TEST-NET) | 200 | 200 |

Repeated HTTPS-root probes from both machines returned stable results. Both
machines resolve the actual hostnames to `192.168.1.201`; this was not a different
DNS destination. `/login` returns 200 on both access paths. Unauthenticated
`/api/v3/system/status` returns 401 on both paths: the UI LAN bypass is not an API
key bypass. Two native, authenticated GET status reads per app returned stable
versions/start times; API keys stayed in server memory.

The generated nginx locations for the actual hostnames contain
`proxy_set_header X-Forwarded-For $remote_addr` and `X-Real-IP $remote_addr`, with
neither `auth_basic` nor `auth_request`. Ingress metadata also has no auth
annotations. The apps, not nginx basic-auth configuration, issue the prompts.

## Hypotheses and disposition

The initial ranked list was shown before historical testing:

1. Lost browser session or different access path: cannot explain the verified
   old/new proxy-policy difference; not needed to explain this regression.
2. Changed source/proxy classification: **confirmed**, caused by new application
   proxy-trust policy, not evidence of a changed ingress image or DNS destination.
3. Changed authentication settings: rejected by original-baseline/current match.
4. Mutable-image update: **confirmed**, at the first reboot, before Noble.
5. New ingress authentication: rejected by configuration and differential probe.

## Historical settings and credentials

Selected original files were privately inspected from verified encrypted run
`~/homelab-backups/ryback/20261008T132448Z-ec0bde38/`:

- `applications.tar.zst.age`: active apps' `config.xml` only.
- `databases.tar.zst.age`: active apps' standalone native SQLite snapshots and
  whitelisted pod/ingress/controller metadata.
- Checked encrypted archive digests against the verification report, fully drained
  age/zstd streams to authenticated EOF, and checked selected-file hashes against
  the archive manifest before using the results.
- SQLite snapshots had `PRAGMA quick_check = ok`. Only these complete native
  snapshots used immutable read-only SQLite; current databases used `mode=ro`.
- Extracted SQLite files were mode 0600 in an approved private temporary directory,
  then deleted automatically. No live files were restored.

| Whitelisted setting | Original pre-maintenance | Current XML and authoritative GET host config |
| --- | --- | --- |
| Sonarr authentication | Basic | Basic |
| Radarr authentication | Forms | Forms |
| Both authentication-required policy | DisabledForLocalAddresses | DisabledForLocalAddresses |
| Bind address | `*` | `*` |
| Ports | Sonarr 8989; Radarr 7878 | same |
| URL base / app-side SSL | empty / false | same |

Each original SQLite `Users` table had one configured account. Private equality
comparisons of its credential records (including password/salt), against current
read-only queries, returned **unchanged = true** for both apps. Both API-key
comparisons also returned **unchanged = true**. No usernames, passwords, hashes,
API keys, tokens, cookies or raw configuration were printed or retained here.

Current `TrustedNetworks` is empty in XML and GET host config for both apps;
there are no trusted-network environment overrides. Current
`trustCgnatIpAddresses` is false. The old versions' proxy behavior was hard-coded,
so an unchanged old configuration does not preserve that behavior in newer code.

The narrow pre-22 and pre-24 archives intentionally exclude app configurations
and app databases; do not claim a separate pre-Noble app-config snapshot from
them. They do provide verified image/ingress evidence. Jammy acceptance already
recorded Sonarr HTTPS 401 and Radarr a login-path response, after the first image
update; Noble acceptance recorded 401 and 302 respectively. Those acceptance
checks classified responses as expected but did not establish unchanged user
experience.

## Actual image/version timeline (not merely deployment specifications)

Verified pod inventories from original run, pre-22
`20261009T063359Z-bb1e3ce0/databases-host-preubuntu22.tar.zst.age`, and pre-24
`20261009T075949Z-b6d955cb/databases-host-preubuntu24.tar.zst.age`:

| App | Original / immediate pre-22 image | Pre-24 and current image |
| --- | --- | --- |
| Sonarr | 4.0.17.2952; `sha256:bed3afb5d46fde809290997760f2e19d41e57d1eb34f507c485d5a8979c7cd8d` | 4.0.20.3014; `sha256:f247545d23ba8b233d6604575347e48a623fe6ad75dda02348bf81917f3b5c06` |
| Radarr | 6.1.1.10360; `sha256:659e5f20500948b1491f31dd85c6f99a43508ce3e46595793e1e15aa955bf6d7` | 6.4.4.10685; `sha256:7dfd049e79c00b16fbc29c3f5d96a9e7b9e73a23930b4c5b3c4541d60b366814` |

Old cached image labels independently establish the old versions. Bounded startup
log inspection confirms Sonarr switched from 4.0.17.2952 to 4.0.20.3014 around
07:05 UTC on October 9; Radarr switched from 6.1.1.10360 to 6.4.4.10685 around
07:04 UTC. The pre-24 inventory captured these new images already running.
Current processes started around 09:22 UTC, with the same new image digests.
Both deployment tags remain `lscr.io/linuxserver/<app>:latest`; both pull policies
are `Always`. Unchanged image specifications were **not** unchanged running code.

Ingress controller's actual image digest stayed
`sha256:594ceea76b01c592858f803f9ff4d2cb40542cae2060410b2c95f75907d659e1`
across original, pre-22, pre-24 and current observations. Hostnames, ingress class
and absence of authentication annotations match. Original and current controller
ConfigMaps have no entries for the checked forwarded-header/real-IP options.

## Mechanism: old vs new release source

The exact release-tag source was compared read-only:

- [Old Sonarr Startup](https://github.com/Sonarr/Sonarr/blob/v4.0.17.2952/src/NzbDrone.Host/Startup.cs)
  and [old Radarr Startup](https://github.com/Radarr/Radarr/blob/v6.1.1.10360/src/NzbDrone.Host/Startup.cs)
  automatically trust private proxy networks, including `10.0.0.0/8`.
- [New Sonarr ForwardedHeadersConfigurator](https://github.com/Sonarr/Sonarr/blob/v4.0.20.3014/src/NzbDrone.Host/ForwardedHeadersConfigurator.cs)
  and [new Radarr equivalent](https://github.com/Radarr/Radarr/blob/v6.4.4.10685/src/NzbDrone.Host/ForwardedHeadersConfigurator.cs)
  only add explicit `TrustedNetworks`; empty config leaves no trust for the
  ingress pod's network.
- New [Sonarr UiAuthorizationHandler](https://github.com/Sonarr/Sonarr/blob/v4.0.20.3014/src/Sonarr.Http/Authentication/UiAuthorizationHandler.cs)
  and [Radarr equivalent](https://github.com/Radarr/Radarr/blob/v6.4.4.10685/src/Radarr.Http/Authentication/UiAuthorizationHandler.cs)
  require `IsClientAddressKnown`, which rejects the local bypass if an unprocessed
  `X-Forwarded-For` header remains. Both old handlers lack this check.

Current ingress pod IP is `10.42.0.193`, within node pod CIDR `10.42.0.0/24`.
The old code trusted this private proxy automatically; the new code does not.
The one-header HTTP differential directly reproduces the changed decision.
Different existing auth methods then explain Basic challenge vs Forms redirect.

## Minimal safe next choice — proposal only

Offer the user a focused repair of proxy trust to restore **LAN passwordless /
external authenticated** behavior while retaining Basic/Forms and the existing
local-address policy. First verify the actual client source arriving at nginx
from LAN and an external connection, and review the exposure boundary. Current
ingress Service uses `externalTrafficPolicy: Cluster`; NAT may obscure an external
source, so simply adding proxy trust is not sufficient proof of safety.

If source fidelity is verified, explicitly trust only the actual ingress proxy
via each app's supported `TrustedNetworks` host setting, with a narrow and durable
scope. A current single pod `/32` is narrow but changes on rescheduling; broader
pod ranges trust other workloads and require an explicit security decision.
Obtain approval for the chosen app-state change and any required GitOps work,
then regression-test anonymous LAN UI access and authentication for an external
source. Never blindly disable authentication, strip forwarding headers, trust
all networks, or downgrade to older proxy-safety behavior.

Until then, the unchanged existing accounts remain configured; this diagnosis
does not reset, reveal or test their credentials. If the user chooses to keep
authentication instead, normal existing-account login is the no-policy-change
option, not the explanation for the regression.

## Implication for planned k3s maintenance

This is an application compatibility regression triggered by restart, not evidence
of a k3s version defect (k3s remains v1.33.11+k3s1). Record it as an unresolved
user-facing acceptance issue before proceeding. Future reboot/k3s planning must
compare actual image digests and versions, not just mutable image specifications;
pin reviewed images through separately approved GitOps changes or explicitly
account for further `latest` updates. No upgrade or repair was executed here.

## Follow-up source-IP/exposure audit — read-only, 10:00 UTC

**Do not apply proxy trust alone. Actual client-source loss is proven. Also,
`externalTrafficPolicy: Local` alone does not solve the existing Tailscale subnet
router's source NAT. Full LAN-vs-remote safety remains conditional on that path.**

### Actual tagged-request and network evidence

Two ordinary anonymous HTTPS GETs from the Mac used harmless query/User-Agent tag
`arr-auth-source-audit-20261009-7d65`. Only their matching nginx log metadata was
returned; no other requests, credentials or cookies were displayed.

- Mac's route source is `192.168.1.171`.
- Nginx recorded **`remote_addr = 10.42.0.1` for both tagged requests**.
- Live ingress Service: LoadBalancer VIP `192.168.1.201`, ClusterIP
  `10.43.92.160`, `externalTrafficPolicy: Cluster`; HTTP/HTTPS NodePorts
  31296/30672. Its sole EndpointSlice endpoint `10.42.0.193` is Ready on ryback.
- Controller is not host-networked; host IP `192.168.1.110`, pod IP
  `10.42.0.193`. Node pod CIDR is `10.42.0.0/24`.
- Live NAT rules for both ingress external-destination chains unconditionally
  jump to `KUBE-MARK-MASQ`; `KUBE-POSTROUTING` applies MASQUERADE to that mark.
  This corroborates, rather than merely assumes, the observed LAN source NAT.
- Nginx overwrites `X-Forwarded-For` and `X-Real-IP` with `$remote_addr`; checked
  real-IP/forwarded-header ConfigMap overrides are absent. Do not try to repair
  this by stripping headers or trusting client-supplied forwarding headers.

WAN packets arriving through this same LoadBalancer/NodePort path also match the
masquerade rule. That is a rule-based prediction, **not** an observed external
connection. Proxy trust would let the apps see the private masquerade address
and bypass authentication irrespective of the original client location.

### Exposure and remaining external-vantage gap

An independent public recursive DNS-over-HTTPS lookup returned only
`A = 192.168.1.201` for both hostnames, with no AAAA or CNAME answers. MetalLB is
configured for L2 advertisement of `192.168.1.200–249`. These exact DNS URLs have
no publicly routable address, but this does **not** rule out router forwarding,
alternate public hostnames, split DNS, VPN or other access paths. No router
configuration or actual outside-client connection was available in this audit.

There is a verified live remote-access path: Tailscale Connector `ts-nginx-ip`
advertises `192.168.1.201/32`, is Ready, and its subnet-router pod is
`10.42.0.178` (`TS_USERSPACE=false`). Read-only `tailscale debug prefs` reports
**`NoSNAT=false`**. It can conceal an off-LAN client's original address behind a
private pod address independently of kube-proxy. Therefore Local plus app trust
must not be described as guaranteeing authentication for off-LAN Tailscale users.
The installed Connector/ProxyClass schemas expose no direct SNAT property found
in this limited audit; no routing workaround was attempted or proposed as tested.

Owner input/test needed: from a phone on cellular, first **without** Tailscale,
then **with** Tailscale, open both exact URLs with a harmless per-test query tag.
Clarify whether remote Tailscale users must be prompted or are intentionally
treated as trusted LAN users. Correlate each reachable request with nginx source
metadata. Unreachable non-VPN private DNS is expected, but is not proof that all
other public forwarding is absent. The owner should confirm any router/public
forwarding. Spoofed-header tests are never a substitute for this external test.

### Exact candidate changes — not executed, approval required

1. **Prevent another application update during the repair.** Only the two image
   objects in `~/Documents/homelab-flux/apps/prd/sonarr-values.yaml` and
   `apps/prd/radarr-values.yaml`, under
   `spec.values.controllers.main.containers.main.image`, would change:

   ```yaml
   # Sonarr image object; retain existing repository
   tag: "4.0.20.3014-ls326"
   digest: "sha256:f247545d23ba8b233d6604575347e48a623fe6ad75dda02348bf81917f3b5c06"
   # Radarr image object; retain existing repository
   tag: "6.4.4.10685-ls319"
   digest: "sha256:7dfd049e79c00b16fbc29c3f5d96a9e7b9e73a23930b4c5b3c4541d60b366814"
   ```

   Both observed parent digests are still retrievable public OCI indexes, with
   Linux amd64 entries. Their amd64 config labels report the exact tags above.
   The installed app-template/common 5.2.1 image helper supports separate
   `repository`, `tag`, `digest` and renders `repository:tag@digest`. No image
   pull or workload was created. Digest pinning, not a guessed tag, supplies the
   immutable identity. This retains current code; no downgrade/database rollback.
   Neither app has an image-automation marker or ImagePolicy. The live policies
   concern foodbot/wrenchmate only: **no automation markers need removal and no
   global image automation should be disabled**.

2. **Preserve actual client IPs at the Kubernetes ingress boundary.** In
   `infrastructure/controllers/ingress-nginx.yaml`, add only:

   ```yaml
   spec:
     values:
       controller:
         service:
           externalTrafficPolicy: Local
   ```

   This is the supported installed ingress-nginx chart 4.15.1 value. A healthy
   local endpoint on the one-node MetalLB installation makes it plausible, but
   it needs runtime verification. It changes source handling for **all 22 nginx
   ingress resources**, not just the two apps. Explicit approval must cover this
   shared-Service scope, VIP reachability and representative route checks. It
   does not upgrade/replace ingress or change application authentication. Apply
   separately first, while apps still reject anonymous proxied access; verify
   genuine client-source fidelity before allowing any app local bypass.

3. **Only after source/exposure gates pass**, persist narrowly scoped app trust
   through GitOps env overrides in the existing two app container `env` objects:

   ```yaml
   # apps/prd/sonarr-values.yaml
   SONARR__SERVER__TRUSTEDNETWORKS: "10.42.0.193/32"
   # apps/prd/radarr-values.yaml
   RADARR__SERVER__TRUSTEDNETWORKS: "10.42.0.193/32"
   ```

   Exact current release source binds `Sonarr:Server` / `Radarr:Server` from
   environment configuration, `ServerOptions.TrustedNetworks` is a string, and
   ConfigFileProvider gives that override precedence over XML. The correct
   namespace is **SERVER, not AUTH**. No XML/API write is required for this
   proposed configuration. Existing Basic/Forms, credential sets and
   DisabledForLocalAddresses remain untouched.

   A `/32` trusts only the current ingress pod. The configuration is durable,
   but the pod address is not: after rescheduling it fails closed (login returns)
   until explicitly reviewed/updated. `10.42.0.0/24` is operationally more durable
   on this node but grants header trust to **all** its pods, including the remote
   subnet router; it is not proxy identity. Prefer the `/32` candidate for the
   minimal repair, acknowledging this maintenance tradeoff. Never trust all
   private networks or `0.0.0.0/0` as a shortcut.

**Approval gate:** if remote Tailscale must remain authenticated, this three-item
candidate is not yet sufficient because `NoSNAT=false` survives item 2. Leave
app trust unset until that remote path is demonstrably source-preserving or
separately isolated by an explicitly approved, supported design. No blanket
restore-LAN claim is justified with the current remote-path ambiguity.

### Validation plan after explicit approval

- After Service Local, repeat a new tagged Mac request: nginx must log
  `192.168.1.171`, not `10.42.0.1`. Check all Ready endpoints, VIP, and representative
  routes among the 22 affected ingress resources. Check Tailscale reachability
  without assuming its source NAT was fixed.
- Before/after any app rollout, native GET status must retain the pinned digests,
  versions and authoritative auth/credential state (boolean comparisons only).
- After app trust, anonymous LAN root must give 200 for both actual HTTPS URLs;
  anonymous protected API GET must still give 401.
- A read-only request **originating in the trusted ingress pod**, directly to
  each app's Service, with a TEST-NET public `X-Forwarded-For`, must give Sonarr
  401 Basic / Radarr 302 login. The equivalent genuine LAN header may give 200.
  This tests the app classification once the trusted-peer condition is met, not
  actual internet connectivity. An untrusted peer supplying either header must
  still get challenged.
- Through nginx, a client-supplied fake public/private header must not replace
  the genuine `$remote_addr`; correlate tagged source logs. This sanitization
  check is distinct from the trusted-peer app test.
- Actual off-Wi-Fi tests must independently verify reachable public and Tailscale
  paths and the intended auth boundary. If source remains private due to router
  or subnet-router NAT, do not enable/retain app trust and call the boundary safe.

No candidate changes, pins, service updates, API writes, routing changes, reloads,
restarts or new workloads were executed. Only this document was appended.

## Subsequent explicitly approved execution

The read-only statements above describe the diagnosis/audit stage. The owner
subsequently selected passwordless LAN **and their Tailscale devices**, confirmed
no public forwarding/tunnel for these apps, and explicitly approved committing,
pushing and deploying the shared-Service repair and current image/chart pins.
Existing Tailscale router SNAT is intentionally trusted under that chosen policy.

Repair is now deployed in Flux commits **109aa59** (nginx chart pin + Local) and
**2d922f7** (current arr image/chart pins + verified proxy `10.42.0.193/32`). Genuine
LAN source preservation, anonymous HTTPS roots 200, public-source challenges,
unchanged credentials/auth methods/versions/digests and 22-route TLS/HTTPS checks
passed. All 59 pods / 43 Flux resources Ready; only the two app pods rolled.

See [the execution and validation record](arr-private-access-fix-2026-10-09.md)
for exact scope, regression matrix and remaining real phone/Tailscale browser
check. No actual WAN-vantage test is claimed. The `/32` requires reviewed updating
after ingress pod-IP changes; it deliberately fails closed instead of broadly
trusting all pods. No OS/k3s/app upgrade, credential reset or Tailscale change was
performed in the repair.
