from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

import app_restore_remote
import app_restore_verify


class AppRecoverySafetyTests(unittest.TestCase):
    def test_payload_never_selects_other_apps_or_books(self):
        for name in ["etc/k8sconfigs/plex/file", "mnt/volume1/books/file",
                     "etc/shadow", "backup-metadata/host/credentials"]:
            self.assertIsNone(app_restore_verify.payload_name(name))
        self.assertEqual(app_restore_verify.payload_name("etc/k8sconfigs/suwayomi/database.mv.db"),
                         "suwayomi/database.mv.db")

    def test_foundry_instances_are_mapped_distinctly(self):
        for app in app_restore_remote.APPS[:3]:
            name = "var/lib/rancher/k3s/storage/pvc-test_" + app + "_data-" + app + "-0/Data/test"
            self.assertEqual(app_restore_verify.payload_name(name), app + "/Data/test")

    def test_app_containers_are_isolated_and_digest_pinned(self):
        for image in [app_restore_remote.FOUNDRY, app_restore_remote.SUWAYOMI]:
            self.assertRegex(image, r"@sha256:[a-f0-9]{64}$")
        source = Path(app_restore_remote.__file__).read_text()
        self.assertIn('"--network", "none"', source)
        self.assertNotIn('"--privileged"', source)
        self.assertNotIn('"-p"', source)
        self.assertNotIn('/var/lib/rancher', source)
        self.assertNotIn('/etc/k8sconfigs', source)

    def test_world_check_never_modifies_original_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary)
            source = stage / "foundryvtt"
            (source / "Config").mkdir(parents=True)
            original = '{"port": 30000, "world": "fixture"}'
            (source / "Config/options.json").write_text(original)
            world = source / "Data/worlds/fixture"
            world.mkdir(parents=True)
            (world / "world.json").write_text('{"id":"fixture","coreVersion":"12.331"}')
            def checked(args, **kwargs):
                if args[-1] == app_restore_remote.LEVEL_CHECK:
                    return b'[]'
                return b'{"world":"fixture","user_count":2}'
            report = {"apps": []}
            with patch.object(app_restore_remote, "container"), \
                    patch.object(app_restore_remote, "chown_copy"), \
                    patch.object(app_restore_remote.os, "chown"), \
                    patch.object(app_restore_remote.helper, "remove_owned_container"), \
                    patch.object(app_restore_remote.helper, "checked", side_effect=checked), \
                    patch.object(app_restore_remote, "http", return_value=(200, b'auth join flexcol')):
                app_restore_remote.foundry_check(stage, "20261008T131500Z-abcdef12",
                                                "foundryvtt", stage / "runtime", report)
            self.assertEqual((source / "Config/options.json").read_text(), original)
            self.assertTrue(report["apps"][0]["full_world_launch"])
            self.assertEqual(report["apps"][0]["world_launches"][0]["user_count"], 2)


if __name__ == "__main__":
    unittest.main()
