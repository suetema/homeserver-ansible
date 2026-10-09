"""Render accepted nested manual source privately, check an image-only override."""
import json
from pathlib import Path
import tempfile

import yaml

from k3s_pin_render_review import TEMP, run, compare_pods, podspecs

REVISION = '7572e16d417721b09e0c34435b65275338fbe3eb'
DIGEST = 'sha256:29b7aba0466f2870aaba1113cedb28ca8d862bc5fe3fc344f71ed7d772d0e093'


def main():
    with tempfile.TemporaryDirectory(prefix='manual-pin-render-', dir=TEMP) as temp:
        root = Path(temp)
        repo = root / 'source'
        repo.mkdir()
        run(['git', 'init', '-q'], cwd=repo)
        run(['git', 'fetch', '--depth=1', 'https://github.com/suetema/manual-ducati-monster-1100.git', REVISION], cwd=repo)
        listing = run(['git', 'ls-tree', '--name-only', REVISION + ':deploy/flux'], cwd=repo).decode().splitlines()
        for name in listing:
            if not name.endswith('.yaml') or '/' in name:
                raise RuntimeError('Unexpected nested source structure')
            (root / name).write_bytes(run(['git', 'show', REVISION + ':deploy/flux/' + name], cwd=repo))
        before = run(['kubectl', 'kustomize', str(root)])
        path = root / 'kustomization.yaml'
        spec = yaml.safe_load(path.read_text())
        spec['images'] = [{'name': 'ghcr.io/suetema/manual-ducati-monster-1100', 'digest': DIGEST}]
        path.write_text(yaml.safe_dump(spec))
        after = run(['kubectl', 'kustomize', str(root)])
        diffs = compare_pods(podspecs(before), podspecs(after))
        assert len(diffs) == 1 and diffs[0]['container'] == 'manual'
        print(json.dumps({'accepted_source': REVISION, 'pod_image_diffs': diffs}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Nested manual render failed; raw manifests/errors suppressed.')
