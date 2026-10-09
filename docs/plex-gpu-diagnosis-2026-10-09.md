# Plex GPU acceptance blocker — 2026-10-09

**Subsequent execution:** owner approved deployment; fix and real hardware
transcode acceptance now pass. See `docs/plex-gpu-fix-2026-10-09.md`. The
diagnosis/proposal below preserves the earlier pre-approval evidence boundary.

## Outcome / approval boundary

**Root cause established with high confidence: the Plex container's cgroup-v2
device filters reject DRM character major 226. `/dev/dri` is only a hostPath
bind mount, not a Kubernetes allocated device.** File visibility does not confer
device authorization. Two independently attached BPF device programs reject it.

No fix deployed, Plex restart, new container, package install, runtime/security
policy change, reboot, commit/push, PVC/config/media write, or cloud change.
Only credential-free `/var/backups/homelab-upgrade/status.json` was updated on
the host, preserving its existing checkpoint/version fields. Local additions
are this document and `scripts/test_or_probe_plex_gpu.py`; Flux files and other
agents' documents were not edited. Temporary local rendering files were removed.

**Stop before Ubuntu 24.04 until fixed and validated, or explicitly deferred by
the owner.** There was no actual pre-upgrade device-open/hardware-transcode
baseline, so this is not proof that a previously working transcode regressed.
The cgroup-v1 → v2 transition may expose the pre-existing hostPath-only design.
Dormant Docker Compose v1/Python breakage is separate and nonblocking.

## Feedback loop and reproducible failure

Run from `homeserver-ansible`:

```sh
python3 scripts/test_or_probe_plex_gpu.py
```

The stdlib-only coordinator sends Python over SSH without installing/writing it
on the host. Host probes use native `os.open(O_RDWR|O_CLOEXEC)`; pod probes use
Perl's native `sysopen(..., 2)` as root and `runuser -u plex`. Descriptors close
immediately; no bytes, ioctls or config changes. A forked host child drops to the
exact pod Plex UID/GID/supplementary groups. Exit 1 reproduces the blocker; exit
0 requires every host and pod open to pass. Two consecutive runs reproduced it.

| Context | Credentials | card0 | renderD128 |
| --- | --- | --- | --- |
| Host root | UID/GID 0, group 0 | PASS | PASS |
| Host Plex-equivalent child | UID/GID 1000, groups 44/100/109/1000 | PASS | PASS |
| Existing pod root | UID/GID 0, group 0 | errno 1 EPERM | errno 1 EPERM |
| Existing pod Plex | UID/GID 1000, groups 44/100/109/1000 | errno 1 EPERM | errno 1 EPERM |

Host and pod reference the **same inodes**: card0 inode 412, device **226:0**,
owner 0:44, mode 0660; renderD128 inode 411, device **226:128**, owner 0:109,
mode 0660. Pod group 109 is named `video2`, not `render`; numeric membership is
what matters, and it is correct. More groups or chmod would not fix EPERM.

## Ranked hypotheses, predictions and results

The ranked list was stated after building/reproducing the loop and before
instrumenting the cause:

1. **Container cgroup-v2 filter:** predict OCI/BPF rules omit major 226 despite
   visible hostPath. **Confirmed by OCI, systemd scope and both BPF programs.**
2. **AppArmor/seccomp:** predict syscall filtering or device-path denial evidence.
   Seccomp is **off** (`Seccomp: 0`, zero filters; OCI seccomp null). Default
   `cri-containerd.apparmor.d` is enforced; current-boot kernel journal has no
   AppArmor DENIED. No AppArmor policy alteration was needed to explain failure.
3. **UID/groups/DAC:** predict credential-equivalent host failure or different
   inodes/permissions. **Falsified by native host/pod differential.**
4. **Mount/driver:** predict different devices, `nodev`, missing i915, or host
   failure. **Falsified for this open blocker.** Both sysfs nodes bind to i915;
   actual device opens on the host work, including the non-root equivalent.
5. **Ancestor systemd restriction:** predict inherited cgroup device filters.
   **Falsified:** no attached filters in the pod slice, QoS slice, kubepods slice
   or cgroup root. The denial is in Plex's own container scope.

## Live runtime proof

Observed state: Ubuntu **22.04.5**, kernel **6.8.0-138-generic**, k3s
**v1.33.11+k3s1**, bundled containerd **2.2.3-k3s1.33**, unified cgroups/systemd.
All application changes remain out of scope; previous acceptance established
58 running pods and 43 Flux resources Ready.

- Pod: `plex/plex-plex-media-server-0`, UID
  `4576284f-8c12-4e9f-8f6d-f66002874148`; container
  `df36e2155533e58e2376a62ee0ee5b1f19c5f8af5a0eeb354c9f602dbdd2324c`, PID 10980
  at inspection. IDs/PID/BPF IDs are boot/container-instance specific.
- Pod security context `{}`, container security context unset, resources `{}`;
  unprivileged. Original image `plexinc/pms-docker:1.43.4.10903-e5521bd8c`.
- CRI `info.runtimeSpec.linux.devices` absent. OCI resources device rule is
  `[{"access":"rwm","allow":false}]` (deny-all baseline); runc supplies ordinary
  container device exceptions, **not DRM**.
- OCI `/dev/dri` bind options `rbind,rprivate,rw`. Actual mountinfo:
  devtmpfs, same host filesystem 0:5, `/dri` mounted `/dev/dri`, `rw,relatime`;
  **not nodev**. The nodev cgroup mount is unrelated to DRM device access.
- Container scope:
  `/sys/fs/cgroup/kubepods.slice/kubepods-besteffort.slice/`
  `kubepods-besteffort-pod4576284f_8c12_4e9f_8f6d_f66002874148.slice/`
  `cri-containerd-df36e2155533e58e2376a62ee0ee5b1f19c5f8af5a0eeb354c9f602dbdd2324c.scope`.
- `systemctl show <scope>`: **DevicePolicy=strict**. DeviceAllow includes normal
  char devices 1:3/5/7/8/9, 5:0/2, 10:200 and 136:*; wildcard char/block entries
  allow **mknod only**, not read/write. No DRM entry.
- `bpftool -j cgroup show <scope> effective` returns **308 and 312**, both
  `cgroup_device`. Direct attachment is on this scope, not an ancestor.
- `bpftool prog dump xlated id 308` and `... id 312` show matching allowlists.
  Character-device requests for major 226 and read/write access match none;
  program 308 reaches instruction 51 `r0=0`, program 312 reaches instruction
  62 `w0=0`, then exits. Both deny this operation. cgroup-v2 device rejection
  returns **EPERM**, even to container root with correct file permissions.
- `k3s.service`: DevicePolicy=auto, no DeviceAllow, Delegate=yes, own cgroup
  `/system.slice/k3s.service` (not Plex's ancestor).
- Intel GPU plugin is **not deployed**: no plugin pod, no GPU allocatable
  resource on `ryback`, and `/var/lib/kubelet/device-plugins` only has kubelet.sock.
  No repo Intel/device-plugin configuration found. `bpftool` and `strace` were
  already available; no packages installed. No strace attachment was necessary.

This proves a sufficient immediate blocker. Only post-fix hardware transcoding
can establish that there are no subsequent media-library/settings limitations.

## Minimal durable fix proposal — NOT authorization to apply

Use Kubernetes device allocation: **one standalone Intel GPU device-plugin
DaemonSet on ryback, then request one `gpu.intel.com/i915` for Plex**. No Intel
operator, NFD, driver install, firmware, kernel flags, generated containerd edits,
AppArmor disabling, global device exception or privileged Plex required.

Reviewed official upstream release **v0.37.1** (published 2026-10-02), whose
standalone manifest pins `intel/intel-gpu-plugin:0.37.1`, defaults to one consumer
per GPU, drops all capabilities, disables privilege escalation, uses a read-only
root filesystem and RuntimeDefault seccomp, and is **not privileged**. Its host
DRM/sysfs mounts are read-only. Its writable kubelet device-plugin socket and
CDI directory mounts are **security-sensitive host integration**: deploying it
requires explicit parent/owner review, even though it is not privileged.
No unsafe disposable test container or temporary BPF exception was run.

### Exact proposed Flux edits

New `homelab-flux/apps/base/intel-gpu-plugin/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: kube-system
resources:
  - https://raw.githubusercontent.com/intel/intel-device-plugins-for-kubernetes/v0.37.1/deployments/gpu_plugin/base/intel-gpu-plugin.yaml
patches:
  - target:
      group: apps
      version: v1
      kind: DaemonSet
      name: intel-gpu-plugin
    patch: |-
      - op: add
        path: /spec/template/spec/nodeSelector/kubernetes.io~1hostname
        value: ryback
```

Add `- ../base/intel-gpu-plugin` to `apps/prd/kustomization.yaml` resources.
Alternatively vendor this exact release manifest alongside the new Kustomization
for reproducibility without a remote build dependency; no operator/CRDs needed.

In `apps/prd/plex-values.yaml`, pin the **existing** chart version to `"1.9.0"`
instead of `">=1.5.0"` to prevent incidental chart upgrades, and add:

```yaml
spec:
  values:
    pms:
      resources:
        limits:
          gpu.intel.com/i915: 1
        requests:
          gpu.intel.com/i915: 1
```

**The field is `values.pms.resources`, not `values.resources`.** Keep every
existing image, other value, volume and mount unchanged in this minimal fix.
The existing `/dev/dri` directory bind may stay: allocation supplies the missing
device allowlist. Merely changing this mount or adding supplementary groups
cannot grant authorization. Removing the now-redundant hostPath can be a later
separately reviewed cleanup, not a prerequisite.

Offline verified the exact official chart 1.9.0 tarball SHA-256
`d6b026d8ddb212d496b6aae5f23f4168506211df24bc1588ec79928309a27ff6` against its
index, and ran before/after `helm template` with existing repo Plex values.
**Only the five resource-block lines were added in rendered manifests**;
image, PVC template, `/config`, network and other mounts unchanged.
Offline Kustomize render of the tagged plugin manifest plus the proposed
namespace/node-selector overlay passed: exactly one DaemonSet, kube-system,
ryback only, pinned image, no privileged container. This did not contact the
cluster. Remote-fetch availability in Flux and live plugin discovery remain
deployment acceptance checks, not claimed as tested.

### Approval, rollout and rollback

Parent must obtain reviewed GitOps deployment/commit/push approval covering:
the new host-integrated plugin, GPU allocation to Plex, and **one Plex restart**.
No existing approval here allows those changes.

Prefer two stages: (1) plugin only; wait for DaemonSet Ready and node allocatable
`gpu.intel.com/i915: 1`; (2) Plex resource edit, render/review and allow its normal
StatefulSet rollout. Avoid applying the Plex request before the resource exists,
which would leave its replacement Pending. Preserve active PVC
`pms-config-plex-plex-media-server-0`; do not restore the deleted legacy config.

Rollback through reviewed GitOps: revert **only these approved edits**, first
remove Plex's GPU resource request and let the old workload return, then remove
the plugin. Preserve all unrelated work/PVC data. This restores today's running
but GPU-blocked configuration, not a claim of previously working transcoding.
No reboot or old-kernel selection is required to remedy device allocation.

## Post-fix acceptance (parent / authorized executor)

1. Re-run `python3 scripts/test_or_probe_plex_gpu.py`: all eight opens PASS,
   exit 0. Inspect updated OCI allocated devices and cgroup filters for 226:0
   and 226:128; Plex stays unprivileged and existing groups remain sufficient.
2. Verify Plex Ready on the same image, same active `/config` PVC and server
   identity. If credentialed checks are needed, use the Plex admin skill/helpers
   that discover ready-pod mounted Preferences.xml and verify
   ProcessedMachineIdentifier; never hardcode a retired config or expose tokens.
3. Force a real video transcode (not Direct Play/Direct Stream). Verify PMS
   session/dashboard reports hardware decoding/encoding `(hw)` as applicable
   and the transcode completes. Check logs for VAAPI/QSV device initialization
   errors; a Ready pod or successful open alone is not hardware validation.
   Do not change sharing, cloud registration, licensing or account settings.
4. Recheck normal application/Flux readiness and no new denial/OOM/I/O errors.
   Resolve any remaining media-library/PMS preference issue separately on Jammy.
   Only then mark GPU acceptance passed and review continuation to Noble.

## Sources

- [Intel GPU plugin documentation](https://github.com/intel/intel-device-plugins-for-kubernetes/blob/v0.37.1/cmd/gpu_plugin/README.md)
- [Pinned standalone GPU plugin manifest](https://github.com/intel/intel-device-plugins-for-kubernetes/blob/v0.37.1/deployments/gpu_plugin/base/intel-gpu-plugin.yaml)
- [Release v0.37.1](https://github.com/intel/intel-device-plugins-for-kubernetes/releases/tag/v0.37.1)
- [Official Plex chart index](https://raw.githubusercontent.com/plexinc/pms-docker/gh-pages/index.yaml)
