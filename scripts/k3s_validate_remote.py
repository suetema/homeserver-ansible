"""Ansible acceptance helper: read-only functional checks and bounded real soak.

Imports copies installed by the role; no live object/config writes. No secrets
or raw journals/HTTP headers/bodies are returned. Exceptions suppress raw detail.
"""
import json
import os
from pathlib import Path
import re
import socket
import sys
import time

import k3s_guard as guard
import arr_private_access_probe as arr


def functional():
    result = guard.inspect()
    snapshot = arr.remote()
    result['arr'] = snapshot['apps']
    hosts = snapshot['nginx_hosts']
    if len(hosts) != 22:
        raise RuntimeError('Route inventory changed')
    if any(socket.gethostbyname(h) != '192.168.1.201' for h in hosts):
        raise RuntimeError('Ingress DNS failure')
    result['routes'] = arr.web(snapshot)
    if any(r.get('error') or not r.get('tls_validated') or r.get('status', 599) >= 500
           for r in result['routes'].values()):
        raise RuntimeError('Ingress HTTPS failure')
    if snapshot['ingress_service']['externalTrafficPolicy'] != 'Local':
        raise RuntimeError('Ingress source policy changed')
    for app, data in result['arr'].items():
        if data['anonymous_https']['status'] != 200 or data['anonymous_api']['status'] != 401:
            raise RuntimeError('Arr LAN/auth regression')
        if data['host']['trustedNetworks'] != '10.42.0.193/32':
            raise RuntimeError('Arr narrow proxy trust changed')
    # Query DNS from an existing pod; no image pull, privileged Job or config edit.
    ha = next(p for p in guard.get('pods') if p['metadata']['namespace'] == 'homeassistant'
              and guard.ready(p) and p['metadata']['name'].startswith('homeassistant-')
              and 'cnpg' not in p['metadata']['name'])
    result['cluster_dns'] = guard.run(['/usr/local/bin/k3s', 'kubectl', '--request-timeout=30s',
                                     'exec', '-n', 'homeassistant', ha['metadata']['name'], '--',
                                     'python3', '-c', "import socket; print(socket.gethostbyname('kubernetes.default.svc.cluster.local'))"]).strip()
    if result['cluster_dns'] != '10.43.0.1':
        raise RuntimeError('Cluster DNS query failed')
    if any(c['status'].get('readyInstances') != c['spec']['instances']
           or c['status'].get('phase') != 'Cluster in healthy state'
           for c in guard.get('clusters.postgresql.cnpg.io')):
        raise RuntimeError('CNPG unhealthy')
    if any(not guard.ready(c) for c in guard.get('certificates')):
        raise RuntimeError('Certificate not Ready')
    config = json.loads(guard.run(['/usr/local/bin/k3s', 'kubectl', '--request-timeout=30s',
                                  'get', '--raw=/api/v1/nodes/ryback/proxy/configz']))['kubeletconfig']
    result['kubelet'] = {k: config.get(k) for k in ['cgroupDriver', 'failSwapOn', 'memorySwap']}
    if config['cgroupDriver'] != 'systemd' or config['failSwapOn'] is not False:
        raise RuntimeError('Cgroup/swap policy changed')
    if not re.search(r'SystemdCgroup\s*=\s*true',
                     Path('/var/lib/rancher/k3s/agent/etc/containerd/config.toml').read_text()):
        raise RuntimeError('Runtime cgroup driver changed')
    # Established CRDs and webhook ready endpoints, not a speculative migration.
    if any(not any(c['type'] == 'Established' and c['status'] == 'True'
                   for c in x['status'].get('conditions', [])) for x in guard.get('crds')):
        raise RuntimeError('CRD not established')
    if any(not any(c['type'] == 'Available' and c['status'] == 'True'
                   for c in x['status'].get('conditions', [])) for x in guard.get('apiservices')):
        raise RuntimeError('Aggregated API unavailable')
    slices = guard.get('endpointslices')
    for config in guard.get('validatingwebhookconfigurations,mutatingwebhookconfigurations'):
        for webhook in config['webhooks']:
            service = webhook['clientConfig'].get('service')
            if service and not any(
                    s['metadata']['namespace'] == service['namespace']
                    and s['metadata']['labels'].get('kubernetes.io/service-name') == service['name']
                    and any(e.get('conditions', {}).get('ready') is True for e in s.get('endpoints', []))
                    for s in slices):
                raise RuntimeError('Admission webhook has no Ready endpoint')
    native_gpu_opens()
    public_source_auth()
    logs = guard.run(['journalctl', '-u', 'k3s', '--since=-5min', '--no-pager', '-o', 'cat'])
    for pattern in [r'database disk image is malformed', r'disk I/O error',
                    r'failed to create pod sandbox', r'failed to load kubelet config',
                    r'failed to decrypt bootstrap']:
        if len(re.findall(pattern, logs, re.IGNORECASE)) > 1:
            raise RuntimeError('Repeated control-plane/runtime error signature')
    return result


def native_gpu_opens():
    cards = [p for p in Path('/sys/class/drm').glob('card[0-9]*')
             if re.fullmatch(r'card\d+', p.name) and (p / 'device/driver').resolve().name == 'i915']
    if len(cards) != 1:
        raise RuntimeError('Expected one i915 card')
    renders = [p for p in Path('/sys/class/drm').glob('renderD*')
               if (p / 'device').resolve() == (cards[0] / 'device').resolve()]
    if len(renders) != 1:
        raise RuntimeError('Expected matching i915 render node')
    devices = ['/dev/dri/' + p.name for p in [cards[0], renders[0]]]
    base = ['/usr/local/bin/k3s', 'kubectl', '--request-timeout=30s', 'exec',
            '-n', 'plex', 'plex-plex-media-server-0', '--']
    # Native O_RDWR open only: no DRM writes, symlinks or permission changes.
    perl = 'for $p (@ARGV) { sysopen(F,$p,2) or die "DRM open failed"; close(F); }'
    guard.run(base + ['perl', '-e', perl] + devices)
    guard.run(base + ['runuser', '-u', 'plex', '--', 'perl', '-e', perl] + devices)
    for d in devices:
        fd = os.open(d, os.O_RDWR | os.O_CLOEXEC)
        os.close(fd)
    uid = int(guard.run(base + ['id', '-u', 'plex']))
    gid = int(guard.run(base + ['id', '-g', 'plex']))
    groups = list(map(int, guard.run(base + ['id', '-G', 'plex']).split()))
    child = os.fork()
    if child == 0:
        try:
            os.setgroups(groups)
            os.setgid(gid)
            os.setuid(uid)
            for d in devices:
                fd = os.open(d, os.O_RDWR | os.O_CLOEXEC)
                os.close(fd)
            os._exit(0)
        except Exception:
            os._exit(1)
    _, result = os.waitpid(child, 0)
    if result:
        raise RuntimeError('Host Plex-equivalent native DRM open failed')
    plex = next(p for p in guard.get('pods') if p['metadata']['namespace'] == 'plex' and guard.ready(p))
    if not any(c.get('resources', {}).get('requests', {}).get('gpu.intel.com/i915') in ['1', 1]
               and c.get('resources', {}).get('limits', {}).get('gpu.intel.com/i915') in ['1', 1]
               for c in plex['spec']['containers']):
        raise RuntimeError('Plex GPU allocation requirement changed')


def public_source_auth():
    nginx = next(p for p in guard.get('pods') if p['metadata']['namespace'] == 'ingress-nginx' and guard.ready(p))
    cid = nginx['status']['containerStatuses'][0]['containerID'].split('://')[1]
    inspected = json.loads(guard.run(['/usr/local/bin/k3s', 'crictl', 'inspect', cid]))
    pid = inspected['info']['pid']
    services = guard.get('services')
    for app, port, expected in [('sonarr', 8989, 401), ('radarr', 7878, 302)]:
        service = next(s for s in services if s['metadata']['namespace'] == app and s['metadata']['name'] == app)
        url = 'http://' + service['spec']['clusterIP'] + ':' + str(port) + '/'
        script = """import urllib.request,urllib.error
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args): return None
try:
 r=urllib.request.build_opener(NoRedirect).open(urllib.request.Request(URL,headers={'X-Forwarded-For':'203.0.113.10','X-Forwarded-Proto':'https'}),timeout=10)
 print(r.code)
except urllib.error.HTTPError as e: print(e.code)
""".replace('URL', repr(url))
        code = guard.run(['nsenter', '-t', str(pid), '-n', '/usr/bin/python3', '-c', script]).strip()
        if code != str(expected):
            raise RuntimeError('Trusted-ingress public source classification changed')


def compare(before, after, target):
    if after['version'] != target or after['nodes'][0]['version'] != target:
        raise RuntimeError('Wrong upgraded binary/node version')
    if after['sha256'] != before['target_sha256'] or after['unit_sha256'] != before['unit_sha256']:
        raise RuntimeError('Wrong binary or service unexpectedly modified')
    if after['readyz'] != 'ok' or len(after['nodes']) != 1 or not after['nodes'][0]['ready']:
        raise RuntimeError('API/node not Ready')
    if after['nodes'][0]['gpu'] != '1' or after['running_pods'] != after['ready_pods']:
        raise RuntimeError('GPU/workloads not Ready')
    if any(c['status'] != 'False' for c in after['nodes'][0]['conditions'] if 'Pressure' in c['type']):
        raise RuntimeError('Node pressure')
    if after['pvcs'] != before['pvcs'] or after['ingress_ips'] != before['ingress_ips']:
        raise RuntimeError('PVC identity or narrow trusted nginx IP changed; stop for GitOps repair approval')
    if after['swap_bytes'] != before['swap_bytes']:
        raise RuntimeError('Intentional swap changed')
    mount_ids = lambda value: sorted((m['target'], m['uuid'], m['fstype']) for m in value['mounts'])
    if mount_ids(after) != mount_ids(before) or any('rw' not in m['options'].split(',') for m in after['mounts']):
        raise RuntimeError('Mount identities/writable state changed')
    if len(after['flux']) != len(before['flux']) or after['automation'] != before['automation']:
        raise RuntimeError('Flux inventory/image-automation state changed')
    def protected_images(value):
        return {(i['uid'], i['container']) for i in value['images']
                if i['namespace'] != 'kube-system' or i['container'] == 'intel-gpu-plugin'}
    if protected_images(before) != protected_images(after):
        raise RuntimeError('Application pod identities/inventory changed')
    for old in before['flux']:
        new = next(f for f in after['flux'] if (f['kind'], f['namespace'], f['name']) ==
                   (old['kind'], old['namespace'], old['name']))
        if old['suspended'] != new['suspended'] or not new['ready']:
            raise RuntimeError('Flux original suspension/Ready state not restored')
    for old in before['images']:
        # K3s may update its own bundled images, but not the separately managed GPU.
        if old['namespace'] == 'kube-system' and old['container'] != 'intel-gpu-plugin':
            continue
        new = next(i for i in after['images'] if i['uid'] == old['uid'] and i['container'] == old['container'])
        if (new['image'], new['image_id']) != (old['image'], old['image_id']):
            raise RuntimeError('Application code/spec changed')
    if after['routes'] != before['routes']:
        raise RuntimeError('HTTPS route behavior changed')
    for app in ['sonarr', 'radarr']:
        if after['arr'][app]['status']['version'] != before['arr'][app]['status']['version']:
            raise RuntimeError('Arr application version changed')
        if after['arr'][app]['host'] != before['arr'][app]['host']:
            raise RuntimeError('Arr authentication boundary changed')


def main():
    os.umask(0o077)
    if sys.argv[1] == 'baseline':
        value = functional()
        value['target_sha256'] = sys.argv[3]
        Path(sys.argv[2]).write_text(json.dumps(value))
        return
    before = json.loads(Path(sys.argv[2]).read_text())
    seconds = int(sys.argv[4])
    deadline = time.monotonic() + seconds
    initial_restarts = None
    while True:
        after = functional()
        compare(before, after, sys.argv[3])
        restarts = {(i['uid'], i['container']): i['restarts'] for i in after['images']}
        if initial_restarts is not None and any(restarts.get(k, -1) > v for k, v in initial_restarts.items()):
            raise RuntimeError('Restart count increased during acceptance soak')
        initial_restarts = restarts
        if time.monotonic() >= deadline:
            break
        time.sleep(min(60, deadline - time.monotonic()))
    print(json.dumps({'status': 'accepted', 'version': after['version'], 'soak_seconds': seconds,
                      'pods_ready': after['ready_pods'], 'flux_resources': len(after['flux']),
                      'pvcs': len(after['pvcs']), 'routes': len(after['routes'])}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('Acceptance failed; stop this hop, no automatic datastore/binary downgrade.', file=sys.stderr)
        sys.exit(1)
