"""Read-only k3s guard. Only whitelisted, credential-free fields reach stdout.

Run via Ansible command stdin; never copies or displays raw pod env/Secrets.
"""
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys


def run(argv):
    result = subprocess.run(argv, capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError("Read-only guard command failed: " + argv[0])
    return result.stdout.decode()


def get(resource):
    return json.loads(run(['/usr/local/bin/k3s', 'kubectl', '--request-timeout=30s',
                           'get', resource, '-A', '-o', 'json']))['items']


def ready(obj):
    return any(c['type'] == 'Ready' and c['status'] == 'True'
               for c in obj.get('status', {}).get('conditions', []))


def image_inventory(pods):
    images = []
    for pod in pods:
        if pod.get('status', {}).get('phase') != 'Running':
            continue
        for spec_key, status_key in [('containers', 'containerStatuses'),
                                     ('initContainers', 'initContainerStatuses')]:
            statuses = {s['name']: s for s in pod['status'].get(status_key, [])}
            for c in pod['spec'].get(spec_key, []):
                s = statuses.get(c['name'], {})
                images.append({'namespace': pod['metadata']['namespace'],
                               'pod': pod['metadata']['name'], 'uid': pod['metadata']['uid'],
                               'container': c['name'], 'image': c['image'],
                               'pull_policy': c.get('imagePullPolicy'),
                               'image_id': s.get('imageID'), 'restarts': s.get('restartCount', 0)})
    return images


def drift_risks(images):
    # Digest refs remain immutable with Always. Never intentionally uses local cache.
    return [i for i in images if i['namespace'] != 'kube-system'
            and '@sha256:' not in i['image'] and i['pull_policy'] == 'Always']


def inspect():
    binary = Path('/usr/local/bin/k3s')
    mounts = []
    for target in ['/', '/mnt/volume1', '/boot', '/boot/efi', '/root', '/home']:
        mounts.extend(json.loads(run(['findmnt', '--json', '--mountpoint', target,
                                     '-o', 'TARGET,UUID,FSTYPE,OPTIONS']))['filesystems'])
    result = {'installed': binary.is_file(), 'hostname': run(['hostname']).strip(),
              'mounts': mounts, 'cgroup': run(['stat', '-fc', '%T', '/sys/fs/cgroup']).strip(),
              'root_free_bytes': shutil.disk_usage('/').free,
              'swap_bytes': sum(int(l.split()[2]) * 1024 for l in Path('/proc/swaps').read_text().splitlines()[1:])}
    if not binary.is_file():
        result['partial_state'] = any(Path(p).exists() for p in
                                      ['/var/lib/rancher/k3s/server/db/state.db',
                                       '/etc/systemd/system/k3s.service', '/etc/rancher/k3s'])
        return result
    result.update(version=run([str(binary), '--version']).splitlines()[0].split()[2],
                  sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                  active=run(['systemctl', 'show', 'k3s', '--property=ActiveState', '--value']).strip() == 'active',
                  bootstrap_managed=Path('/etc/rancher/k3s/.ansible-bootstrap').is_file(),
                  datastore_present=Path('/var/lib/rancher/k3s/server/db/state.db').exists())
    unit = Path('/etc/systemd/system/k3s.service').read_text()
    starts = re.findall(r'^ExecStart=(.*)$', unit.replace('\\\n', ' '), re.MULTILINE)
    expected = ['/usr/local/bin/k3s', 'server', '--data-dir', '/var/lib/rancher/k3s',
                '--disable=servicelb', '--disable=traefik']
    result['service_reviewed'] = (len(starts) == 1
                                  and shlex.split(starts[0]) == expected
                                  and 'KillMode=process' in unit and 'Delegate=yes' in unit)
    result['unit_sha256'] = hashlib.sha256(unit.encode()).hexdigest()
    result['extra_config'] = any(Path(p).exists() for p in
                                ['/etc/rancher/k3s/config.yaml', '/etc/rancher/k3s/config.yaml.d',
                                 '/etc/systemd/system/k3s.service.d', '/etc/default/k3s', '/etc/sysconfig/k3s'])
    env = Path('/etc/systemd/system/k3s.service.env')
    result['empty_private_env'] = env.is_file() and env.stat().st_size == 0 and env.stat().st_mode & 0o777 == 0o600
    if not result['active']:
        return result
    result['private_credentials_protected'] = all(
        Path(p).is_file() and Path(p).stat().st_uid == 0 and Path(p).stat().st_mode & 0o777 == 0o600
        for p in ['/var/lib/rancher/k3s/server/token', '/etc/rancher/k3s/k3s.yaml'])
    result['readyz'] = run([str(binary), 'kubectl', '--request-timeout=30s', 'get', '--raw=/readyz']).strip()
    nodes, pods, pvcs = get('nodes'), get('pods'), get('pvc')
    flux = get('helmreleases,kustomizations')
    result['chart_risks'] = [{'namespace': f['metadata']['namespace'], 'name': f['metadata']['name'],
                              'constraint': f['spec'].get('chart', {}).get('spec', {}).get('version', '')}
                             for f in flux if f['kind'] == 'HelmRelease'
                             and not re.fullmatch(r'v?\d+\.\d+\.\d+(?:[-+][\w.-]+)?',
                                                  f['spec'].get('chart', {}).get('spec', {}).get('version', ''))]
    result['automation'] = [{'kind': a['kind'], 'namespace': a['metadata']['namespace'],
                              'name': a['metadata']['name'], 'suspended': a['spec'].get('suspend', False)}
                             for a in get('imageupdateautomations')]
    result['flux_cli'] = shutil.which('flux')
    images = image_inventory(pods)
    result.update(nodes=[{'name': n['metadata']['name'], 'ready': ready(n),
                          'version': n['status']['nodeInfo']['kubeletVersion'],
                          'runtime': n['status']['nodeInfo']['containerRuntimeVersion'],
                          'gpu': n['status']['allocatable'].get('gpu.intel.com/i915'),
                          'conditions': n['status']['conditions']} for n in nodes],
                  running_pods=sum(p['status'].get('phase') == 'Running' for p in pods),
                  ready_pods=sum(p['status'].get('phase') == 'Running' and ready(p) for p in pods),
                  images=images, drift_risks=drift_risks(images),
                  pvcs=[{'namespace': p['metadata']['namespace'], 'name': p['metadata']['name'],
                         'uid': p['metadata']['uid'], 'phase': p['status'].get('phase'),
                         'volume': p['spec'].get('volumeName')} for p in pvcs],
                  flux=[{'kind': f['kind'], 'namespace': f['metadata']['namespace'],
                         'name': f['metadata']['name'], 'ready': ready(f),
                         'suspended': f['spec'].get('suspend', False)} for f in flux],
                  ingress_ips=[p['status'].get('podIP') for p in pods
                               if p['metadata']['namespace'] == 'ingress-nginx' and ready(p)])
    return result


if __name__ == '__main__':
    try:
        print(json.dumps(inspect()))
    except Exception:
        print('Read-only k3s guard failed; no raw command output displayed.', file=sys.stderr)
        sys.exit(1)
