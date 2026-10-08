"""Exercise the embedded bootstrap using the installed Core's validator."""

import json
import os
from pathlib import Path
import tempfile
import unittest

if source_path := os.environ.get("HTTP_BOOTSTRAP_TEST_SOURCE"):
    source = Path(source_path).read_text()
else:
    chart = Path(__file__).resolve().parents[1]
    embedded = (chart / "templates/configmap.yaml").read_text().split(
        "  http-bootstrap.py: |\n", 1
    )[1]
    source = "\n".join(line[4:] if line.startswith("    ") else line
                       for line in embedded.splitlines())
bootstrap = {"__name__": "http_bootstrap_test_target"}
exec(compile(source, "http-bootstrap.py", "exec"), bootstrap)


class HTTPBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "http"
        bootstrap["HTTP_STORE"] = self.path

    def write(self, data):
        self.path.write_text(json.dumps({"version": 2, "minor_version": 2,
                                         "key": "http", "data": data}))
        return self.path.read_bytes()

    def run_bootstrap(self):
        bootstrap["main"]()
        return json.loads(self.path.read_text())["data"]

    def test_fresh_install(self):
        data = self.run_bootstrap()
        self.assertEqual(data["stable"]["server_port"], 8123)
        self.assertTrue(data["stable"]["use_x_forwarded_for"])

    def test_missing_stable_recovers_and_backs_up_exact_bytes(self):
        before = self.write({"pending": None, "yaml_migration_done": True})
        data = self.run_bootstrap()
        self.assertTrue(data["stable"]["trusted_proxies"])
        self.assertIsNone(data["pending"])
        backup = self.path.with_name("http.before-stable-repair")
        self.assertEqual(backup.read_bytes(), before)
        after = self.path.read_bytes()
        self.run_bootstrap()
        self.assertEqual(self.path.read_bytes(), after)
        self.assertEqual(backup.read_bytes(), before)

    def test_null_stable_preserves_valid_pending_settings(self):
        self.write({"stable": None, "pending": {
            "server_port": 9000, "ip_ban_enabled": True,
            "login_attempts_threshold": 5, "trusted_proxies": ["203.0.113.1"],
            "use_x_forwarded_for": True, "error": "not_promoted"}})
        stable = self.run_bootstrap()["stable"]
        self.assertEqual(stable["server_port"], 8123)
        self.assertTrue(stable["ip_ban_enabled"])
        self.assertEqual(stable["login_attempts_threshold"], 5)
        self.assertIn("203.0.113.1/32", stable["trusted_proxies"])
        self.assertIsNone(stable["error"])

    def test_invalid_pending_falls_back_to_olares_defaults(self):
        self.write({"pending": {"server_port": "invalid", "error": None}})
        self.assertEqual(self.run_bootstrap()["stable"]["server_port"], 8123)

    def test_flat_legacy_store_preserves_settings(self):
        self.path.write_text(json.dumps({"version": 1, "key": "http", "data": {
            "server_port": 8123, "login_attempts_threshold": 8}}))
        self.assertEqual(self.run_bootstrap()["stable"]["login_attempts_threshold"], 8)
        self.assertEqual(json.loads(self.path.read_text())["version"], 2)

    def test_valid_stable_is_unchanged(self):
        before = self.write({"stable": {"server_port": 8123,
            "use_x_forwarded_for": True, "trusted_proxies": ["127.0.0.1"],
            "login_attempts_threshold": 9}, "pending": None})
        self.run_bootstrap()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(self.path.with_name("http.before-stable-repair").exists())

    def test_existing_failed_yaml_migration_still_promotes(self):
        self.write({"stable": {"server_port": 8123}, "pending": {
            "server_port": 8123, "use_x_forwarded_for": True,
            "trusted_proxies": ["127.0.0.1"], "error": "not_promoted"}})
        self.assertTrue(self.run_bootstrap()["stable"]["use_x_forwarded_for"])

    def test_corrupt_or_unsupported_store_is_not_overwritten(self):
        for content in ("{bad", "[]", '{"data": []}',
                        '{"version": 3, "key": "http", "data": {}}',
                        '{"version": 2, "key": "http", "data": {"stable": []}}'):
            with self.subTest(content=content):
                self.path.write_text(content)
                with self.assertRaises(SystemExit):
                    bootstrap["main"]()
                self.assertEqual(self.path.read_text(), content)


if __name__ == "__main__":
    # The remote runner supplies bootstrap from the exact Chart source.
    unittest.main()
