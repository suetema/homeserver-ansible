# Sonarr/Radarr private-access repair — 2026-10-09

## Authorization and scope

Owner explicitly selected passwordless **LAN and their Tailscale devices**,
confirmed private access only (no router public forwarding/tunnel for these apps),
and approved committing, pushing and deploying the focused repair. Shared nginx
Service source-preservation affects all 22 routes; brief Sonarr/Radarr restarts
are approved. Existing credentials and external authentication must stay intact.
No OS/k3s/application upgrade, downgrade, Tailscale routing/ACL change or unrelated
cleanup is authorized. This execution is the sole live mutator.

Only three Flux files may be committed: the nginx controller HelmRelease and
the Sonarr/Radarr production values. Local diagnostic/probe files stay uncommitted.
Existing unrelated work, including Recyclarr and SOPS files, is preserved.

## Starting verification

- Flux local HEAD and remote main both `402d5b676dde3d08dae82a645a3ce7f00b609d61`;
  index empty, none of the three target files modified.
- Live nginx chart 4.15.1; Sonarr/Radarr charts 5.2.1.
- Current apps 4.0.20.3014 / 6.4.4.10685, authentication Basic / Forms,
  DisabledForLocalAddresses, empty TrustedNetworks.
- Ready ingress pod `10.42.0.193`; VIP `192.168.1.201`; policy Cluster.
- Tailscale router SNAT stays unchanged and is explicitly within the approved
  trusted-private-access policy. External/public forwarded addresses must still
  require application authentication; no actual WAN-vantage test is claimed.

## Execution plan

1. Render the installed charts, verify the nginx pod template will not change,
   commit/push only nginx chart pin + Service Local. Wait for Flux reconciliation.
2. Verify TLS/HTTPS for all routes and tagged Mac source-IP preservation. Re-read
   the actual ingress pod IP before setting trust.
3. Render pinned app manifests, verify immutable image refs and unchanged mounts,
   commit/push only current app image/chart pins + proxy `/32` environment overrides.
4. Verify auth regression matrix, unchanged credential booleans and library/profile
   metadata, versions/digests, Flux/pod health and Plex GPU allocation. Record the
   remaining manual cellular/Tailscale browser check.

Status: **DEPLOYED AND VALIDATED. LAN passwordless access restored; public-source
classification still requires auth. Real phone/Tailscale browser check remains
manual; no actual WAN connection test is claimed.**

## Commits and deployment

1. **`109aa59e86c9d29a07b68457e08d12825e97ad7b`** — only
   `infrastructure/controllers/ingress-nginx.yaml`: pin installed chart 4.15.1 and
   set `controller.service.externalTrafficPolicy: Local`.
2. **`2d922f707e9683c1687ce943c4c9c761b2ee0165`** — only
   `apps/prd/sonarr-values.yaml` and `apps/prd/radarr-values.yaml`: pin installed
   charts 5.2.1, immutable current image digests, and startup proxy-trust overrides.

Both commits pushed to `origin/main`, then reconciled through Flux GitRepository,
the appropriate Kustomization and HelmReleases. No live Deployment/Service/config
was patched or edited. No API settings write, secret change, Tailscale change,
OS/k3s/app upgrade or database restore occurred. Index and unrelated working-tree
changes were preserved; neither helpers nor task documents were committed.

Exact image pins:

- Sonarr `lscr.io/linuxserver/sonarr:4.0.20.3014-ls326@sha256:f247545d23ba8b233d6604575347e48a623fe6ad75dda02348bf81917f3b5c06`.
- Radarr `lscr.io/linuxserver/radarr:6.4.4.10685-ls319@sha256:7dfd049e79c00b16fbc29c3f5d96a9e7b9e73a23930b4c5b3c4541d60b366814`.
- `SONARR__SERVER__TRUSTEDNETWORKS` / `RADARR__SERVER__TRUSTEDNETWORKS` both
  `10.42.0.193/32`. Re-read ingress IP after the Service change and before app
  deployment; it stayed `10.42.0.193`, including final validation.

Public registry reads confirmed these are existing OCI indexes with amd64
entries and matching image-version labels. Helm renders using installed chart
archives confirmed the network change alters only the ingress Service, not the
controller pod template. App renders alter only the image reference and trust
environment variable in each Deployment; mounts and other resources are unchanged.

## Validation results

### Source IP and shared ingress

- Stage 1 tagged Mac source changed from nginx-observed `10.42.0.1` to genuine
  **`192.168.1.171`**. VIP remains `192.168.1.201` and its local endpoint remains
  Ready. Ingress controller did not restart; actual image digest unchanged.
- All **22** nginx HTTPS root probes validated DNS/TLS and retained their prior
  status/redirect behavior after the network stage.
- After app deployment, all **22** still validate TLS; only the expected Sonarr
  401 → 200 and Radarr 302 → 200 root responses changed. Other 20 routes match.
- Runtime nginx still **overwrites** incoming X-Forwarded-For with `$remote_addr`.
  Tagged LAN requests containing fake public/private headers retained the genuine
  Mac source in ingress logs, and did not replace its classification.

### Authentication matrix

| Anonymous GET / client classification | Sonarr | Radarr |
| --- | --- | --- |
| Actual HTTPS root from Mac LAN | 200 | 200 |
| Actual HTTPS root from ryback LAN | 200 | 200 |
| Actual HTTPS protected API status from LAN | 401 | 401 |
| Trusted ingress peer, forwarded genuine LAN address | 200 | 200 |
| Trusted ingress peer, forwarded existing Tailscale-router SNAT address | 200 | 200 |
| Trusted ingress peer, forwarded public TEST-NET address | 401 Basic realm Sonarr | 302 `/login` |
| Untrusted peer supplying a fake LAN/public forwarded address | 401 Basic | 302 `/login` |
| Trusted ingress peer, direct CGNAT-range test address | 401 | 302 |

The trusted-peer checks were credential-free GETs from the **actual nginx pod's
network namespace** directly to each Service. They prove application source
classification, **not an actual WAN or phone/Tailscale connection**. The direct
CGNAT test is not the currently configured Tailscale subnet-router flow: its SNAT
to `10.42.0.178` remains intentionally unchanged and explicitly approved as trusted.

Native API-key authenticated GETs remain successful. Authoritative host config
still reports Basic / Forms, DisabledForLocalAddresses, false trustCgnatIpAddresses,
and the exact proxy `/32`. No global authentication disablement was introduced.

### Secrets, data and runtime

A read-only SSH process held the pre-deployment key and credential records in
server memory throughout deployment, then compared them after both new apps
were serving. For **each app**, credential-record equality, API-key equality and
XML auth-setting equality were **true**; each still has one configured account.
Only booleans and whitelisted public configuration were printed. No secret hashes,
credentials, raw config, tokens or cookies were saved in these local records.

- Sonarr remains **4.0.20.3014**, Radarr **6.4.4.10685**; actual imageIDs equal
  pre-repair values. New pod spec image refs include the pinned digest. CRI status
  may display the cached `latest` alias, but the identity and pod spec are pinned.
- Library counts remain Sonarr **94 series**, Radarr **157 movies**; quality-profile
  ID sets and root paths (`/tv`, `/movies`) unchanged. Rendered hostPath/mounts
  unchanged. No downloads, media files, library/profile settings or PVCs were edited.
- Only the two app pods rolled once (new processes around 10:25 UTC). All **57
  other running pods** retain the baseline UID, imageID, restart count and metadata.
- Final **59/59 running pods Ready**, **43/43 Flux resources Ready**; node Ready,
  k3s still **v1.33.11+k3s1**. No k3s upgrade performed.
- Plex pod unchanged; request/limit `gpu.intel.com/i915 = 1` and node allocatable
  GPU 1 retained. No new transcode test was needed/claimed by this repair.

Credential-free local artifacts: `arr-private-access-{before,network,after}-2026-10-09.json`,
`arr-private-access-web-{before,network,after}-2026-10-09.json`, and
`arr-private-access-auth-mac-2026-10-09.json`. Repeatable native/anonymous probe:
`scripts/arr_private_access_probe.py`. These remain local/uncommitted.

## Remaining manual check and maintenance caveat

Ask the owner to turn off phone Wi-Fi, enable their existing Tailscale connection,
and open both exact HTTPS URLs. They should load without credentials through the
approved existing subnet router. No routing/ACL setting was changed. Private DNS
without Tailscale is not expected to provide public reachability, consistent with
the owner's explicit no-public-forwarding confirmation.

The ingress pod `/32` is intentionally narrow and **fails closed if its IP changes**.
After any future ingress rescheduling/migration, re-verify the actual proxy IP and
source preservation, then update the two GitOps overrides with explicit approval.
Do not broaden trust to the pod subnet/all private networks as an automatic fix.
Any future public forwarding requires a fresh source-IP/authentication boundary
review: upstream router SNAT to private addresses would defeat LAN classification.

No rollback was required. The previously documented remote-Tailscale gate was
resolved by explicit owner policy selection (Tailscale trusted), not by pretending
the subnet router's source NAT had been removed.
