"""Ensure the default Ansible path cannot revive legacy apps or mutate the host."""

from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]


class PreflightSafetyTests(unittest.TestCase):
    def test_default_playbook_only_runs_preflight(self):
        plays = yaml.safe_load((ROOT / "homeserver.yaml").read_text())
        self.assertEqual(len(plays), 1)
        play = plays[0]
        self.assertEqual(play["hosts"], "homelab")
        self.assertEqual([role["role"] for role in play["roles"]], ["preflight"])
        self.assertNotIn("tasks", play)
        self.assertNotIn("handlers", play)

    def test_preflight_only_uses_read_only_modules_and_commands(self):
        tasks = yaml.safe_load((ROOT / "roles/preflight/tasks/main.yaml").read_text())
        allowed_modules = {"ansible.builtin.assert", "ansible.builtin.command",
                           "ansible.builtin.stat", "ansible.builtin.debug"}
        for task in tasks:
            modules = {key for key in task if key.startswith("ansible.")}
            self.assertEqual(len(modules), 1, task["name"])
            self.assertTrue(modules <= allowed_modules, task["name"])
            self.assertNotIn("notify", task)
            if "ansible.builtin.command" in task:
                argv = task["ansible.builtin.command"]["argv"]
                self.assertIn(argv[0], ["hostname", "findmnt", "/usr/bin/python3", "k3s"])
                self.assertIs(task["changed_when"], False)
                self.assertIs(task["check_mode"], False)
                if argv[0] == "k3s":
                    self.assertEqual(argv, ["k3s", "kubectl", "get", "nodes", "-o", "json"])
                if argv[0] == "findmnt":
                    self.assertIn("--mountpoint", argv)
                    self.assertEqual(len(argv), 6)
                    self.assertIn(",", argv[-1])

    def test_registered_results_do_not_shadow_role_defaults(self):
        tasks = yaml.safe_load((ROOT / "roles/preflight/tasks/main.yaml").read_text())
        defaults = yaml.safe_load((ROOT / "roles/preflight/defaults/main.yaml").read_text())
        registered = {task["register"] for task in tasks if "register" in task}
        self.assertFalse(registered & defaults.keys())

    def test_inventory_requires_real_disks_and_current_access(self):
        inventory = yaml.safe_load((ROOT / "inventories/production/hosts.yaml").read_text())
        host = inventory["all"]["children"]["homelab"]["hosts"]["ryback"]
        self.assertEqual(host["ansible_host"], "192.168.1.110")
        self.assertEqual(host["ansible_user"], "maarten")
        variables = yaml.safe_load((ROOT / "inventories/production/group_vars/homelab.yaml").read_text())
        self.assertEqual(variables["homelab_expected_hostname"], "ryback")
        self.assertNotEqual(variables["homelab_media_uuid"], variables["homelab_root_uuid"])
        self.assertIn(variables["homelab_media_uuid"], (ROOT / "hosts").read_text())
        self.assertIn(variables["homelab_root_uuid"], (ROOT / "hosts").read_text())


if __name__ == "__main__":
    unittest.main()
