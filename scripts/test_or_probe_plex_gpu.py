#!/usr/bin/env python3
"""Read-only native DRM open differential over SSH; never writes device data.

Exit 0 only when host root/equivalent Plex credentials and both pod identities
can open both DRM devices. No installs, test containers, or policy changes.
"""
import argparse
import json
import subprocess
import sys

REMOTE = r'''
import json, os, stat, subprocess

devices = ["/dev/dri/card0", "/dev/dri/renderD128"]
def host_probe(label):
    rows = []
    for path in devices:
        s = os.stat(path)
        row = dict(context=label, path=path, uid=os.getuid(), gid=os.getgid(),
                   groups=os.getgroups(), inode=s.st_ino, fs_device=s.st_dev,
                   major=os.major(s.st_rdev), minor=os.minor(s.st_rdev),
                   mode=oct(stat.S_IMODE(s.st_mode)), owner=[s.st_uid, s.st_gid])
        try:
            fd = os.open(path, os.O_RDWR | os.O_CLOEXEC)
            os.close(fd)
            row["open"] = "PASS"
        except OSError as e:
            row.update(open="FAIL", errno=e.errno, error=e.strerror)
        rows.append(row)
    return rows

perl = r'for $p (@ARGV) { @s=stat($p); $ok=sysopen(F,$p,2); $e=0+$!; $msg="$!"; close(F) if $ok; printf "%s uid=%d gid=%s inode=%d rdev=%d mode=%o owner=%d:%d open=%s errno=%d error=%s\n",$p,$<,$(,$s[1],$s[6],$s[2]&07777,$s[4],$s[5],$ok?"PASS":"FAIL",$ok?0:$e,$ok?"":$msg; }'
base = ["k3s", "kubectl", "exec", "-n", "plex", "plex-plex-media-server-0", "--"]
root = subprocess.run(base+["perl", "-e", perl]+devices, text=True, capture_output=True, check=True)
plex = subprocess.run(base+["runuser", "-u", "plex", "--", "perl", "-e", perl]+devices, text=True, capture_output=True, check=True)
ident = subprocess.run(base+["id", "plex"], text=True, capture_output=True, check=True).stdout.strip()
# Run an exact UID/GID/group credential equivalent on the host, isolated child only.
uid = int(subprocess.check_output(base+["id", "-u", "plex"], text=True))
gid = int(subprocess.check_output(base+["id", "-g", "plex"], text=True))
groups = list(map(int, subprocess.check_output(base+["id", "-G", "plex"], text=True).split()))
r, w = os.pipe()
pid = os.fork()
if pid == 0:
    os.close(r)
    os.setgroups(groups); os.setgid(gid); os.setuid(uid)
    with os.fdopen(w, "w") as f:
        json.dump(host_probe("host-plex-equivalent"), f)
    os._exit(0)
os.close(w)
with os.fdopen(r) as f:
    equivalent = json.load(f)
os.waitpid(pid, 0)
host = host_probe("host-root") + equivalent
result = dict(host=host, pod_root=root.stdout.splitlines(), pod_plex=plex.stdout.splitlines(), pod_identity=ident)
result["passed"] = all(x["open"] == "PASS" for x in host) and all("open=PASS" in x for x in result["pod_root"]+result["pod_plex"])
print(json.dumps(result, indent=2))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="192.168.1.110")
    args = parser.parse_args()
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", args.host, "sudo -n python3 -"],
        input=REMOTE, text=True, capture_output=True, timeout=45, check=True,
    )
    result = json.loads(proc.stdout)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
