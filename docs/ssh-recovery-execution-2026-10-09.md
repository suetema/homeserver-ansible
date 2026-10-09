# Approved SSH recovery — 2026-10-09

**SSH restored; all temporary recovery jobs/pods removed. OS upgrade remains
unfinished/unverified and is handed back to the parent for review.**

## Authorization and boundary

Owner explicitly approved temporary privileged host-root inspection, conditional
SSH service start and cleanup, including an emergency direct-Kubernetes exception
to the Flux GitOps policy. Read homelab-flux AGENTS.md/CLAUDE.md and the earlier
proposal in `docs/ssh-recovery-access-2026-10-09.md`. No Flux/application edits,
commits/pushes, password changes, package operations, reboot or upgrade resumption.
This was the sole live mutator.

## Execution, 09:06–09:08 UTC

Both jobs used the exact previously observed cached Alpine/socat immutable digest,
`imagePullPolicy: Never`, nodeName ryback, privileged root, hostPID, host-root mount,
no service-account token, backoffLimit 0, 60-second active deadline and 120-second
TTL. Host binaries were invoked using the reviewed chroot/Ubuntu nsenter command
with PID 1 namespaces and explicit host root/cwd. Admission, image cache and
host tools all worked; nothing installed or overridden.

| Job | Job UID | Pod / UID | Exit |
| --- | --- | --- | --- |
| `ryback-ssh-recovery-20261009-inspect` | `e0df5420-9389-4586-9b1b-a2a34d3f722f` | `ryback-ssh-recovery-20261009-inspect-zh8cz` / `badbf4fc-40e7-4b31-8f8a-02d2b6b3ae35` | 0 |
| `ryback-ssh-recovery-20261009-start` | `1e01409b-5958-42d6-8179-7a87dd27b74b` | `ryback-ssh-recovery-20261009-start-q2dwn` / `1bdfd07c-dab8-40e2-a0f6-0293c757219f` | 0 |

Inspection: ssh.service and ssh.socket both **loaded, inactive/dead, Result=success**;
neither masked; no drop-ins. Unit paths were `/usr/lib/systemd/system/ssh.service`
and `/usr/lib/systemd/system/ssh.socket`. This supported the approved start without
unmasking, configuration changes or socket-policy overrides. Removed the inspection
job/pod before proceeding.

Start command, inside host namespaces: `/usr/bin/timeout 20s /usr/bin/systemctl
start ssh.service`. Exit 0, no error output. Removed its job/pod promptly; no
privileged workload left running while waiting for SSH.

Fresh nonmultiplexed SSH to maarten@192.168.1.110 succeeded with **public-key-only**
authentication and **StrictHostKeyChecking=yes**; `sudo -n` succeeded. Read-only
checks established:

- ssh.service **active/running, Result=success**; ssh.socket remains inactive/dead.
- Service ExecStartPre `/usr/sbin/sshd -t` **exited 0** at 09:07:16 UTC. No separate
  config-test job needed; the existing unit's normal test passed.
- Host `/etc/os-release`: **Ubuntu 24.04.5 LTS**; kernel **6.8.0-138-generic**.
- Process names **dpkg** and **unattended-upgr** present. No arguments/environments
  collected and no process interrupted.
- Original root tmux **ubuntu24: 1 window** still present; no attach/send-keys.

Updated root `/var/backups/homelab-upgrade/status.json` atomically to
**ssh-restored-awaiting-upgrade-review**, retaining previous fields and appending
the prior phase to historical milestones. Added credential-free SSH recovery
evidence and explicitly marked upgrade completion unverified.

## Verified cleanup and credential handling

For each job, checked its exact UID and recovery-owner label before DELETE with
UID precondition and Background propagation. Only pods whose ownerReferences
matched that job UID and whose recovery-owner label matched were eligible for
explicit deletion, also with UID preconditions and five-second grace. Confirmed
the specific job and pods absent after each cleanup.

Final independent API check at **09:08:21 UTC**: **zero jobs and zero pods** with
`recovery-owner=ssh-recovery-20261009`; `/readyz` **200, ok**; TCP 22 reachable.

All Kubernetes requests used the existing private kubeconfig and client-cert
authentication with full CA and TLS hostname/IP verification. Original kubeconfig
unchanged. Decoded client cert/key/CA were 0600 in private TemporaryDirectories,
deleted in context-manager cleanup. No credentials, Secrets objects, host configs,
raw environments or unrelated journals printed; no backup decryption required.

## Parent handoff

Recovery is complete. Resume **review of the existing ubuntu24 transaction** through
the original OS operator, not a second upgrader. dpkg presence and 24.04 userspace
do not establish successful package completion, safe boot selection or Noble
acceptance. No reboot was requested/performed by this recovery unit.
