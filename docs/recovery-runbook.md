# ryback rebuild and recovery procedure

**Status:** Written from verified live inventory; software database restores
tested in isolation. Whole-server reinstall, hardware boot and GPU recovery
have **not** been rehearsed. This is not an instant rollback disk image.

## Before permitting OS/boot maintenance

Owner has accepted sequential in-place Ubuntu 20.04 → 22.04 → 24.04 and confirms
they have the backup key (2026-10-08). Independent off-Mac key storage is not
explicitly confirmed. Recovery USB is planned if needed, not prepared/tested;
avoid treating possession of instructions as proof of bootable recovery media.

1. Keep this Mac awake, with SSH connectivity, sufficient space and verified
   encrypted archives. Do not count an unfinished or `.partial` archive.
2. Store a separate secure copy of `~/.config/homelab-backup/ryback.agekey` in an
   owner-controlled recovery location. Its loss makes the archives unusable;
   another encrypted copy requiring the same key is not sufficient.
3. Confirm a bootable Ubuntu recovery/install USB, working display/keyboard,
   and physical emergency access. The agent works remotely, but cannot recover a
   nonbooting machine over SSH without an out-of-band console or human help.
4. Agree on reinstall versus sequential in-place LTS upgrades and the residual
   lockout risk. Never assume downgrading packages reverses an OS upgrade.
5. Take a fresh consistent datastore/application checkpoint before each
   disruptive transition. Preserve the matching k3s server token and binaries.

## Verified machine/storage identifiers

**Current host after authorized upgrades (2026-10-09):** Ubuntu **24.04.5 LTS**,
maintained **6.8.0-146-generic**, k3s **v1.35.9+k3s1**, same UUID storage/PVCs.
Six mounts, SSH, cluster/app access, MCP and real Plex VAAPI pipeline validated.
Boot policy now explicitly uses the new distro kernel with an eight-second GRUB
menu; working Jammy 6.8.0-138 kernel/initrd and older fallback entries retained.
Noble SSH is socket-activated (`ssh.socket` enabled); do not mistake disabled
service autostart for disabled access. See the dated upgrade execution record.

- Hostname: `ryback`; current SSH address: `192.168.1.110`; user: `maarten`.
- Existing root: UUID `badcfde0-9b10-4f96-8684-f2baba24b223`, currently `/dev/sdb5`.
- Media: UUID `8bf25db0-ca04-4c96-b91e-07d3458f4021`, ext4 at `/mnt/volume1`,
  currently `/dev/sda1`. **Device letters are not permanent identities.**
- Original pre-upgrade boot used UEFI, separate `/boot`, and a GRUB first menu
  entry selecting `/vmlinuz-5.18.0-051800rc1-generic`; this unmanaged default was
  replaced during the upgrades. Current boot/kernel policy is recorded above.
- k3s recovery version: baseline `v1.33.11+k3s1`, current installed
  `v1.35.9+k3s1`; SQLite datastore, data directory `/var/lib/rancher/k3s`.
- Verified service flags: `--data-dir /var/lib/rancher/k3s --disable=servicelb
  --disable=traefik`. Consult the encrypted service/host inventory for all exact
  environment/options rather than assuming this summary is exhaustive.

Boot/root UUIDs will change after a fresh reinstall. Review/update inventory
assertions after verifying the new disks; never bypass a media-UUID mismatch.

## If the host fails to boot or loses remote access

1. Stop automated follow-on work. Try the known-working GRUB fallback from the
   local/out-of-band console; do not repeatedly upgrade or regenerate boot files
   blindly. Check storage mount failures before trying application repairs.
2. If reinstall is required, identify the boot disk physically/by UUID and
   **preserve the media disk**. Prefer disconnecting the media disk during disk
   selection if feasible, or verify the installation target explicitly before
   any formatting. No whole-media-disk backup exists.
3. Install the chosen supported Ubuntu release on the boot disk only, establish
   hostname/network/SSH and user access, and validate remote connectivity before
   continuing. Do not blindly restore old apt repositories, network settings or
   firewall dumps onto a different OS.
4. Mount the preserved media disk at `/mnt/volume1` by its original UUID and
   verify it is a real mount, not an empty directory on root. Preserve ownership.

## Decrypt and inspect backups on the Mac first

```sh
~/homelab-backups/tools/age-v1.3.2/age -d \
  -i ~/.config/homelab-backup/ryback.agekey \
  ~/homelab-backups/ryback/<run>/applications.tar.zst.age \
  | zstd -d -c | tar -tf -
```

For extraction, use a private empty staging directory, not the Mac/server root.
Check every pipeline exit code, manifests, paths, permissions and hashes. Do not
decrypt secrets into Git, world-readable locations, or command output. The
age identity itself never needs to be copied onto ryback.

## Restore application and cluster layers deliberately

1. Restore selected host configuration and prerequisites, not the obsolete
   Compose stack. Use the latest post-cleanup local checkout/recovery archive.
2. Restore app-file/PVC contents to their recorded paths while applications are
   stopped. Original local-volume directory names and claim mappings matter.
   Preserve Linux UID/GID and modes; ACL/xattr recovery needs separate review.
3. Overlay **consistent SQLite snapshots** at their original relative paths.
   Remove stale WAL/SHM/journal files in the isolated restore destination before
   starting the corresponding app. Use newest applicable quiesced Foundry/H2
   checkpoint instead of an earlier hot file copy.
4. Install the matching k3s recovery binary/options without automatically
   starting the service. Restore its matching token and SQLite `state.db` with
   the server stopped. Do not restore old live WAL sidecars or run etcd-snapshot
   instructions against this SQLite cluster. Follow the version-specific k3s
   datastore recovery documentation before starting it.
5. Restore PostgreSQL into fresh compatible-major instances from custom dumps
   and globals, not online PGDATA copies. CNPG globals use the original `postgres`
   bootstrap grantor: reuse that bootstrap identity and skip only its redundant
   `CREATE ROLE postgres;` statement. Keep ALTER ROLE, other roles and grants.
   Restore using `pg_restore --exit-on-error` and verify tables/indexes.
6. Restore CouchDB from the preserved append-only files using the matching
   image/configuration and original node mode. This source uses `nonode@nohost`
   (no distributed-node flag); imposing a new NODENAME breaks shard routing.
   Confirm `_all_dbs` and reading each database's documents before allowing sync
   clients to reconnect. Do not overwrite newer client changes unknowingly.
7. Redis recovery requires deliberately choosing RDB versus AOF; do not let a
   stale AOF override the preserved replication RDB.
8. Restore SOPS/Flux access from the encrypted recovery material, then allow
   GitOps reconciliation only once required volumes/state are ready. An
   unattended initial app deployment can initialize empty databases on wrong
   mounts. Keep external writes/sync paused until recovery validation passes.
9. Validate SSH, disks, node/PVC mapping, Flux/Helm readiness, DNS/TLS, Plex and GPU,
   arr apps, Home Assistant, Foundry worlds, Suwayomi, Obsidian and fitness apps.
   A DB integrity check does not replace an application-level test.

### Important baseline exclusions and superseded state

- The original baseline includes legacy `/etc/dockerconfigs/plex` and dormant
  Compose configuration from before cleanup. **Do not restore that legacy path
  or resurrect its service.** Active Plex must use its recorded PVC and current
  database snapshot; its old Docker library database has malformed entries.
- Bulk media/downloads remain excluded. The separately authorized small book
  folders are an exception, with consistent Calibre metadata snapshots.
- The two Google Calendar MCP listeners on ports 3500/3502 run from user login
  sessions, not identified system services. Package/cache contents are
  reproducible (`@cocal/google-calendar-mcp` 2.6.1). Their client OAuth file lives
  at `/tmp/gcp-oauth.keys.json`, outside the initial backup scope; it and four
  launcher/listener process command/environment records are now captured in the
  encrypted `host-mcp-addendum.tar.zst.age` alongside the quiesced checkpoint.
  New normal backups include them and refuse silent credential omission while
  MCP processes are active. Restore credentials privately (0600), preferably
  under durable user configuration, and adjust `GOOGLE_OAUTH_CREDENTIALS` before
  recreating the saved launch commands. Do not print those raw commands or
  credential files. Automatic startup/restart behavior remains untested; do not
  assume these user-session processes auto-start after reboot.

## Evidence and remaining proof

The initial encrypted baseline contains 53 SQLite snapshots. All open;
49 generic checks passed and native Plex checks passed for both active DBs.
All six PostgreSQL dumps were fully restored in disposable isolated containers,
their user tables read and pg_amcheck passed. All four CouchDB databases started
and documents were readable. These tests did not mount live application volumes,
publish ports or change live databases.

Quiesced Foundry/Suwayomi and book checkpoint evidence is recorded separately.
Suwayomi/H2 application reads and native export now pass (below). Full Foundry
gameplay is deliberately deferred after the offline licensing limitation was
identified. CNPG operator reconstruction and whole-machine boot/GPU recovery
remain untested. Owner confirms key possession; recovery USB is still planned,
not prepared. No OS/package upgrade or reboot is authorized by these tests.

### Additional application checks, 2026-10-08

Application test run `20261008T204601Z-6b8fdf4e` reopened the quiesced backups
using the matching Foundry/Suwayomi image digests in network-disabled disposable
containers. Foundry's reproducible runtime was copied read-only from the ready
pod, without copying its live application data. All 83 ClassicLevel databases
were iterated using Foundry's own Node/native LevelDB implementation:

| Instance | Stores | Records read | World descriptors | HTTP |
| --- | ---: | ---: | ---: | ---: |
| Main Foundry | 57 | 27,879 | 2 | 200 |
| Hans | 13 | 5,416 | 0 | 200 |
| Rogier | 13 | 5,416 | 0 | 200 |

The zero-world counts for Hans/Rogier also match lightweight live checks; they
are not missing world descriptors introduced by restoration. HTTP startup alone
does not prove authenticated setup access, gameplay or world migrations.

Deeper run `20261008T211159Z-7b41674a` reopened Suwayomi's H2 copy and queried its
library through the actual application API: zero library mangas, one category,
zero chapters, matching the live read-only check. Native H2 check
`20261008T211644Z-d78ea764` then performed a full SQL export using the image's own
`org.h2.tools.Script`, opening the original snapshot read-only with `IFEXISTS`.
All 15 table definitions exported. H2 uses the empty/default database username,
not `sa`; this was corrected only in the test harness. Native SQL stayed private
and was removed with test staging. Successful test containers/plaintext removed.

#### Foundry world launch: explicitly unverified

Both older world copies failed to reach a playable join page in the offline
clone. Focused probe `20261008T211944Z-00faa5f5` confirmed the clone redirects
`/` and `/setup` to `/license`; `/join` returns an error page. Live instances
still redirect `/` to `/auth` normally. An HTTP 200 alone had masked this
distinction in the initial startup check.

Foundry's license signing uses its service identity, so a signature valid for
the live instance need not validate in a new isolated container. No license
validation request, EULA submission, license-file editing or signing/bypass was
performed. The owner explicitly chose **keep the test offline**, rather than
authorize contacting the licensing service. Database iteration passes, but
world launch, gameplay, client modules and core-12-to-14 migration are **not
proven**. Do not mark this deferred check as passed or call it database corruption.
Account for legitimate license validation when restoring onto a new instance.

Probe logs/results were preserved only in encrypted, authenticated,
hash-verified `world-probe-diagnostics-20261008T211944Z-00faa5f5-verified.tar.zst.age`.
Probe containers and root-only plaintext staging were removed afterward.

Redis test `20261008T211327Z-f0e555d6` loaded the preserved native RDB in the matching
image with AOF disabled, finished loading and answered commands. DB 0 contained
zero keys. The restored snapshot is a cache baseline, not retained job payloads;
live Endurain/Redis state was never mounted. Test container/staging removed.

The repository's CNPG manifest creates one fresh instance, database/owner
`home-assistant`, and its application Secret. A rebuild must restore that Secret
before client reconnection, and must not reuse the dead cluster's PVC contents
as though an online PGDATA copy were consistent. Bootstrap the empty cluster,
then restore the verified logical dump using its recorded roles/ownership.
Operator-generated/bootstrap roles must not be blindly recreated twice.
Database recovery has been demonstrated; rebuilding the CNPG operator and its
Kubernetes resources has not been exercised in a separate cluster. Doing that
on the production cluster would change live Kubernetes state and is not part
of these non-disruptive checks.

## Pinned Ansible k3s host installation — 2026-10-09

Use `k3s.yaml` / `roles/k3s`, not a floating installer or retired host Compose
roles, for the reviewed Ubuntu 24.04 installation. Production desired pin is
**v1.35.9+k3s1**, now installed after the explicitly authorized sequential hops
v1.33.11 → v1.34.12 → v1.35.9; the blocked first-hop attempt performed no
mutation.

Explicit empty-host bootstrap defaults to an installed but disabled/stopped
service; verify all six UUID mounts before installation and again before start.
The new-host service has a UUID/RW boot guard, disabled Traefik/ServiceLB and the
original data-dir; existing upgrades preserve the installed unit byte-for-byte.
After a real hop, use that hop's encrypted `k3s-<UTC>-<ID>/checkpoint.tar.age`
and `verified.json` on the Mac, not a generic older binary over migrated SQLite.
The checkpoint retains the **whole stopped DB directory**, including any paired
WAL/SHM, and matching token/config/TLS/cred/binary. Restore those as a unit; the
older standalone SQLite backup-API archives have different WAL overlay rules.

This is control-plane recovery only. Apps continue running/writing while k3s is
stopped. PVC/application recovery still uses the separately verified native/
quiesced backups and original mappings. The blocked first-hop attempt created no
checkpoint; each executed hop produced a verified encrypted one, and previous
encrypted backups remain untouched. Never claim
fresh installation regenerates old applications, data or Secrets. A cross-minor
restore requires a separately reviewed Ansible recovery playbook; the upgrade
play deliberately rejects downgrades and does not implement automatic DB rollback.
