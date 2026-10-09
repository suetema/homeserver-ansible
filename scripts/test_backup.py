import importlib.util
from pathlib import Path
import unittest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


local = load("backup_to_mac")
remote = load("backup_remote")


class BackupSafetyTests(unittest.TestCase):
    def test_archive_paths_reject_traversal(self):
        for name in ["/etc/shadow", "../escape", "etc/../../escape", ""]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                local.safe_name(name)

    def test_archive_paths_allow_spaces(self):
        self.assertEqual(str(local.safe_name("etc/dockerconfigs/Plex Media Server/data.db")),
                         "etc/dockerconfigs/Plex Media Server/data.db")

    def test_cleanup_scope(self):
        run_id = "20261008T131500Z-abcdef12"
        self.assertEqual(remote.run_dir(run_id).parent, remote.STAGING)
        for value in ["../", "", "/var", "20261008T131500Z-abcdef12/../../etc"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                remote.run_dir(value)

    def test_path_exclusion_boundary(self):
        root = Path("/etc/k8sconfigs/endurain/postgres")
        self.assertTrue(remote.under(root / "pgdata/base", root))
        self.assertFalse(remote.under(Path(str(root) + "-other"), root))

    def test_host_oauth_file_captured_without_changing_source(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "oauth-test.json"
            source.write_text('{"fixture": "test-only-not-a-real-key"}')
            payload = root / "payload"
            payload.mkdir()
            with patch.object(remote, "MCP_CLIENT_CONFIG", source):
                result = remote.collect_mcp_recovery(payload)
            self.assertTrue(result["client_config_captured"])
            self.assertEqual((payload / str(source).lstrip("/")).read_bytes(), source.read_bytes())

    def test_sqlite_scan_excludes_reproducible_browser_cache(self):
        import sqlite3
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            live = root / "app.db"
            cache = root / "cache" / "browser.db"
            cache.parent.mkdir()
            state = root / "state.db"
            for path in [live, cache, state]:
                with sqlite3.connect(str(path)) as db:
                    db.execute("CREATE TABLE fixture (value TEXT)")
                db.close()
            with patch.object(remote, "ROOTS", [root]), patch.object(remote, "STATE", state), \
                    patch.object(remote, "REPRODUCIBLE_PATHS", [cache.parent]):
                found = remote.sqlite_sources()
            self.assertIn(live, found)
            self.assertNotIn(cache, found)

    def test_sqlite_online_snapshot(self):
        import sqlite3
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "live.db"
            output = Path(directory) / "backup.db"
            with sqlite3.connect(str(source)) as db:
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("CREATE TABLE entries (value TEXT)")
                db.execute("INSERT INTO entries VALUES ('test')")
                db.commit()
                result = remote.snapshot_sqlite(source, output)
            db.close()
            self.assertEqual(result["quick_check"], "ok")
            with sqlite3.connect(str(output)) as db:
                self.assertEqual(db.execute("SELECT value FROM entries").fetchall(), [("test",)])
            db.close()

    def test_prepare_can_resume_completed_staging(self):
        import contextlib
        import io
        import sqlite3
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state.db"
            with sqlite3.connect(str(state)) as db:
                db.execute("CREATE TABLE fixture (value TEXT)")
            db.close()

            def inventory(args, timeout=120, output=None):
                if output:
                    output.write(b"test inventory\n")
                return b"test inventory\n"

            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(remote, "STAGING", root / "staging"))
                stack.enter_context(patch.object(remote, "ROOTS", []))
                stack.enter_context(patch.object(remote, "STATE", state))
                stack.enter_context(patch.object(remote, "postgres_exports", return_value=[]))
                stack.enter_context(patch.object(remote, "redis_export", return_value={}))
                stack.enter_context(patch.object(remote, "copy_couchdb", return_value={}))
                stack.enter_context(patch.object(remote, "command", side_effect=inventory))
                stack.enter_context(patch.object(remote, "kube", return_value=b'{"items": []}'))
                stack.enter_context(patch.object(remote.subprocess, "run",
                                                return_value=SimpleNamespace(stdout=b"", returncode=0)))
                snapshots = stack.enter_context(patch.object(remote, "snapshot_sqlite",
                                                             wraps=remote.snapshot_sqlite))
                stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
                run_id = "20261008T131500Z-abcdef12"
                remote.prepare(run_id)
                remote.prepare(run_id, resume=True)
                self.assertEqual(snapshots.call_count, 1)
                self.assertTrue((remote.run_dir(run_id) / "report.json").exists())

    @unittest.skipUnless(local.AGE.is_file() and local.IDENTITY.is_file() and local.ZSTD,
                         "Private encryption tooling not initialized")
    def test_encrypted_restore_and_tamper_detection(self):
        import hashlib
        import io
        import json
        import sqlite3
        import subprocess
        import tarfile
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "fixture.sqlite"
            with sqlite3.connect(str(database)) as db:
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("CREATE TABLE fixture (value TEXT)")
                db.execute("INSERT INTO fixture VALUES ('safe test data')")
                db.commit()
            db.close()
            archive = root / "fixture.tar"
            manifest = {"files": [{"path": "etc/fixture.sqlite",
                                  "sha256": hashlib.sha256(database.read_bytes()).hexdigest()}],
                        "changed_during_read": [], "missing_paths": [],
                        "special_or_cross_device_skipped": []}
            with tarfile.open(str(archive), "w") as tf:
                tf.add(str(database), arcname="etc/fixture.sqlite")
                data = json.dumps(manifest).encode()
                info = tarfile.TarInfo("backup-metadata/databases-file-manifest.json")
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))

            def producer(errors):
                return subprocess.Popen(["cat", str(archive)], stdout=subprocess.PIPE,
                                        stderr=errors)

            encrypted = root / "databases.tar.zst.age"
            local.encrypt_stream(encrypted, producer)
            result = local.verify(encrypted, root)
            self.assertTrue(result["file_hashes_verified"])
            self.assertEqual(len(result["sqlite_restore_tests"]), 1)
            with self.assertRaises(RuntimeError):
                local.encrypt_stream(encrypted, producer)
            changed = bytearray(encrypted.read_bytes())
            changed[-1] ^= 1
            encrypted.write_bytes(changed)
            with self.assertRaises((RuntimeError, tarfile.ReadError, EOFError)):
                local.verify(encrypted, root)


if __name__ == "__main__":
    unittest.main()
