import importlib.util
from pathlib import Path
import unittest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


remote = load("restore_verify_remote")


class IsolatedRestoreSafetyTests(unittest.TestCase):
    def test_staging_is_narrow_and_identifiers_are_validated(self):
        self.assertEqual(remote.stage_for("20261008T131500Z-abcdef12").parent, remote.BASE)
        for value in ["../etc", "", "/var", "20261008T131500Z-abcdef12/../../etc"]:
            with self.assertRaises(ValueError):
                remote.stage_for(value)

    def test_restore_images_are_digest_pinned(self):
        for image in [remote.POSTGRES18, remote.POSTGRES15, remote.COUCHDB]:
            self.assertRegex(image, r"^[a-z0-9]+@sha256:[a-f0-9]{64}$")

    def test_no_live_paths_in_remote_restore_harness(self):
        code = Path(remote.__file__).read_text()
        for live in ["/etc/k8sconfigs", "/etc/dockerconfigs", "/var/lib/rancher", "/mnt/volume1"]:
            self.assertNotIn(live, code)
        self.assertIn('"--network", "none"', code)
        self.assertIn('"--memory", "2g"', code)
        self.assertIn('"--restart", "no"', code)
        self.assertNotIn('"--privileged"', code)


if __name__ == "__main__":
    unittest.main()
