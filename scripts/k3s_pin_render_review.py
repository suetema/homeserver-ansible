"""Local render/diff gate for narrowly approved current-version Flux pins.

Raw Kustomize/Helm output stays in memory. Public result lists image-only diffs.
Never prints values, Secret bodies, tokens, environment dumps or raw errors.
"""
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

import yaml

TEMP = Path('/private/var/folders/6h/rlm489tx0xvg5c7p4jw9w3vw0000gn/T/opencode')
EVIDENCE = TEMP / 'k3s-pins-evidence'


def run(argv, data=None, cwd=None):
    p = subprocess.run(argv, input=data, capture_output=True, cwd=cwd, timeout=120)
    if p.returncode:
        raise RuntimeError('Local pin render command failed; raw output suppressed')
    return p.stdout


def objects(root):
    result = {}
    for path in ['apps/prd', 'infrastructure/controllers']:
        data = run(['kubectl', 'kustomize', str(root / path)])
        for doc in yaml.safe_load_all(data):
            if doc and doc.get('kind') == 'HelmRelease':
                result[(doc['metadata']['namespace'], doc['metadata']['name'])] = doc
    return result


def podspecs(manifests):
    result = {}
    for doc in yaml.safe_load_all(manifests):
        if not doc:
            continue
        kind = doc['kind']
        if kind not in ['Deployment', 'StatefulSet', 'DaemonSet', 'Job', 'CronJob']:
            continue
        spec = doc['spec']['jobTemplate']['spec']['template']['spec'] if kind == 'CronJob' else doc['spec']['template']['spec']
        spec = copy.deepcopy(spec)
        for c in spec.get('containers', []) + spec.get('initContainers', []):
            c.setdefault('imagePullPolicy', 'Always' if c['image'].endswith(':latest') else 'IfNotPresent')
        result[(kind, doc['metadata']['name'])] = spec
    return result


def compare_pods(before, after):
    if before.keys() != after.keys():
        raise RuntimeError('Rendered workload inventory changed')
    diffs = []
    for name in before:
        old, new = copy.deepcopy(before[name]), copy.deepcopy(after[name])
        for key in ['containers', 'initContainers']:
            if len(old.get(key, [])) != len(new.get(key, [])):
                raise RuntimeError('Rendered container inventory changed')
            for a, b in zip(old.get(key, []), new.get(key, [])):
                if a['name'] != b['name']:
                    raise RuntimeError('Rendered container identity changed')
                if a['image'] != b['image']:
                    diffs.append({'workload': '/'.join(name), 'container': a['name'],
                                  'before': a['image'], 'after': b['image']})
                    b['image'] = a['image']
                # Operator configuration changes only the proxy image reference.
                for x, y in zip(a.get('env', []), b.get('env', [])):
                    if x['name'] == y['name'] == 'PROXY_IMAGE' and x != y:
                        diffs.append({'workload': '/'.join(name), 'container': a['name'],
                                      'before': x['value'], 'after': y['value'], 'field': 'PROXY_IMAGE'})
                        y.update(x)
        if old != new:
            raise RuntimeError('Non-image rendered PodSpec change; stop pin batch')
    return diffs


def main():
    worktree = Path(sys.argv[1])
    inventory = json.loads((EVIDENCE / 'before.json').read_text())
    live = {(r['namespace'], r['name']): r for r in inventory['releases']}
    with tempfile.TemporaryDirectory(prefix='pin-render-before-', dir=TEMP) as temp:
        original = Path(temp)
        archive = run(['git', 'archive', sys.argv[2]], cwd=worktree)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(original, filter='data')
        before, after = objects(original), objects(worktree)
        if before.keys() != after.keys():
            raise RuntimeError('HelmRelease inventory changed')
        report = {'reviewed_releases': 0, 'chart_pins': 0, 'pod_image_diffs': []}
        for key in before:
            r = live[key]
            a, b = before[key], after[key]
            if a == b:
                continue
            av, bv = a['spec'].get('values', {}), b['spec'].get('values', {})
            chart = EVIDENCE / 'charts' / (r['chartName'] + '-' + r['chartVersion'] + '.tgz')
            if b['spec']['chart']['spec'].get('version') != r['chartVersion']:
                raise RuntimeError('Pin is not the accepted deployed chart version')
            command = ['helm', 'template', r['releaseName'], str(chart), '-n', key[0],
                       '--kube-version', '1.33.11', '-f', '-']
            ap = podspecs(run(command, json.dumps(av).encode()))
            bp = podspecs(run(command, json.dumps(bv).encode()))
            diffs = compare_pods(ap, bp)
            report['pod_image_diffs'] += [dict(d, release='/'.join(key)) for d in diffs]
            report['reviewed_releases'] += 1
            if a['spec']['chart']['spec'].get('version') != b['spec']['chart']['spec'].get('version'):
                report['chart_pins'] += 1
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('Current-version render gate failed; raw manifests/values/errors suppressed.', file=sys.stderr)
        sys.exit(1)
