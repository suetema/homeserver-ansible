# homeserver-ansible

Host-only preparation for **ryback** (`192.168.1.110`). Kubernetes applications
belong to the separate `homelab-flux` repository.

As of 2026-10-09 these Ansible paths completed reviewed host maintenance: ryback
runs **Ubuntu 24.04.5 LTS** (kernel **6.8.0-146**) with **k3s v1.35.9+k3s1**.
The OS and k3s transitions each used fresh encrypted checkpoints and are recorded
under `docs/` (see the linked execution records below).

## Safe default

`homeserver.yaml` now performs **read-only preflight checks only**, including
hostname, OS/Python compatibility, exact disk UUIDs, free space, k3s token
presence and Kubernetes readiness. It does not install packages, stop services,
change network/boot settings, upgrade software or reboot.

The historical `common`, `docker`, `compose` and `nfs-client` roles are deliberately
not included. Do not invoke them against this server: their old time/DNS/power
settings and obsolete applications need separate review. The old Compose files
are historical, not the current application deployment mechanism.

## Controller setup and checks

Use Python 3.13 on this Mac in an isolated environment:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/ansible-playbook homeserver.yaml --syntax-check
.venv/bin/ansible-lint homeserver.yaml roles/preflight
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

The controller is pinned to ansible-core 2.19 (`requirements-dev.lock`), resolved
and tested on 2026-10-08 for the transitional Ubuntu 20.04 / Python 3.8 target.
ryback has since moved to Ubuntu 24.04 (Python 3.12); adopting a newer supported
core is a separate, reviewed change. Only builtin modules are used; no external
Ansible collections are needed for this preflight.

SSH keys and sudo access must already work. SSH host-key checking remains enabled.
After authorization, the same read-only checks work in check mode and normally:

```sh
.venv/bin/ansible-playbook homeserver.yaml --check
.venv/bin/ansible-playbook homeserver.yaml
```

The default inventory is `inventories/production/hosts.yaml`. The old `hosts` INI
file is updated as a compatibility alias. Never use an unreviewed inventory or
change disk UUID assertions merely to bypass a failure.

## Maintenance and recovery

- [Staged update plan](docs/update-plan.md)
- [Audit](docs/update-audit-2026-10-08.md)
- [Ubuntu 24.04 upgrade record](docs/ubuntu-24-upgrade-2026-10-09.md)
- [k3s 1.35 upgrade execution](docs/k3s-upgrade-execution-2026-10-09.md)
- [Encrypted Mac backup runbook](docs/backup-runbook.md)
- [Rebuild/recovery procedure](docs/recovery-runbook.md)

Actual mutating host roles, release upgrades, application pauses, reboots and
GitOps pushes still require their own reviewed scope. Do not treat successful
preflight or check mode as proof that an OS upgrade is safe.

## Explicit pinned k3s host playbook

`k3s.yaml` / `roles/k3s` is a separate, opt-in host installation/one-hop upgrade
path using builtin modules and official SHA-256-pinned amd64 binaries. Production
desired state is **v1.35.9+k3s1**; existing **v1.33.11+k3s1** must first traverse
**v1.34.12+k3s1**. No floating installer/channel, default app/legacy role revival,
drain, killall, uninstall or reboot. Existing service/config/token are preserved;
an unfamiliar configuration/checksum stops the play rather than resetting it.

```sh
.venv/bin/ansible-playbook k3s.yaml --syntax-check
.venv/bin/ansible-lint k3s.yaml roles/k3s
.venv/bin/ansible-playbook k3s.yaml --check -e k3s_target_version=v1.34.12+k3s1
# Explicitly authorized execution, ONE hop per command:
.venv/bin/ansible-playbook k3s.yaml -e k3s_apply=true -e k3s_target_version=v1.34.12+k3s1
# Only after first-hop acceptance and actual >=30-minute observation:
.venv/bin/ansible-playbook k3s.yaml -e k3s_apply=true
```

**2026-10-09 execution completed on ryback: v1.33.11 → v1.34.12 → v1.35.9+k3s1**,
one authorized hop per invocation (`k3s_apply=true`, `k3s_code_review_cleared=true`),
each with a fresh encrypted stopped-SQLite checkpoint, bounded acceptance and a
real ≥30-minute observation. Checkpoints `k3s-20261009T131032Z-2f1aa6ae` and
`k3s-20261009T135422Z-6756f9d6` were encrypted and fully re-verified on the Mac.
Final state: node **v1.35.9+k3s1**, `/readyz=ok`, **59/59 pods Ready**, **43/43
Flux resources Ready**, **7 Bound PVCs** and **22** DNS/TLS/HTTP routes, with
image/chart isolation risks **0/0**. No newer app code, reboot or k3s 1.36 was
introduced; the GitOps isolation pins were deployed separately, so Ansible did
not become a second application-spec authority. See
[execution record](docs/k3s-upgrade-execution-2026-10-09.md) for exact scope,
verification and limitations. Check mode inspects only: it does not exercise
the checkpoint or simulate a running target cluster.

On a reviewed **empty new host**, after manually establishing Ubuntu 24.04/SSH,
sudo and all six UUID mounts (review new root/boot UUIDs, never bypass media UUID),
`-e k3s_apply=true -e k3s_bootstrap=true` installs the pinned binary and reviewed
service/mount guard but **defaults to stopped**. Restore datastore/token/TLS,
Secrets and PVC/application files separately. Starting an intentionally empty
new cluster additionally needs `-e k3s_start_bootstrap=true`; installation is not
application-state recovery. Whole-host bootstrap/recovery has not been rehearsed.
