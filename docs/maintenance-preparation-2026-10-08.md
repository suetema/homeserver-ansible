# Maintenance preparation result — 2026-10-08

## Authorized and completed

After Plex playback ended, the user authorized starting preparation. They then
explicitly approved temporary GitOps pause/resume of only the three Foundry
instances and Suwayomi, and the two small book backup exceptions.

- Safe host-only Ansible entry point, named inventory with real disk UUIDs and
  Python-compatible isolated controller (core 2.19.14, complete dependency lock).
  Obsolete common/Docker/Compose roles retained but not executed by default.
- Syntax/lint passes; 20 safety regressions pass. Check-mode and normal preflight
  each ran 15 tasks, **zero changes/failures**. Disks and k3s readiness verified.
- Existing-metadata apt simulation: **79 upgrades, seven new packages, zero
  removals**. Includes Docker 20 → 28, containerd/firewall, GRUB, Node and updater
  changes; do not apply blindly. Metadata was not refreshed and no package changed.
- Six PostgreSQL dumps fully imported in disposable containers with roles/grants,
  table reads and pg_amcheck; four physical CouchDB databases started/read.
  Restore harness uses pinned digests, no live mounts, no published ports,
  network disabled inside containers and limited CPU/RAM. Test containers and
  successful/superseded plaintext staging removed.
- Clean checkpoint run `20261008T200511Z-98611d33`: pause **905a6d2**, original
  settings restoration **af90c28**. All four pods stopped before capture and were
  Ready again before off-host transfer. Exactly four target files committed.
- Checkpoint archive **337.8 MiB encrypted**, **4,805** regular files hash-verified,
  no changed/missing/skipped paths. Calibre metadata and notes snapshots pass.
  Approved book contents included; bulk media excluded. Owned staging removed.
- Identified both user-session Google Calendar MCP listeners (`3500`/`3502`,
  package 2.6.1). Their client OAuth file is `/tmp/gcp-oauth.keys.json`, which the
  initial backup omitted. Verified encrypted host addendum now covers it and
  four launcher/listener command/environment records. No secrets displayed or
  live files/processes changed. Future normal backups include this material.
- All three Foundry HTTP roots and Suwayomi HTTP root return 200 after restart.
  Plex, Home Assistant, CouchDB, Endurain and VeloMate pods remain Ready.
- [Recovery procedure](recovery-runbook.md) written and update/backup plans current.

## Explicitly not done

No apt installs/upgrades, OS/k3s upgrades, network/firewall or bootloader changes,
and no reboot. Foundry/Suwayomi briefly paused only under the separate approval;
other applications were not paused. Local helper/Ansible/runbook edits are not
committed/pushed; preserve and synchronize them deliberately. Only the narrow
pause/resume manifests were committed/pushed in this preparation batch.

## Before the next mutating host batch

1. Owner confirms separate secure age-key storage and bootable recovery equipment.
2. Confirm sequential in-place versus spare-SSD route and residual remote lockout
   risk; working physical recovery remains a contingency, not planned work.
3. Finalize MCP reboot-start procedure and any required app-level world/H2/CNPG
   restore checks. Clean files and DB imports do not prove every application UI.
4. Refresh/review apt changes, third-party packages and configuration prompts;
   establish a specific package maintenance scope, fresh checkpoint and window.
5. Take Ubuntu transitions one at a time. The current GRUB first kernel is still
   unmanaged `5.18.0-051800rc1`; maintain access and an explicitly reviewed boot
   selection before reboot. Unified cgroup v2 is required before the k3s 1.35 step.
