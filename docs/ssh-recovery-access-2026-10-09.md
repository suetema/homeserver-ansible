# Read-only recovery access — 2026-10-09

**Subsequently authorized and executed:** SSH restored with verified temporary
job/pod cleanup. See `docs/ssh-recovery-execution-2026-10-09.md`; the proposal and
authorization boundaries below describe the earlier read-only checkpoint.

## Result (checked 09:02 UTC)

- Existing owner-private `~/.kube/config` (0600), current context `default`, works
  against `https://192.168.1.110:6443`. Client-certificate authentication,
  kubeconfig CA trust and TLS IP/hostname validation all enabled; no insecure TLS.
- Authenticated GET `/readyz`: **200, ok**. GET nodes and pods: **200**.
  GET `/api/v1/nodes/ryback/proxy/healthz`: **200, ok**.
  This proves permission to read nodes/pods and that proxy health endpoint;
  permission to deploy privileged workloads was **not tested**.
- One node, `ryback`, Ready=True. Node-reported userspace **Ubuntu 24.04.5 LTS**,
  kernel **6.8.0-138-generic**, kubelet **v1.33.11+k3s1**, runtime
  **containerd://2.2.3-k3s1.33**. These are kubelet-reported facts, not proof that
  apt/dpkg finished, boot selection is correct, or a reboot occurred.
- 61 pods: **59 Running**, **2 Succeeded**; no continuation page. Running phase
  alone does not prove every container/application is healthy.
- TCP 6443 and Plex 32400 reachable; **22 and 1022 refuse connections**.
- No existing control sockets found in `~/.ssh` or `~/.ansible/cp`.
- No backup decryption needed. Original kubeconfig unchanged. Decoded client
  key/cert/CA existed only as 0600 files under an approved private TemporaryDirectory
  and were deleted after requests. No Secrets requests, exec, remote mutations,
  password attempts, package commands, reboot, commits or pushes.

## Parent decision required

Read `homelab-flux/AGENTS.md` and `CLAUDE.md`: live changes normally require
GitOps. **Request explicit owner approval for an emergency direct-creation
exception** for this one temporary recovery job, rather than editing production
application manifests. Alternatively obtain approval for a GitOps maintenance
job and its subsequent removal; that is slower and must not recreate a completed
recovery action indefinitely. Neither route is authorized by this check.

Explain that privileged + hostPID + a writable host-root mount gives effectively
**root authority over the entire host**, despite the narrow intended command.
No service-account token is needed. Authorization must cover inspection, then
the reviewed one-time SSH start, and deletion of only our own job/pod.

## Proposed manifest — NOT APPLIED

First run **inspection only**, review its output, and only then authorize the
one-time start below. Reuse an image already running on this node, pinned to its
observed digest; `Never` prevents an incidental image download. Admission/RBAC,
cache resolution and host-tool availability remain untested. kube-system has no
explicit Pod Security Admission labels; that does not prove admission approval.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: ryback-ssh-recovery-20261009-inspect
  namespace: kube-system
  labels:
    recovery-owner: ssh-recovery-20261009
spec:
  backoffLimit: 0
  activeDeadlineSeconds: 60
  ttlSecondsAfterFinished: 120
  template:
    metadata:
      labels:
        recovery-owner: ssh-recovery-20261009
    spec:
      nodeName: ryback
      hostPID: true
      automountServiceAccountToken: false
      restartPolicy: Never
      containers:
        - name: maintenance
          image: docker.io/alpine/socat@sha256:82ad20f6f6e29b91ff33b6662d24063522b1378f08fd8569cd3ab412cac13f50
          imagePullPolicy: Never
          securityContext:
            privileged: true
            runAsUser: 0
          command: ["/bin/sh", "-ec"]
          args:
            - >-
              exec chroot /host /usr/bin/nsenter
              --target 1 --mount --uts --ipc --net --pid
              --root=/proc/1/root --wd=/ --
              /usr/bin/timeout 20s /usr/bin/systemctl show
              ssh.service ssh.socket
              --property=LoadState,ActiveState,SubState,Result,FragmentPath,DropInPaths
          volumeMounts:
            - name: host-root
              mountPath: /host
          resources:
            requests: {cpu: 10m, memory: 16Mi}
            limits: {cpu: 100m, memory: 64Mi}
      volumes:
        - name: host-root
          hostPath: {path: /, type: Directory}
```

This uses Alpine's `chroot` to execute **Ubuntu's util-linux nsenter**, not an
assumed feature-complete BusyBox nsenter. Enter PID 1's namespaces and explicitly
its root/cwd, so host systemctl sees the host systemd and its sockets. Requires
`/usr/bin/nsenter`, `/usr/bin/timeout`, `/usr/bin/systemctl`, and functioning host
libraries/proc mount; fail closed if unavailable during package transition.
The pod's host-root view must include the host submounts. No runtime socket is
mounted or used. Do not install missing tooling or improvise pod-to-host access.

After inspection, parent may request narrowly filtered SSH service/socket journal
errors through another approved inspection job if needed; never dump unrelated
logs or credentials. Review errors and masks before proceeding. For a separately
approved job named `ryback-ssh-recovery-20261009-start`, preserve the same limits
and replace only the command after `--` with:

```sh
/usr/bin/timeout 20s /usr/bin/systemctl start ssh.service
```

No restart of networking, socket policy override, package repair, apt/dpkg kill,
password reset, tmux interruption or reboot. A timeout is not permission to kill
systemd's service job or package processes. If start fails, stop and report.
Observe fresh owner SSH access before resuming the upgrade. Remove only the
recovery job(s)/their owned pod(s), with ownership/UID verification; the bounded
deadline and TTL are additional safeguards, not a substitute for verified cleanup.

The proposal is locally reviewable only, not server-validated or executed.
Physical password reset/reboot is not a safe next step while upgrade activity
is unknown; keep the machine running and coordinate authorized recovery.
