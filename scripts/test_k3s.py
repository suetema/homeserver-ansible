"""Safety/crypto regressions for the opt-in k3s path; never access the live host."""
import hashlib
import copy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tarfile
import tempfile
import unittest

import yaml

import k3s_checkpoint_remote as remote
import k3s_checkpoint_verify as verify
import k3s_guard as guard
import k3s_validate_remote as acceptance

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / 'roles/k3s'
AGE = Path.home() / 'homelab-backups/tools/age-v1.3.2/age'
KEYGEN = AGE.with_name('age-keygen')


class K3sSafetyTests(unittest.TestCase):
    def test_explicit_playbook_and_disabled_opt_in(self):
        play = yaml.safe_load((ROOT / 'k3s.yaml').read_text())[0]
        self.assertEqual(play['roles'], [{'role': 'k3s'}])
        defaults = yaml.safe_load((ROLE / 'defaults/main.yaml').read_text())
        self.assertFalse(defaults['k3s_apply'])
        self.assertFalse(defaults['k3s_bootstrap'])
        self.assertFalse(defaults['k3s_start_bootstrap'])
        self.assertGreaterEqual(defaults['k3s_soak_seconds'], 1800)

    def test_only_supported_pinned_versions_in_inventory(self):
        values = yaml.safe_load((ROOT / 'inventories/production/group_vars/homelab.yaml').read_text())
        self.assertEqual(values['k3s_desired_version'], 'v1.35.9+k3s1')
        self.assertEqual(set(values['k3s_release_checksums']),
                         {'v1.33.11+k3s1', 'v1.34.12+k3s1', 'v1.35.9+k3s1'})
        self.assertEqual(len(values['k3s_required_mounts']), 6)
        self.assertTrue(all(len(c) == 64 for c in values['k3s_release_checksums'].values()))

    def test_checkpoint_cannot_change_services(self):
        source = (ROOT / 'scripts/k3s_checkpoint_remote.py').read_text()
        for action in ["'stop'", "'start'", "'restart'", 'etcd-snapshot', 'killall']:
            self.assertNotIn(action, source)
        self.assertIn('MainPID=0', source)
        self.assertIn("'no_datastore_open_descriptors': True", source)

    def test_checkpoint_resume_is_always_and_precedes_transfer(self):
        tasks = yaml.safe_load((ROLE / 'tasks/checkpoint.yaml').read_text())
        index = next(i for i, t in enumerate(tasks) if 'block' in t)
        self.assertEqual(tasks[index]['block'][0]['ansible.builtin.systemd_service']['state'], 'stopped')
        self.assertEqual(tasks[index]['always'][0]['ansible.builtin.systemd_service']['state'], 'started')
        fetch = next(i for i, t in enumerate(tasks) if 'ansible.builtin.fetch' in t)
        self.assertGreater(fetch, index)

    def test_whole_database_not_etcd_or_binary_only_rollback(self):
        source = (ROOT / 'scripts/k3s_checkpoint_remote.py').read_text()
        self.assertIn("['db', 'token', 'cred', 'tls', 'manifests']", source)
        source = (ROOT / 'scripts/k3s_checkpoint_verify.py').read_text()
        self.assertNotIn('?mode=ro&immutable=1', source)
        self.assertIn("'?mode=rw'", source)
        self.assertIn('while process.stdout.read', source)

    def test_no_uninstall_drain_reboot_or_floating_installer(self):
        for path in ROLE.rglob('*'):
            if path.is_file():
                source = path.read_text()
                for forbidden in ['get.k3s.io', 'k3s-killall', 'k3s-uninstall', 'kubectl drain',
                                  'ansible.builtin.reboot', 'ansible.builtin.shell']:
                    self.assertNotIn(forbidden, source)

    def test_artifact_has_sha256_gate(self):
        tasks = yaml.safe_load((ROLE / 'tasks/artifact.yaml').read_text())
        download = next(t['ansible.builtin.get_url'] for t in tasks if 'ansible.builtin.get_url' in t)
        self.assertIn('k3s_target_version', download['url'])
        self.assertEqual(download['checksum'], 'sha256:{{ k3s_target_sha256 }}')

    def test_upgrade_does_not_rewrite_unit(self):
        source = (ROLE / 'tasks/upgrade.yaml').read_text()
        self.assertNotIn('/etc/systemd/system/k3s.service', source)
        self.assertLess(source.index('include_tasks: checkpoint.yaml'),
                        source.index('dest: /usr/local/bin/k3s\n'))
        self.assertEqual(source.count('notify:'), 1)

    def test_check_mode_never_invokes_mutating_branches(self):
        tasks = yaml.safe_load((ROLE / 'tasks/main.yaml').read_text())
        for task in tasks:
            if task.get('ansible.builtin.include_tasks') in ['upgrade.yaml', 'bootstrap.yaml']:
                self.assertIn('not ansible_check_mode', task['when'])
                self.assertIn('k3s_apply | bool', task['when'])

    def test_drift_guard_checks_init_and_main_but_not_pinned_always(self):
        pod = {'metadata': {'namespace': 'app', 'name': 'app-0', 'uid': 'u'},
               'spec': {'containers': [{'name': 'main', 'image': 'x@sha256:a', 'imagePullPolicy': 'Always'}],
                        'initContainers': [{'name': 'init', 'image': 'x:latest', 'imagePullPolicy': 'Always'}]},
               'status': {'phase': 'Running'}}
        images = guard.image_inventory([pod])
        self.assertEqual(len(images), 2)
        self.assertEqual([x['container'] for x in guard.drift_risks(images)], ['init'])

    def test_guard_does_not_display_pod_env_or_secret_bodies(self):
        pod = {'metadata': {'namespace': 'app', 'name': 'app', 'uid': 'u'},
               'spec': {'containers': [{'name': 'main', 'image': 'x:latest',
                                         'env': [{'name': 'PASSWORD', 'value': 'never-print-me'}]}]},
               'status': {'phase': 'Running'}}
        self.assertNotIn('never-print-me', json.dumps(guard.image_inventory([pod])))

    def test_owned_paths_cannot_escape_backup_root(self):
        for value in ['../etc', 'k3s-../../root', 'bad', 'k3s-20261009T120000Z-aaaaaaaa/extra']:
            with self.assertRaises(ValueError):
                remote.stage_path(value)
        self.assertEqual(remote.stage_path('k3s-20261009T120000Z-aaaaaaaa').parent, remote.BASE)

    def test_unsafe_archive_paths_rejected(self):
        for value in ['../etc/shadow', '/etc/shadow', 'a/../../b']:
            with self.assertRaises(ValueError):
                verify.safe_name(value)

    def test_bootstrap_mount_guard_is_native_and_service_retains_flags(self):
        unit = (ROLE / 'templates/k3s.service.j2').read_text()
        for value in ['KillMode=process', 'Delegate=yes', '--disable=servicelb', '--disable=traefik',
                      'k3s-mountcheck.py', 'RequiresMountsFor=']:
            self.assertIn(value, unit)

    def test_acceptance_rejects_image_pvc_ingress_swap_and_flux_drift(self):
        before = {'target_sha256': 'new-sha', 'unit_sha256': 'same-unit',
                  'nodes': [{'version': 'v1.33.11+k3s1', 'ready': True, 'gpu': '1', 'conditions': []}],
                  'images': [{'namespace': 'app', 'uid': 'same-pod', 'container': 'main',
                              'image': 'same@sha256:x', 'image_id': 'same-id'}],
                  'pvcs': ['same-claim'], 'flux': [], 'automation': [], 'routes': {},
                  'arr': {a: {'status': {'version': 'same-version'}, 'host': {}} for a in ['sonarr', 'radarr']},
                  'swap_bytes': 8, 'ingress_ips': ['10.42.0.193'],
                  'mounts': [{'target': '/', 'uuid': 'same', 'fstype': 'ext4', 'options': 'rw'}]}
        after = copy.deepcopy(before)
        after.update(version='v1.34.12+k3s1', sha256='new-sha', readyz='ok', running_pods=59, ready_pods=59)
        after['nodes'][0]['version'] = after['version']
        acceptance.compare(before, after, after['version'])
        for key, changed in [('pvcs', ['wrong']), ('ingress_ips', ['10.42.0.200']),
                             ('swap_bytes', 0), ('automation', [{'suspended': True}]),
                             ('images', [dict(after['images'][0], image_id='wrong')])]:
            value = copy.deepcopy(after)
            value[key] = changed
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                acceptance.compare(before, value, after['version'])


@unittest.skipUnless(AGE.is_file() and KEYGEN.is_file(), 'Private approved age tools unavailable')
class K3sCryptoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='k3s-test-')
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.identity = self.root / 'identity'
        subprocess.run([str(KEYGEN), '-o', str(self.identity)], capture_output=True, check=True)
        self.recipient = self.root / 'recipient'
        value = subprocess.run([str(KEYGEN), '-y', str(self.identity)], capture_output=True, check=True)
        self.recipient.write_bytes(value.stdout)

    def tearDown(self):
        self.temp.cleanup()

    def fixture(self, bad_hash=False):
        payload = self.root / 'payload'
        db = payload / 'var/lib/rancher/k3s/server/db/state.db'
        db.parent.mkdir(parents=True)
        self.connection = sqlite3.connect(db)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('CREATE TABLE kine(id INTEGER PRIMARY KEY, name TEXT)')
        self.connection.execute("INSERT INTO kine VALUES(1, 'fixture-only')")
        self.connection.commit()
        binary = b'fixture binary, not executable'
        files = {'var/lib/rancher/k3s/server/token': b'fixture-token-not-a-real-secret',
                 'usr/local/bin/k3s': binary, 'etc/systemd/system/k3s.service': b'fixture unit'}
        pairing = {'run_id': 'k3s-20261009T120000Z-aaaaaaaa', 'version': 'v1.33.11+k3s1',
                   'sha256': hashlib.sha256(binary).hexdigest(), 'captured_epoch': 1}
        files['backup-metadata/pairing.json'] = json.dumps(pairing).encode()
        for name, data in files.items():
            p = payload / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        manifest = {'files': [{'path': str(p.relative_to(payload)),
                               'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                              for p in sorted(payload.rglob('*')) if p.is_file()]}
        if bad_hash:
            manifest['files'][0]['sha256'] = '0' * 64
        (payload / 'backup-metadata/manifest.json').write_text(json.dumps(manifest))
        tarpath = self.root / 'fixture.tar'
        with tarfile.open(tarpath, 'w') as tar:
            for p in payload.rglob('*'):
                tar.add(p, arcname=str(p.relative_to(payload)), recursive=False)
        self.connection.close()
        archive = self.root / 'fixture.tar.age'
        subprocess.run([str(AGE), '-R', str(self.recipient), '-o', str(archive), str(tarpath)],
                       capture_output=True, check=True)
        return archive

    def test_authenticated_roundtrip_with_wal_only_kine_schema(self):
        receipt = verify.verify(self.fixture(), AGE, self.identity, self.root)
        self.assertEqual(receipt['status'], 'verified')
        self.assertTrue(receipt['age_authenticated_to_eof'])
        self.assertEqual(receipt['sqlite_integrity'], 'ok')
        self.assertFalse(list(self.root.glob('sqlite-verify-*')))

    def test_valid_encryption_with_bad_file_hash_fails(self):
        with self.assertRaises(RuntimeError):
            verify.verify(self.fixture(True), AGE, self.identity, self.root)

    def test_truncated_ciphertext_fails_authentication(self):
        archive = self.fixture()
        archive.write_bytes(archive.read_bytes()[:-20])
        with self.assertRaises((RuntimeError, tarfile.ReadError)):
            verify.verify(archive, AGE, self.identity, self.root)


if __name__ == '__main__':
    unittest.main()
