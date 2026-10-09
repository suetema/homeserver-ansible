"""Offline regressions for review findings; never contact the live host."""
import ast
import hashlib
import json
from pathlib import Path
import signal
import tempfile
import types
import unittest
from unittest.mock import patch

import yaml

import k3s_checkpoint_guard as safeguard
import k3s_checkpoint_remote as checkpoint
import test_or_probe_plex_gpu_transcode as plex

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / 'roles/k3s'
RUN = 'k3s-20261009T120000Z-aaaaaaaa'


class CheckpointSafeguardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='k3s-safeguard-')
        self.root = Path(self.temp.name)
        self.binary = self.root / 'k3s'
        self.unit = self.root / 'k3s.service'
        self.binary.write_bytes(b'unchanged current binary')
        self.unit.write_bytes(b'unchanged current service')
        self.patches = [patch.object(safeguard, 'BASE', self.root),
                        patch.object(safeguard, 'META', self.root / 'guard.json'),
                        patch.object(safeguard, 'BINARY', self.binary),
                        patch.object(safeguard, 'UNIT', self.unit)]
        for p in self.patches:
            p.start()
        self.addCleanup(self.temp.cleanup)
        for p in self.patches:
            self.addCleanup(p.stop)

    def arm(self):
        safeguard.arm(RUN, safeguard.digest(self.binary), safeguard.digest(self.unit))

    def test_lost_controller_host_local_fires_only_unchanged_service(self):
        self.arm()
        # No controller callback, SSH connection or Ansible always branch.
        with patch.object(safeguard.subprocess, 'run') as systemd:
            self.assertEqual(safeguard.fire(), 'started_unchanged_service_after_checkpoint_deadline')
            systemd.assert_called_once_with(['systemctl', 'start', '--no-block', 'k3s'],
                                           capture_output=True, check=True, timeout=10)
            safeguard.fire()
            self.assertEqual(systemd.call_count, 1)
        self.assertEqual(self.binary.read_bytes(), b'unchanged current binary')

    def test_promoted_binary_or_changed_unit_never_falls_back(self):
        for path in [self.binary, self.unit]:
            with self.subTest(path=path):
                self.arm()
                previous = path.read_bytes()
                path.write_bytes(b'new migrated version or unexpected unit')
                with patch.object(safeguard.subprocess, 'run') as systemd:
                    self.assertEqual(safeguard.fire(), 'identity_changed_no_action')
                    systemd.assert_not_called()
                self.assertEqual(path.read_bytes(), b'new migrated version or unexpected unit')
                path.write_bytes(previous)

    def test_cancel_before_promotion_prevents_any_later_restart(self):
        self.arm()
        safeguard.disarm(RUN)
        self.binary.write_bytes(b'promoted binary')
        with patch.object(safeguard.subprocess, 'run') as systemd:
            self.assertEqual(safeguard.fire(), 'disarmed_no_action')
            systemd.assert_not_called()

    def test_wrong_owner_and_double_arm_fail_closed(self):
        self.arm()
        with self.assertRaises(RuntimeError):
            safeguard.disarm('other-run')
        with self.assertRaises(RuntimeError):
            self.arm()
        self.assertTrue(safeguard.read_metadata()['armed'])

    def test_identity_mismatch_blocks_arm_and_metadata_is_private(self):
        with self.assertRaises(RuntimeError):
            safeguard.arm(RUN, '0' * 64, safeguard.digest(self.unit))
        self.arm()
        self.assertEqual(safeguard.META.stat().st_mode & 0o777, 0o600)
        self.assertNotIn('token', safeguard.META.read_text())

    def test_capture_host_deadline_survives_lost_controller_and_restores_handler(self):
        old = signal.getsignal(signal.SIGALRM)
        def stalled_capture(*args):
            signal.raise_signal(signal.SIGALRM)
        with patch.object(checkpoint, 'capture_payload', side_effect=stalled_capture):
            with self.assertRaises(TimeoutError):
                checkpoint.capture(RUN, {})
        self.assertEqual(signal.getsignal(signal.SIGALRM), old)
        self.assertEqual(signal.alarm(0), 0)

    def test_copy_failure_never_deletes_original_db_or_publishes_archive(self):
        server = self.root / 'server'
        db = server / 'db'
        db.mkdir(parents=True)
        (db / 'state.db').write_bytes(b'original DB must stay intact')
        with patch.object(checkpoint, 'BASE', self.root), patch.object(checkpoint, 'SERVER', server), \
                patch.object(checkpoint, 'stopped'), \
                patch.object(checkpoint.shutil, 'copytree', side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                checkpoint.capture(RUN, {})
        self.assertEqual((db / 'state.db').read_bytes(), b'original DB must stay intact')
        self.assertFalse((self.root / RUN / 'checkpoint.tar').exists())

    def test_role_ordering_deadlines_and_no_block_requests(self):
        tasks = yaml.safe_load((ROLE / 'tasks/checkpoint.yaml').read_text())
        arm = next(i for i, t in enumerate(tasks) if t.get('ansible.builtin.include_tasks') == 'guard-arm.yaml')
        capture = next(i for i, t in enumerate(tasks) if 'block' in t)
        self.assertLess(arm, capture)
        block = tasks[capture]
        for t in block['block'] + block['always']:
            if 'ansible.builtin.systemd_service' in t:
                self.assertTrue(t['ansible.builtin.systemd_service']['no_block'])
                self.assertLessEqual(t['async'], 20)
        copy = next(t for t in block['block'] if 'Copy the whole' in t['name'])
        self.assertLessEqual(copy['async'], 90)
        self.assertIn('guard-disarm.yaml', [t.get('ansible.builtin.include_tasks') for t in block['always']])
        upgrade = yaml.safe_load((ROLE / 'tasks/upgrade.yaml').read_text())
        transaction = next(t['block'] for t in upgrade if 'block' in t)
        promote = next(i for i, t in enumerate(transaction) if 'ansible.builtin.copy' in t)
        self.assertEqual(transaction[promote - 1]['ansible.builtin.include_tasks'], 'guard-disarm.yaml')
        handler = yaml.safe_load((ROLE / 'handlers/main.yaml').read_text())[0]
        self.assertTrue(handler['ansible.builtin.systemd_service']['no_block'])
        self.assertLessEqual(handler['async'], 20)
        bootstrap = yaml.safe_load((ROLE / 'tasks/bootstrap.yaml').read_text())
        service = next(t['ansible.builtin.systemd_service'] for t in bootstrap if 'ansible.builtin.systemd_service' in t)
        self.assertIn('k3s_start_bootstrap', service['state'])
        defaults = yaml.safe_load((ROLE / 'defaults/main.yaml').read_text())
        self.assertFalse(defaults['k3s_start_bootstrap'])
        self.assertFalse(defaults['k3s_code_review_cleared'])

    def test_clearance_is_not_conditional_on_remaining_pin_risks(self):
        tasks = yaml.safe_load((ROLE / 'tasks/existing.yaml').read_text())
        gate = next(t for t in tasks if 'parent clearance' in t['name'])
        self.assertNotIn('drift_risks', str(gate['when']))
        self.assertNotIn('chart_risks', str(gate['when']))

    def test_validated_phase_is_terminal_with_no_active_command(self):
        with patch.object(checkpoint, 'BASE', self.root):
            checkpoint.status('k3s-accepted', 'v1.34.12+k3s1')
            checkpoint.status('k3s-replacing-binary', 'v1.35.9+k3s1')
            self.assertEqual(json.loads((self.root / 'status.json').read_text())['running_command_category'], 'k3s-ansible')
            checkpoint.status('validated-k3s-1.35', 'v1.35.9+k3s1')
            value = json.loads((self.root / 'status.json').read_text())
            self.assertEqual(value['phase'], 'validated-k3s-1.35')
            self.assertIsNone(value['running_command_category'])
            self.assertEqual(value['next_step'], 'Maintenance complete; no automatic subsequent minor')
            self.assertTrue(any(m.get('phase') == 'k3s-replacing-binary' for m in value['historical_milestones']))


class PlexCleanupTests(unittest.TestCase):
    def setUp(self):
        # Load real remote functions without executing the remote CLI entrypoint.
        tree = ast.parse(plex.REMOTE)
        tree.body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef))]
        self.remote = types.ModuleType('plex_fixture')
        exec(compile(tree, 'plex-fixture', 'exec'), self.remote.__dict__)

    def test_stop_200_does_not_prove_owned_session_termination(self):
        def fetch(path, query=None, timeout=None):
            if path == '/transcode/sessions':
                return b'<MediaContainer><TranscodeSession key="owned-key" /></MediaContainer>'
            return b'<MediaContainer />'
        with patch.object(self.remote.time, 'sleep'):
            self.assertFalse(self.remote.stop_owned_stream(fetch, 'owned-session', {'owned-key'}))

    def test_failed_stop_can_pass_only_after_verified_absence(self):
        def fetch(path, query=None, timeout=None):
            if path.endswith('/stop'):
                raise TimeoutError
            return b'<MediaContainer />'
        self.assertTrue(self.remote.stop_owned_stream(fetch, 'owned-session', set()))

    def test_query_failure_fails_closed_and_never_stops_other_users(self):
        calls = []
        def fetch(path, query=None, timeout=None):
            calls.append((path, query, timeout))
            if path.endswith('/stop'):
                return b''
            raise TimeoutError
        with patch.object(self.remote.time, 'sleep'):
            self.assertFalse(self.remote.stop_owned_stream(fetch, 'owned-session', set()))
        stops = [q for p, q, t in calls if p.endswith('/stop')]
        self.assertEqual(stops, [{'session': 'owned-session'}] * 3)
        self.assertTrue(all(t == 5 for p, q, t in calls))

    def test_other_playback_remains_untouched_but_own_playback_blocks(self):
        calls = []
        player = 'someone-else'
        def fetch(path, query=None, timeout=None):
            calls.append(query)
            if path == '/status/sessions':
                return f'<MediaContainer><Video><Player machineIdentifier="{player}" /></Video></MediaContainer>'.encode()
            return b'<MediaContainer />'
        self.assertTrue(self.remote.stop_owned_stream(fetch, 'owned-session', set()))
        player = 'owned-session'
        with patch.object(self.remote.time, 'sleep'):
            self.assertFalse(self.remote.stop_owned_stream(fetch, 'owned-session', set()))
        self.assertNotIn({'session': 'someone-else'}, calls)

    def transcode(self, cleanup_ok):
        headers = {'X-Plex-Token': 'fixture-only'}
        def fetch(path, query=None, timeout=None):
            if path == '/library/sections':
                return b'<MediaContainer><Directory key="1" type="movie" /></MediaContainer>'
            if path == '/library/sections/1/all':
                return b'<MediaContainer><Video ratingKey="1" duration="10000"><Media videoCodec="h264"><Part /></Media></Video></MediaContainer>'
            if path.endswith('start.m3u8'):
                return b'#EXTM3U\nsegment.ts'
            if path.endswith('segment.ts'):
                return b'actual segment'
            if path == '/transcode/sessions':
                session = headers['X-Plex-Client-Identifier']
                return f'<MediaContainer><TranscodeSession key="{session}" videoDecision="transcode" transcodeHwEncoding="vaapi" transcodeHwDecoding="vaapi" transcodeHwFullPipeline="1" /></MediaContainer>'.encode()
            return b'<MediaContainer />'
        with patch.object(self.remote, 'context', return_value=({}, {}, {}, headers, fetch, 'identity')), \
                patch.object(self.remote, 'stop_owned_stream', return_value=cleanup_ok):
            return self.remote.transcode()

    def test_hardware_success_with_cleanup_failure_blocks_acceptance_keeps_evidence(self):
        value = self.transcode(False)
        self.assertTrue(value['hardware'])
        self.assertEqual(value['segments_read'], 1)
        self.assertTrue(value['session_evidence'])
        self.assertFalse(value['own_stream_stopped'])
        self.assertFalse(value['passed'])
        self.assertEqual(value['cleanup_error'], 'owned_session_termination_unverified')

    def test_hardware_success_with_verified_cleanup_passes(self):
        value = self.transcode(True)
        self.assertTrue(value['passed'])
        self.assertTrue(value['own_stream_stopped'])

    def test_ansible_asserts_cleanup_and_persists_evidence(self):
        tasks = yaml.safe_load((ROLE / 'tasks/validate.yaml').read_text())
        probe = next(t for t in tasks if 'register' in t and t['register'] == 'k3s_plex_transcode')
        self.assertIn('--output', probe['ansible.builtin.command']['argv'])
        gate = next(t for t in tasks if 'ansible.builtin.assert' in t)
        self.assertIn('(k3s_plex_transcode.stdout | from_json).own_stream_stopped is true', gate['ansible.builtin.assert']['that'])


if __name__ == '__main__':
    unittest.main()
