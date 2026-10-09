# Configuration/application-state backups to this Mac

## Scope and authorization

User authorized starting backups on 2026-10-08. The destination is this Mac;
the large attached media disk is excluded. This authorizes backup creation and
isolated verification, not OS/package upgrades, reboots, service shutdowns,
deployment changes, credential rotation, or commits/pushes.

Subsequent explicit approvals covered legacy Plex cleanup, temporary GitOps
pause/resume of the three Foundry instances and Suwayomi for clean snapshots,
and the small book-folder exceptions. Other media remains excluded. These
approvals do not authorize OS/package upgrades or reboots.

The first pass is an **online baseline**, not a fully tested whole-server
disaster-recovery checkpoint. See the dated result below and each run's
`verification.json` before relying on a backup.

## Locations

- Encrypted archives and restricted reports:
  `~/homelab-backups/ryback/<UTC-run-ID>/`.
- Private encryption identity: `~/.config/homelab-backup/ryback.agekey` (0600).
- Public recipient: `~/homelab-backups/tools/ryback.recipient`.
- Privately installed age binaries: `~/homelab-backups/tools/age-v1.3.2/`.
- Temporary server staging: `/var/backups/homelab-agent/<UTC-run-ID>/`, root-only;
  removed only after every archive is verified. Failed runs retain staging.

**Do not lose the age identity.** It is separate from the backup directory, but
currently on the same Mac. The owner should retain a separate secure copy in a
password manager or other recovery location. It is deliberately not committed,
printed, or stored in its own encrypted archive (which would be circular).

age v1.3.2 was downloaded from the official release, and its archive SHA-256 was
checked against the GitHub release asset digest. The Mac's existing zstd performs
compression. No backup software was installed on ryback.

## Archive contents and restore order

1. `host.tar.zst.age`: `/etc` excluding app-state directories, `/root`, selected
   user/home contents, `/boot`, `/usr/local/bin`, `/opt`, `/srv`, cron spool and
   k3s server/agent configuration. Raw k3s SQLite/WAL files are excluded here.
2. `applications.tar.zst.age`: application configurations and local PVC contents,
   excluding reproducible `container_cache`, `.cache`, Suwayomi browser cache, live
   PostgreSQL data directories and files covered by database snapshots.
3. `databases.tar.zst.age`: standalone SQLite snapshots at their original
   relative paths, k3s `state.db`, CouchDB data copies, Redis replication RDB,
   and PostgreSQL custom-format dumps plus globals under
   `backup-metadata/postgres/`. Also contains encrypted host/cluster inventories,
   including secret resources needed for recovery.
4. `local-recovery.tar.zst.age`: both local Git checkouts including history and
   uncommitted work, and the Mac's SOPS age key file if present at the standard
    location. Cache/dependency directories are excluded.
5. `book-exceptions.tar.zst.age` in **new normal runs**: the approved
   `/mnt/volume1/books` and `/mnt/volume1/k8s-books` contents. Their SQLite metadata
   is covered by online snapshots in `databases.tar.zst.age`, not raw live copies.

Bulk media, downloads and the rest of `/mnt/volume1` are not traversed. The two
book folders (approximately 20 MiB when approved) are explicit exceptions; the
first baseline predates that approval and has no book-exception archive. No
image cache or full boot-disk image is made.

Server-generated archives retain Linux UID/GID and file modes. Symlinks are
preserved without following them. Files on unexpected subordinate devices and
special files are skipped and reported. ACL/xattr/SELinux metadata is not captured
by the Python tar writer; review these if a restore requires more than ordinary
file permissions. Live file changes are reported rather than hidden.

For recovery, decrypt/extract into an isolated directory first. Review all paths,
permissions, manifests and excluded data before installation. Do not extract
straight onto a running server. File and database layers are separate: restore
the host/app files and then overlay standalone SQLite snapshots while the apps
are stopped; **do not restore stale WAL/SHM files over those snapshots**.

Restore PostgreSQL from logical exports into fresh compatible instances using
the matching roles/ownership. Do not restore excluded live PGDATA directories
from an online file copy. Redis recovery from the RDB requires a deliberate
decision about AOF; do not allow stale AOF data to override the restored RDB.
For k3s, restore the consistent SQLite `state.db` with its matching server token,
the recorded version/options and original local-volume mappings.

Use the newest applicable quiesced checkpoint for Foundry/Suwayomi. Do not restore
the removed legacy Plex directory or old Compose service from the initial
baseline. See [rebuild/recovery procedure](recovery-runbook.md) for layer ordering,
PostgreSQL bootstrap grantor handling and CouchDB node identity.

Do not blindly apply old firewall dumps or service settings to a newer OS.
Inventory files are recovery evidence, not an automatic installation script.

## Verification performed by the runner

- Checks every pipeline exit code, including SSH, compression and encryption.
- Keeps failed streams as `.partial`, never as a successful archive.
- Decrypts and decompresses each archive completely, including through EOF,
  validating age authentication and zstd integrity.
- Recomputes and compares SHA-256 for every regular file in server archives.
- Restores SQLite snapshots into temporary private files on the Mac, opens their
  schemas and runs `quick_check` where application extensions allow it. Complete
  standalone snapshots are opened with `immutable=1` to avoid Apple's read-only
  WAL-sidecar initialization requirement; this must never be used on live DBs.
- Parses each complete PostgreSQL dump with its producing container's pg_restore,
  without importing data into the live database. This is **not** a full isolated
  database restore test.
- Checks Redis RDB format and attempts redis-check-rdb; reports if the producing
  tool requires a seekable-file test instead of accepting a stream.
- Removes only the runner's owned remote staging directory after verification.

`verification.json` is restricted to the current Mac user. It records counts,
hashes, paths and limitations, not credential values. Native SQL globals and
cluster secret contents are retained only inside encrypted archives.

## Remaining recovery gates

- Clean Foundry LevelDB/Suwayomi H2 checkpoints now exist; world/UI/application
  restoration still needs testing. Refresh consistent checkpoints before actual
  disruptive maintenance; a successful hot tar copy is not a substitute.
- Full PostgreSQL/CouchDB isolated imports and reads now pass. Application-level
  behavior, CNPG operator reconstruction and client sync remain separate checks.
- Redis native RDB validation passed on the initial export; no full application
  Redis restart/rehydration rehearsal has been performed.
- The whole-host reinstall/restore procedure has not been rehearsed on ryback.
- The approved book exceptions are included in the newer checkpoint and future
  normal runs; other media cannot be recovered from these backups.
- Secure the encryption identity in a second recovery location.
- There is no unattended schedule or backup failure alert yet. A Mac-side runner
  depends on the Mac being awake, reachable to ryback, and having enough space.

## Repeating the backup

From this checkout, after reviewing the current scope and any live layout changes:

```sh
caffeinate -i python3 scripts/backup_to_mac.py
```

The runner requires at least 45 GiB free at startup. Each run is separate and
never overwrites a prior one. It does not implement retention deletion. Server
staging uses a run-ID ownership marker; no broad cleanup command is permitted.

Run local safety tests:

```sh
python3 -m unittest discover -s scripts -p 'test_backup.py' -v
```

## 2026-10-08 execution

- Private encryption tool/key initialized; no secrets printed.
- Six initial local safety tests passed, including encrypted restore and tamper
  detection; a browser-cache exclusion regression test was subsequently added.
- Online preparation, encrypted transfers and verification started.
- Completed run: `20261008T132448Z-ec0bde38`, under `~/homelab-backups/ryback/`.
- First attempt stopped on a locked Suwayomi browser-cache database after 26
  successful SQLite snapshots. No archive had been transferred at that point.
  The completed snapshots were retained in owned server staging, cache exclusion
  corrected, and the same run resumed without live application changes.
- The next attempt successfully transferred the encrypted database archive but
  stopped during local SQLite verification. Investigation reproduced macOS's
  read-only WAL-sidecar opening issue, not corruption: the same standalone copy
  passed with immutable read-only opening. The verifier was corrected and the
  encrypted archive rechecked without replacing it.
- Database archive authenticated and all 105 regular-file hashes matched.
  All 53 SQLite copies opened successfully; 49 passed `quick_check`, while four
  Plex databases require application-specific SQLite extensions for that check.
  The encryption/restore regression test now includes a WAL-mode fixture.
- Native Plex SQLite was then used inside the existing Plex container against
  temporary isolated snapshot copies, not its live database. Three of the four
  snapshots passed full integrity checks, including **both current PVC-backed
  Plex databases**. The old `/etc/dockerconfigs/plex/.../library.db` snapshot
  returned four malformed-entry diagnostics. Its bytes were unchanged and it is
  retained, not repaired. `plex-verification.json` records these checks.
- Follow-up inspection confirms live Plex mounts `/config` from its local PVC;
  its declared legacy hostPath volume is not the active config mount. Recovery
  must use the PVC-backed Plex snapshot, not overwrite it with the legacy copy.
- User asked whether legacy Plex state could be removed. Read-only investigation
  found approximately 3.9 GiB under `/etc/dockerconfigs/plex`; its main database
  was last written on 2026-04-20, no processes have its files open, and no Docker
  container mounts it. Active and legacy preferences have different server
  identities, names and tokens (values not recorded). Subsequent removal was
  separately authorized, as recorded below.
- Result: **verified_online_baseline**, completed successfully. Four original
  archives total **12.07 GiB encrypted**. All server regular-file hashes matched
  (105 database/export/inventory files, 1,371 host files, 96,246 app files), and
  the 1,984-file local recovery archive authenticated/decompressed successfully.
  Remote snapshot staging was removed after verification. Eight safety tests pass.
  This is not yet a fully rehearsed whole-server rebuild or an upgrade-ready gate.

### Subsequently authorized legacy Plex removal

- Updated both admin helpers to discover preferences in the current pod's mounted
  `/config` and verify the processed server identity; updated skill/runbook paths.
- Manifest-only GitOps commit `6358637` removed the stale `config-host` reference.
  Helm initially removed both entries sharing `/config` due to strategic merging;
  a one-off forced Flux reconciliation restored the desired default PVC mount.
  Original volume data was never modified/restored as part of this fix.
- Removed only Plex from dormant host/local Compose definitions. Other apps and
  unrelated repository changes preserved; tool/Compose/docs edits remain local.
- Created **additional** `legacy-plex.tar.zst.age`: **2.96 GiB encrypted**, every
  file included (also inactive raw databases/caches). All **24,671** regular-file
  hashes checked with no changed, missing or skipped paths. Immediately before
  deletion, every current file matched that archive manifest again.
- Deleted only `/etc/dockerconfigs/plex`, freeing **3.81 GiB**. Current PVC-backed
  Plex, media disk and cloud registrations preserved. Owner/Kids probes and the
  actual read-only media-prune discovery command passed after deletion; six
  helper regression tests passed. See `legacy-plex-cleanup.json` and the Flux
  task brief `docs/tasks/legacy-plex-cleanup.md` for details.
- `local-recovery-post-plex-cleanup.tar.zst.age` preserves the updated local
  checkouts/helpers/runbooks and SOPS recovery material after cleanup; its
  verification is recorded separately in `post-cleanup-local-verification.json`.

### Preparation and recovery tests after playback ended

- Read-only host Ansible preflight now replaces automatic legacy role execution.
  Check and normal runs both passed, 15 tasks and **zero changes**. Named inventory
  pins current access and exact media/root UUIDs. Syntax/lint and 20 safety tests
  pass; local Python 3.13 environment has a complete version lock.
- Isolated database restore test **20261008T200316Z-dbf5a522** succeeded against the
  original baseline. All **six PostgreSQL dumps** imported with roles/ownership,
  user tables readable and pg_amcheck passed. All **four CouchDB databases**
  started and current documents were readable. No live volumes mounted, network
  disabled inside test containers, no published ports, CPU/memory limited.
- Early test-harness failures exposed CNPG's bootstrap grantor requirements,
  tmpfs/RAM budget limitations and CouchDB's `nonode@nohost` source mode. These
  were fixed in isolated tests, not on live databases. Successful test containers
  and plaintext staging were removed; superseded failed-run staging also removed
  after the fresh successful test.
- Quiesced checkpoint **20261008T200511Z-98611d33**: pause commit **905a6d2**, exact
  original-settings restoration commit **af90c28**, both pushed and reconciled.
  Only three Foundry namespaces and Suwayomi paused. All pods were gone before
  capture; all four apps Ready again before encrypted off-host transfer.
- `databases-quiesced.tar.zst.age`: **337.8 MiB encrypted**, **4,805** regular files
  verified, no changed/missing/skipped paths. Includes clean application volumes
  and both book folders; Calibre metadata and notes SQLite snapshots both passed
  restored quick_check. Root-only staging removed after verification.
- Preparation remains distinct from upgrading: no host packages, OS/k3s versions,
  networking or boot settings changed, and no reboot performed.
- Host recovery addendum: the two Google Calendar MCP listeners use
  `/tmp/gcp-oauth.keys.json` (outside the original archive's host roots), and
  package `@cocal/google-calendar-mcp` 2.6.1. Captured that OAuth client file and
  four npm/node launcher/listener command/environment records **only inside**
  encrypted `host-mcp-addendum.tar.zst.age` in the quiesced run directory. Archive
  authenticated/hash-verified, staging removed, no credential values displayed.
  Future normal backups include the file and private process recovery records.
  Reboot startup/restart procedure is still untested.

### Follow-up application recovery checks

See [recovery procedure](recovery-runbook.md#additional-application-checks-2026-10-08).
Foundry's native ClassicLevel implementation read all **83 stores / 38,711
records** across the three restored copies; HTTP servers started. Main has two
world descriptors, Hans/Rogier zero, matching the live counts. This proves native
database readability, **not** playable-world recovery.

Suwayomi's restored application queried H2 successfully: library counts **0
mangas / 1 category / 0 chapters**, matching the live server. A separate native
read-only H2 SQL export passed for all **15 tables**. Redis loaded the preserved
RDB and responded to commands (zero db0 keys). All used isolated copies, no
published ports or live-volume mounts; temporary containers/staging removed.

Focused Foundry probe confirmed the clone reaches `/license`, while live
instances reach `/auth`. The owner chose to keep testing offline; **full world
launch remains unverified**, with no external licensing action or live license
changes. Encrypted diagnostic evidence retained; no plaintext test stage left.
The original baseline's `upgrade_ready: false` remains unchanged. CNPG operator
reconstruction, hardware boot recovery and the MCP restart procedure are not
proven by these application/database tests. Local helper/runbook changes remain
uncommitted; no new deployment changes were pushed for these checks.
