"""Read-only, bounded post-pin validation; no host or cluster mutations.

Runs approved functional checks in remote memory, compares every accepted code
digest, and saves only credential-free evidence in the private controller stage.
"""
import collections
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('/private/var/folders/6h/rlm489tx0xvg5c7p4jw9w3vw0000gn/T/opencode/k3s-pins-evidence')


def main():
    before = json.loads((ROOT / 'before.json').read_text())
    expected = collections.defaultdict(set)
    for p in before['pods']:
        if p['phase'] == 'Running':
            for i in p['images']:
                expected[(p['namespace'], i['name'])].add(i['imageID'])
    source = 'import types,sys,json\n'
    for name in ['k3s_guard', 'arr_private_access_probe', 'k3s_validate_remote']:
        code = Path(__file__).with_name(name + '.py').read_text()
        source += 'm=types.ModuleType(' + repr(name) + ');sys.modules[' + repr(name) + ']=m;exec(' + repr(code) + ',m.__dict__)\n'
    source += "try:\n print(json.dumps(sys.modules['k3s_validate_remote'].functional()))\nexcept Exception:\n sys.exit(1)\n"
    deadline = time.monotonic() + 600
    while True:
        p = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                            'maarten@192.168.1.110', 'sudo -n python3 -'],
                           input=source.encode(), capture_output=True, timeout=240)
        if p.returncode == 0:
            value = json.loads(p.stdout)
            current = collections.defaultdict(set)
            for i in value['images']:
                current[(i['namespace'], i['container'])].add(i['image_id'])
            if current != expected:
                raise RuntimeError('Actual accepted code digest changed; no subsequent batch')
            if value['ready_pods'] == value['running_pods'] == 59 and all(f['ready'] for f in value['flux']):
                path = ROOT / (sys.argv[1] + '-functional.json')
                path.write_text(json.dumps(value, indent=2))
                path.chmod(0o600)
                print(json.dumps({'stage': sys.argv[1], 'version': value['version'],
                                  'ready_pods': value['ready_pods'], 'flux_resources': len(value['flux']),
                                  'routes': len(value['routes']), 'pvcs': len(value['pvcs']),
                                  'accepted_code_digests_unchanged': True,
                                  'remaining_unpinned_always': len(value['drift_risks']),
                                  'remaining_broad_charts': len(value['chart_risks']),
                                  'arr_versions': {k: a['status']['version'] for k, a in value['arr'].items()}}))
                return
        if time.monotonic() >= deadline:
            raise RuntimeError('Post-pin functional/readiness deadline missed; no subsequent batch')
        time.sleep(min(10, deadline - time.monotonic()))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('Pin acceptance failed; raw/credential-bearing output suppressed.', file=sys.stderr)
        sys.exit(1)
