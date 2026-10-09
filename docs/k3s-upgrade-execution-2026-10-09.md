# Ansible k3s execution — 2026-10-09

## Outcome

**COMPLETE. k3s upgraded sequentially v1.33.11 → v1.34.12 → v1.35.9+k3s1**
via Ansible, each hop with a fresh encrypted whole-SQLite checkpoint, bounded
acceptance and a real ≥30-minute observation. Parent granted code-review clearance
(`k3s_code_review_cleared=true` supplied only on the explicit run invocations).
Both hops reported `failed=0`. `ImageUpdateAutomation` was restored to its prior
enabled state after final acceptance. Root phase: **`validated-k3s-1.35`**
(`running_command_category=null`), retaining `validated-noble`.

The earlier blocked attempt performed no mutation; its image/chart isolation
prerequisite is resolved by the approved pins (below).

## Resolved blocker: application image/chart isolation

The blocked first-hop guard found **16 unpinned Always references (13 unique
images)** and **33 broad Helm chart constraints**. All are now resolved by
narrow, current-version-only GitOps pins deployed through Flux in small batches,
each followed by a credential-free digest/readiness validation:

- **Chart pins (34 paths):** every broad constraint pinned to the installed
  version — app-template `5.2.1`, Foundry `15.2.4`, cert-manager `v1.21.2`, CNPG
  `0.29.1`, external-dns `1.23.0`, MetalLB `0.14.9`, Tailscale `1.102.4`,
  Vikunja `2.4.0`, recycled across all `apps/prd/*-values.yaml` and the
  `infrastructure/controllers` releases. A read-only Kustomize/Helm render gate
  verified **zero non-image PodSpec changes** before commit.
- **Image pins:** accepted running digests pinned for Calibre-Web, Geo Activity
  Playground, Heimdall, Overseerr (batch 1); CouchDB `busybox` init, NZBGet,
  Protonmail `socat` sidecar, Spottarr (batch 2); Endurain, Velomate ingestor and
  the nested Ducati-monster manual app (batch 3, via a narrow Kustomize `images:`
  override on the nested source, rendered privately); Tailscale operator and
  proxy images (batch 4, via chart `operatorConfig.image` and
  `proxyConfig.image` digest values on the HelmRelease — proxy identity/routing
  otherwise unchanged).
- Provenance: accepted digests were verified against registry manifest bodies
  **51/51** with existing scoped remote credentials held in memory only. Private
  GHCR and the local Protonmail `Never` image were never exported or rewritten.
- Live result: guard now reports **0 unpinned Always references and 0 broad chart
  constraints**, with **59/59 pods Ready**, **43/43 Flux resources Ready**,
  **7 Bound PVCs**, **22 routes**, ingress **10.42.0.193**, Sonarr/Radarr
  versions unchanged, and every originally accepted running/completed-init image
  digest byte-identical to the pre-pin baseline. Tailscale `ts-nginx-ip` connector
  remains `ConnectorReady` advertising `192.168.1.201/32`; all 5 proxy pods Ready
  on the pinned digest.
- Image automation remains intentionally suspended
  (`ImageUpdateAutomation/flux-system/apps`, `suspend: true`) so Foodbot/
  WrenchMate tag Setters cannot overwrite the pins during maintenance; it must be
  restored after acceptance. No newer code/app/chart was introduced.

## Independent code-review findings and fixes (2026-10-09)

A second, independent, read-only reviewer raised two material findings. Both are
fixed and covered by offline regressions; none of the changed branches has run
against the live host yet.

**Finding #1 (HIGH) — synchronous checkpoint stop/copy/start had no bounded
deadlines; a stalled copy/start or lost SSH while k3s was stopped could leave the
control plane down with no automatic restart.** Fixes:

- All intentional `systemctl` requests now use `no_block` + bounded `async/poll`
  with `systemctl show` ActiveState/MainPID confirmation loops (checkpoint stop,
  resume, upgrade handler restart, bootstrap start).
- Capture is wrapped in a host-local **SIGALRM deadline** (60 s) inside the
  Ansible-only helper, so a lost controller still cannot leave an unbounded copy;
  a partial archive stays `.partial` and never becomes `checkpoint.tar`.
- New temporary **Ansible-managed host-local safeguard**: a root-private helper +
  oneshot service + timer, armed *before* the stop with the exact original
  binary/unit SHA-256, that only ever `systemctl start --no-block k3s` the
  **unchanged** binary. It fires even if SSH/controller is lost. It refuses to act
  if the binary/unit identity changed (never a binary-only downgrade onto a
  migrated DB), is canceled atomically *before* binary promotion, and its
  units/helper are removed after acceptance. Metadata is root `0600`, lock-guarded
  and credential-free.
- The upgrade path now disarms the safeguard, then promotes the binary under a
  handler with bounded restart plus `service-ready.yaml` (active PID, node Ready,
  expected version) before Flux reconciliation resumes. A post-promotion timeout
  reports health and never restores an old DB/binary.
- `k3s_code_review_cleared` (default `false`) gates the first service pause; the
  clearance assertion is independent of the now-zero pin counts, so finishing the
  pins cannot silently bypass the review gate.

**Finding #2 (MEDIUM) — the Plex GPU acceptance helper could report
`passed=True` even when its own transcode session was not verified terminated.**
Fixes:

- `stop_owned_stream` now marks the owned session stopped only after confirming
  absence in both `/transcode/sessions` and `/status/sessions` (bounded retries);
  it never issues stops for other sessions.
- `passed` requires hardware pipeline **and** verified owned-session termination;
  a cleanup failure records `cleanup_error=owned_session_termination_unverified`,
  keeps the evidence, and exits nonzero.
- `validate.yaml` persists evidence to the private run directory (`0600`) and
  asserts `hardware`, `passed` and `own_stream_stopped` are all true.

**Local changes for this response (ansible repo, all still uncommitted):**
`roles/k3s/tasks/{checkpoint,upgrade,bootstrap,existing,validate,guard-arm,guard-disarm,service-ready}.yaml`,
`roles/k3s/templates/k3s-checkpoint-guard.{service,timer}.j2`,
`roles/k3s/handlers/main.yaml`, `roles/k3s/defaults/main.yaml`,
`scripts/k3s_checkpoint_guard.py`, `scripts/k3s_checkpoint_remote.py`,
`scripts/test_or_probe_plex_gpu_transcode.py`, and the new regressions in
`scripts/test_k3s_review_fixes.py` (plus the pins helpers
`scripts/k3s_pin_{inventory,registry_verify,render_review,validate,manual_review}.py`).

## Reproducible host implementation

- `k3s.yaml`: separate opt-in play; `homeserver.yaml` remains read-only.
- `roles/k3s/defaults/main.yaml`: apply/bootstrap/start are false by default.
- `roles/k3s/tasks/{main,existing,artifact,checkpoint,guard-arm,guard-disarm,bootstrap,service-ready,upgrade,validate}.yaml`
  and `handlers/main.yaml`: builtin modules, per-hop binary/checkpoint gates,
  deadline-bounded service operations, independent host-local unchanged-binary
  safeguard, bounded post-promotion readiness, one binary restart handler and
  original Flux suspension restoration.
- `roles/k3s/templates/k3s.service.j2`: reviewed new-host flags and native settings;
  `k3s-mountcheck.py.j2`: boot-time exact UUID/RW gate for new-host service.
- `inventories/production/group_vars/homelab.yaml`: explicit desired version,
  exact hashes, original unit hash and six UUID mounts.
- `scripts/k3s_checkpoint_guard.py` and
  `roles/k3s/templates/k3s-checkpoint-guard.{service,timer}.j2`: temporary,
  Ansible-managed host-local unchanged-binary restart safeguard (root `0600`,
  lock-guarded, identity-checked, disarmed before promotion, removed post-acceptance).
- `scripts/k3s_guard.py`: credential-free read-only inspection; raw pod env and
  Secret bodies are not returned by this helper.
- `scripts/k3s_pin_{inventory,registry_verify,render_review,validate,manual_review}.py`:
  read-only pin inventory, accepted-digest registry verification, image-only
  render gate, post-pin acceptance and nested-source render review.
- `scripts/k3s_checkpoint_remote.py`: deadline-bounded stopped WHOLE SQLite
  directory/bootstrap capture and owner-scoped cleanup/status. It cannot
  start/stop services itself.
- `scripts/k3s_checkpoint_verify.py`: Mac-only encryption/authentication through
  EOF, exact file hashes, paired binary/unit and restored SQLite integrity with
  WAL honored; no `immutable=1` shortcut on whole-directory restores.
- `scripts/k3s_validate_remote.py`: functional route/DNS/arr/PVC/image/Flux/cgroup/
  webhook/CNPG/device checks and actual thirty-minute observation. Discovers i915
  card/render nodes dynamically; no hardcoded `card0`, device permission edits,
  or new privileged workloads. Uses the existing bounded Plex transcode helper.
- `scripts/test_k3s.py` and `scripts/test_k3s_review_fixes.py`: safety,
  encrypted/WAL/negative-verification, checkpoint-deadline/safeguard-ordering
  and Plex owned-session-cleanup regressions.
- README and recovery-runbook additions distinguish host installation from app
  state recovery. All these changes remain **local/uncommitted**.

Existing upgrades preserve the original unit/env/config rather than templating
over credentials/options. Unrecognized current checksums, extra configuration,
inactive/partial installs, skipped minors or downgrades fail closed. Fresh
bootstrap requires explicit empty-host intent and reviewed mounts, installs the
exact binary/service but defaults to stopped for restoration. Ansible does not
install Flux/apps or reconstruct application data/Secrets. Rebuild/root UUIDs must
be deliberately reviewed; media UUID safety is never weakened to force execution.

## Pins and provenance

Official GitHub release API and `sha256sum-amd64.txt` fetched again at
**2026-10-09 11:11:44 UTC**, HTTP 200. Published checksum and GitHub `k3s` asset
digest agree for both destination binaries. No release binary was downloaded in
the blocked run; execution additionally checks its downloaded/transferred bytes.

| Version | amd64 SHA-256 |
| --- | --- |
| Current v1.33.11+k3s1 | `4b9201557bdca116d5d26ed70a38698e2667ac15655efe73f802119af80285fd` |
| First hop v1.34.12+k3s1 | `ef1df26b26276c0f6d962391c94e12f9362d1f1e30ec7a7926e9ddb84b0d66ce` |
| Desired v1.35.9+k3s1 | `897acb21cca57d477a211102251a6591450ce767344a9faaa121a1007ca9fa9a` |

Source pattern: `https://github.com/k3s-io/k3s/releases/download/<URL-encoded-tag>/sha256sum-amd64.txt`,
with `https://api.github.com/repos/k3s-io/k3s/releases/tags/<URL-encoded-tag>`.
Optional 1.33 patch is omitted: adjacent 1.33→1.34 is permitted and avoids an
extra restart/checkpoint. Do not jump 1.33→1.35. **1.36 remains explicitly blocked
for separate ingress/Flux prerequisite approval**, not added to these pins.

Original installed unit SHA-256 is
`40636c7e3db8010795a0f5eb266725874adb2f022e9ace54d03c697ff82c1bc6`.
Flags remain `server --data-dir /var/lib/rancher/k3s --disable=servicelb
--disable=traefik`; service env is empty/root0600, no config.yaml/drop-ins.

## Commands and actual results

```sh
.venv/bin/ansible-playbook homeserver.yaml --syntax-check
.venv/bin/ansible-playbook k3s.yaml --syntax-check
.venv/bin/ansible-lint k3s.yaml roles/k3s
.venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
.venv/bin/ansible-playbook k3s.yaml --check -e k3s_target_version=v1.34.12+k3s1
.venv/bin/ansible-playbook k3s.yaml -e k3s_apply=true -e k3s_target_version=v1.34.12+k3s1
.venv/bin/python scripts/k3s_pin_render_review.py <worktree> HEAD   # image-only render gate
.venv/bin/python scripts/k3s_pin_validate.py <stage>               # post-pin digest/readiness acceptance
```

The host-side `k3s.yaml -e k3s_apply=true` lines are recorded for when the parent
grants clearance; they have **not** been run since the pins completed.

Syntax/lint pass; check mode: **zero changes**. Authorized normal first-hop
attempt: **one status-file change, intentional isolation assertion failure**.
No later task ran. Tests are detailed in the final verification below. The
initial guard read failed because the original installer unit has a final line
continuation; normalized the parser before retrying (no host file changed).
Dry runs inspect actual existing state, not pretend target-cluster readiness.

Latest guard reconfirms `/readyz=ok`, single Ready node, **59/59 running pods
Ready**, **43/43 Flux resources Ready**, **7 original Bound PVCs**, six original
UUID mounts RW/cgroup2fs, intentional ~8 GiB swap, ingress **10.42.0.193**.
After the pins, guard pin risks are **0/0**. Current binary/unit checksums
unchanged. Root phase remains the credential-free
`k3s-blocked-image-chart-isolation` (no hop has run, so no phase/status update was
performed); historical `validated-noble` milestone retained. No post-hop
routes/GPU soak is claimed because no hop occurred.

## Checkpoint, recovery and acceptance boundaries

**No new checkpoint IDs/archives exist yet — the pins did not create any.**
Existing Mac encrypted baseline/quiesced/pre-Noble backups and age identity are
unchanged, and no k3s service pause or checkpoint capture has occurred.
No real key contents were printed or transferred; tests generated disposable
fixture identities, not production keys. Existing native app backup verification
and offline Foundry gameplay limitations remain as recorded previously.

When unblocked, each play creates its own run under
`~/homelab-backups/ryback/k3s-<UTC>-<ID>/checkpoint.tar.age` and `verified.json`.
Ansible stops k3s, proves MainPID=0/no DB descriptors, copies/fsyncs whole DB plus
matching token/TLS/cred/config/binary/inventory into root0700 staging, and always
restarts the unchanged binary before off-host transfer. Mac stage is private;
plaintext is removed only after full authenticated/hash/native SQLite verification.
Binary promotion requires that new receipt to match the current version/hash and
be <600 seconds old. This is **k3s-only consistent recovery**, not a fresh
quiesced backup of running apps/PVCs/media. No bulk-media traversal.

Cross-minor rollback requires restoring the **matching datastore + binary +
token/config/TLS/encryption material** with k3s stopped; the role rejects an
ordinary downgrade invocation. There is no automatic DB rollback or existing
`restore-k3s.yaml` command to claim tested. If needed, first decrypt/inspect the
preceding verified unit privately, then review an explicit recovery playbook:
stop k3s, preserve post-failure evidence, restore the matching DB-directory set,
bootstrap material/binary with recorded ownership/modes, fsync, start the old
version, and validate. Account for Kubernetes/PVC writes since the checkpoint.
Do not run killall/uninstall, replace only the binary over migrated DB, use an
etcd snapshot or restore unrelated legacy Plex/MCP state.

The existing-install execution path (guard → checkpoint → safeguard arm/disarm →
binary promotion → bounded readiness → Flux suspension restoration → functional
acceptance → Plex VAAPI → real soak) is now **production-executed end-to-end for
both hops** (results below). The **empty-host bootstrap** branch and a full
whole-machine/off-host restore rehearsal remain **unexecuted/unproven**; local
crypto tests are not a substitute for those. Normal final usage-cycle acceptance
remains separate; the soak is a real observation window, not an instantaneous
claim.

## Executed hops — actual results

Both hops run by the sole operator with
`k3s_apply=true -e k3s_code_review_cleared=true`, sequential, no subagents, no
reboot/drain/killall/uninstall, no new privileged jobs, no ingress/Flux-version/
app-version changes, no k3s 1.36.

### Hop 1 — v1.33.11 → v1.34.12+k3s1
- Command: `ansible-playbook k3s.yaml -e k3s_apply=true -e k3s_code_review_cleared=true -e k3s_target_version=v1.34.12+k3s1`
- Controller start/exit: first-hop controller exited **2026-10-09T13:50:18Z**;
  `PLAY RECAP ryback: ok=81 changed=29 failed=0 unreachable=0`.
- Checkpoint `k3s-20261009T131032Z-2f1aa6ae` captured **stopped** (baseline
  `v1.33.11+k3s1`, binary `4b9201…85fd`, unit `40636c…1bc6`,
  `no_datastore_open_descriptors=true`, `main_pid=0`), **87 verified regular
  files**, `sqlite_integrity=ok`, `age_authenticated_to_eof=true`,
  `encrypted_bytes≈249 MB`, encrypted Mac-side and fully re-verified.
- Safeguard armed before the stop, disarmed before promotion, units/helper removed
  after acceptance. Binary promoted only after the fresh verified receipt.
- Functional acceptance passed; real bounded Plex VAAPI transcode
  `hardware=true, passed=true, own_stream_stopped=true, segments_read=1`.
- Real ≥30-minute observation completed (async soak jid `j559149755532.119811`,
  ~30×60 s cycles) with no restart increase.

### Hop 2 — v1.34.12 → v1.35.9+k3s1
- Command: `ansible-playbook k3s.yaml -e k3s_apply=true -e k3s_code_review_cleared=true -e k3s_target_version=v1.35.9+k3s1`
- Controller exited **2026-10-09T14:34:08Z**;
  `PLAY RECAP ryback: ok=81 changed=26 failed=0 unreachable=0`.
- Checkpoint `k3s-20261009T135422Z-6756f9d6` captured **stopped** (baseline
  `v1.34.12+k3s1`, binary `ef1df2…66ce`, unit `40636c…1bc6`,
  `no_datastore_open_descriptors=true`, `main_pid=0`), **87 verified regular
  files**, `sqlite_integrity=ok`, `age_authenticated_to_eof=true`,
  `encrypted_bytes≈254 MB`, encrypted Mac-side and fully re-verified.
- Functional acceptance passed; real bounded Plex VAAPI transcode
  `hardware=true, passed=true, own_stream_stopped=true, segments_read=1`.
- Real ≥30-minute observation completed (async soak jid `j785981122014.147240`).

### Final state and convergence
- Server/node **`v1.35.9+k3s1`**, `/readyz=ok`, service `active`;
  `/usr/local/bin/k3s` SHA-256 **`897acb21…fa9a`** (target), unit SHA-256
  unchanged **`40636c7e…1bc6`**.
- Credential-free functional pass: **59/59 pods Ready**, **43/43 Flux resources
  Ready**, **7 Bound PVCs**, **22/22** routes (DNS→`192.168.1.201`, TLS, HTTP),
  Sonarr `4.0.20.3014` / Radarr `6.4.4.10685` unchanged, LAN roots 200 / API 401 /
  controlled public source classification unchanged, ingress source policy
  `Local`, trusted nginx `10.42.0.193/32`, 6 original UUID mounts RW/cgroup2fs,
  systemd cgroup driver, intentional ~8 GiB swap, guard pin risks **0/0**,
  Tailscale 5 proxies pinned + `ts-nginx-ip` `ConnectorReady`.
- Default-target convergence (target = installed `v1.35.9`): normal
  `ok=9 changed=0 failed=0`; check `ok=10 changed=0 failed=0`. `homeserver.yaml`
  syntax OK (preflight/defaults unchanged).
- `ImageUpdateAutomation` restored via narrow commit **`e809c42`**
  (`git revert` of the temporary `fc10bcc` pause) — file back to its original
  enabled state; observed `suspend=null`, run `2026-10-09T14:35:38Z`, no unpinned
  digest/chart rewritten. Foodbot/WrenchMate baselines preserved
  (`foodbot main 9b6c9de4…`, dashboard `7d173689…`, `wrenchmate main 2b7c5ef9…`).
- No active guard units/timer/helper, no active command/job, no owned transcode
  sessions (`/transcode/sessions` count 0). Root phase
  `validated-k3s-1.35`, `running_command_category=null`.

## Verification / tests
- **59 tests pass** (58 prior + 1 new `validated-*` terminal-status regression);
  16 review-fix regressions retained. `ansible-playbook k3s.yaml --syntax-check`
  passes; `ansible-lint k3s.yaml roles/k3s` production profile 0/0.

## Residual limits (honest)
- Real service 20 s stop, 60 s capture and 240 s safeguard bounds, and 600 s
  receipt freshness were exercised in production but **not** adversarially
  rehearsed on ryback; any timeout path fails the hop and restarts the unchanged
  binary (no binary-only downgrade).
- Off-host whole-SQLite recovery is **not** a full restore rehearsal; a real
  bootstrap/restore and full offline Foundry gameplay remain unproven.
- Normal post-upgrade user cycle and real off-LAN phone/Tailscale verification
  remain manual. No automatic subsequent minor; no k3s 1.36.
