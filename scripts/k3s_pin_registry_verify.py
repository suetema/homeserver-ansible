"""Read-only accepted-digest registry checks on ryback; auth stays in memory.

The input is a credential-free list. Output contains only image/manifest metadata.
No pulls, tag selection, filesystem writes, image cache changes or raw errors.
"""
import base64
import concurrent.futures
import hashlib
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

ACCEPT = ', '.join(['application/vnd.oci.image.index.v1+json',
                    'application/vnd.docker.distribution.manifest.list.v2+json',
                    'application/vnd.oci.image.manifest.v1+json',
                    'application/vnd.docker.distribution.manifest.v2+json'])


def request(url, headers):
    try:
        return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30)
    except urllib.error.HTTPError as error:
        return error


def credentials(namespace):
    p = subprocess.run(['/usr/local/bin/k3s', 'kubectl', '--request-timeout=30s',
                        'get', 'secrets', '-n', namespace, '-o', 'json'], capture_output=True, timeout=45)
    if p.returncode:
        raise RuntimeError('Existing scoped pull credentials unavailable')
    result = {}
    for secret in json.loads(p.stdout)['items']:
        if secret.get('type') == 'kubernetes.io/dockerconfigjson':
            data = secret.get('data', {}).get('.dockerconfigjson')
            if data:
                result.update(json.loads(base64.b64decode(data))['auths'])
    return result


def split_repo(reference):
    repo = reference.split('@')[0]
    if ':' in repo.rsplit('/', 1)[-1]:
        repo = repo.rsplit(':', 1)[0]
    parts = repo.split('/')
    if len(parts) == 1 or ('.' not in parts[0] and ':' not in parts[0]):
        registry, name = 'registry-1.docker.io', repo if len(parts) > 1 else 'library/' + repo
    else:
        registry, name = parts[0], '/'.join(parts[1:])
    if registry in ['docker.io', 'index.docker.io']:
        registry = 'registry-1.docker.io'
    return registry, name


def verify(row):
    registry, name = split_repo(row['image'])
    digest = row['digest']
    headers = {'Accept': ACCEPT}
    url = 'https://' + registry + '/v2/' + name + '/manifests/' + digest
    with request(url, headers) as response:
        code = response.code
        challenge = response.headers.get('WWW-Authenticate', '')
        payload = response.read() if code == 200 else None
        published_digest = response.headers.get('Docker-Content-Digest')
    if code == 401 and challenge.startswith('Bearer '):
        parameters = dict(re.findall(r'(\w+)="([^"]+)"', challenge))
        realm = parameters.get('realm', '')
        if not realm.startswith('https://'):
            raise RuntimeError('Unsafe registry auth realm')
        query = urllib.parse.urlencode({k: parameters[k] for k in ['service', 'scope'] if k in parameters})
        token_headers = {}
        # Only use existing registry-scoped auth for this same host/name.
        if registry == 'ghcr.io':
            auth = credentials(row['namespace']).get('ghcr.io', {})
            if auth.get('auth'):
                token_headers['Authorization'] = 'Basic ' + auth['auth']
        with request(realm + '?' + query, token_headers) as token_response:
            if token_response.code != 200:
                raise RuntimeError('Accepted digest authentication failed')
            token = json.load(token_response)
        headers['Authorization'] = 'Bearer ' + (token.get('token') or token['access_token'])
        with request(url, headers) as response:
            code = response.code
            payload = response.read() if code == 200 else None
            published_digest = response.headers.get('Docker-Content-Digest')
    if code != 200 or 'sha256:' + hashlib.sha256(payload).hexdigest() != digest:
        raise RuntimeError('Accepted exact digest absent or hash mismatch')
    if published_digest and published_digest != digest:
        raise RuntimeError('Registry returned a different digest')
    manifest = json.loads(payload)
    platforms = [m['digest'] for m in manifest.get('manifests', [])
                 if m.get('platform', {}).get('os') == 'linux'
                 and m.get('platform', {}).get('architecture') == 'amd64']
    return {'namespace': row['namespace'], 'image': row['image'], 'digest': digest,
            'status': 'available_exact_digest', 'mediaType': manifest['mediaType'],
            'amd64_manifests': platforms}


if __name__ == '__main__':
    try:
        rows = json.loads(sys.stdin.read())
        result = []
        for row in rows:
            try:
                result.append(verify(row))
            except Exception:
                result.append({'namespace': row['namespace'], 'image': row['image'],
                               'digest': row['digest'], 'status': 'unverified_fail_closed'})
        print(json.dumps(result))
        if any(r['status'] != 'available_exact_digest' for r in result):
            sys.exit(1)
    except Exception:
        print('Accepted registry verification failed; all raw/auth data suppressed.', file=sys.stderr)
        sys.exit(1)
