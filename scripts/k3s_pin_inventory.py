"""Read-only whitelist inventory for approved current-version GitOps pinning.

Raw Helm values/pod environments/Secrets never reach stdout. Registry metadata
verification uses existing scoped pull credentials only in remote memory.
"""
import base64
import datetime
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request


def run(args):
    p = subprocess.run(args, capture_output=True, timeout=90)
    if p.returncode:
        raise RuntimeError('Read-only inventory command failed')
    return p.stdout


def get(kind, namespace=None, name=None):
    args = ['/usr/local/bin/k3s', 'kubectl', '--request-timeout=30s', 'get', kind]
    args += ['-n', namespace] if namespace else ['-A']
    if name:
        args.append(name)
    return json.loads(run(args + ['-o', 'json']))


def image_fields(value, path=()):
    result = []
    if isinstance(value, dict):
        if isinstance(value.get('repository'), str) and ('tag' in value or 'digest' in value):
            result.append({'path': list(path), 'repository': value['repository'],
                           'tag': str(value.get('tag', '')), 'digest': value.get('digest'),
                           'pullPolicy': value.get('pullPolicy')})
        for key, child in value.items():
            result += image_fields(child, path + (key,))
    return result


def inventory():
    pods = get('pods')['items']
    releases = get('helmreleases')['items']
    charts = get('helmcharts.source.toolkit.fluxcd.io')['items']
    result = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'pods': [], 'releases': [], 'charts': []}
    for p in pods:
        row = {'namespace': p['metadata']['namespace'], 'name': p['metadata']['name'],
               'uid': p['metadata']['uid'], 'phase': p['status'].get('phase'),
               'owner': p['metadata'].get('ownerReferences', []), 'images': []}
        for key, status in [('containers', 'containerStatuses'), ('initContainers', 'initContainerStatuses')]:
            statuses = {s['name']: s for s in p['status'].get(status, [])}
            for c in p['spec'].get(key, []):
                s = statuses.get(c['name'], {})
                row['images'].append({'name': c['name'], 'init': key == 'initContainers',
                                      'image': c['image'], 'pullPolicy': c.get('imagePullPolicy'),
                                      'imageID': s.get('imageID'), 'restarts': s.get('restartCount'),
                                      'state': next(iter(s.get('state', {})), None)})
        result['pods'].append(row)
    for r in releases:
        history = r['status'].get('history', [])
        deployed = next((h for h in history if h.get('status') == 'deployed'), None)
        if not deployed:
            raise RuntimeError('No deployed chart revision')
        result['releases'].append({'namespace': r['metadata']['namespace'], 'name': r['metadata']['name'],
                                   'releaseName': deployed['name'], 'chartName': deployed['chartName'],
                                   'chartVersion': deployed['chartVersion'],
                                   'chartRef': r['status'].get('helmChart'),
                                   'image_fields': image_fields(r['spec'].get('values', {})),
                                   'constraint': r['spec'].get('chart', {}).get('spec', {}).get('version')})
    for c in charts:
        result['charts'].append({'namespace': c['metadata']['namespace'], 'name': c['metadata']['name'],
                                 'artifact': c['status'].get('artifact'), 'spec': c['spec']})
    return result


if __name__ == '__main__':
    try:
        print(json.dumps(inventory()))
    except Exception:
        print('Credential-safe pin inventory failed; raw output suppressed.', file=sys.stderr)
        sys.exit(1)
