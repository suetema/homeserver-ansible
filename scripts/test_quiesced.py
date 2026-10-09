import copy
from pathlib import Path
import unittest
from unittest.mock import patch
import yaml

import backup_remote
import quiesced_checkpoint


class QuiescedBackupSafetyTests(unittest.TestCase):
    def test_checkpoint_targets_only_approved_apps(self):
        self.assertEqual(quiesced_checkpoint.NAMES,
                         ["foundryvtt", "foundryvtt-hans", "foundryvtt-rogier", "suwayomi"])
        self.assertEqual(len(quiesced_checkpoint.FILES), 4)

    def test_only_approved_media_exceptions(self):
        self.assertEqual(backup_remote.BOOK_ROOTS,
                         [Path("/mnt/volume1/books"), Path("/mnt/volume1/k8s-books")])
        self.assertNotIn(Path("/mnt/volume1"), backup_remote.ROOTS)

    def test_foundry_pause_changes_only_post_renderer(self):
        source = {"spec": {"values": {"image": {"tag": "test"}}}}
        result = quiesced_checkpoint.expected_pause(yaml.safe_dump(source), "foundryvtt")
        restored = copy.deepcopy(result)
        restored["spec"].pop("postRenderers")
        self.assertEqual(restored, source)
        self.assertIn("value: 0", result["spec"]["postRenderers"][0]["kustomize"]["patches"][0]["patch"])

    def test_snapshot_refuses_live_pods_before_writing_staging(self):
        import json
        def kube(*args):
            if args[1] == "pv":
                return json.dumps({"items": []}).encode()
            return json.dumps({"items": [{"metadata": {"name": "still-running"}}]}).encode()
        with patch.object(backup_remote, "kube", side_effect=kube), \
                self.assertRaises(RuntimeError):
            backup_remote.prepare_quiesced("20261008T131500Z-abcdef12")


if __name__ == "__main__":
    unittest.main()
