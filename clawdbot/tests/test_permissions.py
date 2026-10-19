"""Run with: python clawdbot/tests/test_permissions.py. No cluster access required."""
from pathlib import Path
import re
import unittest


def recursive_permission_command(script):
    script = re.sub(r"\\\r?\n", " ", script)
    script = "\n".join(line for line in script.splitlines() if not line.lstrip().startswith("#"))
    return bool(re.search(r"\b(?:chown|chmod)\b[^\n;]*(?:--recursive\b|\s-[A-Za-z]*R[A-Za-z]*(?=\s|$))", script))


class StartupPermissions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (Path(__file__).resolve().parents[1] / "templates" / "deployment.yaml").read_text(encoding="utf-8")
        cls.source = source.split("      initContainers:", 1)[1].split("      containers:", 1)[0]
        parts = re.split(r"^        - name: ([a-z0-9-]+)\s*$", cls.source, flags=re.M)
        cls.init = dict(zip(parts[1::2], parts[2::2]))

    def test_no_recursive_permission_rewrite(self):
        self.assertFalse(recursive_permission_command(self.source))

    def test_guard_rejects_recursive_spellings(self):
        for command in ["chown -R 1000:1000 /home/node", "chmod -Rf 700 /home/node", "chown --recursive 1000 /home/linuxbrew", "chmod \\\n-R 700 /home/node"]:
            with self.subTest(command=command):
                self.assertTrue(recursive_permission_command(command))
        self.assertFalse(recursive_permission_command("chown 1000:1000 /home/node"))

    def test_no_whole_tree_drift_scan(self):
        self.assertNotRegex(self.source, r"\bfind\s+[\"']?/home/(?:node|linuxbrew)(?:/|\s|[\"'])")

    def test_seeding_runs_as_owning_user(self):
        for name in ["init-install-brew", "init-chmod-data", "init-skills", "init-openclaw-state"]:
            with self.subTest(container=name):
                self.assertRegex(self.init[name], r"runAsUser:\s+1000\b")
                self.assertRegex(self.init[name], r"runAsGroup:\s+1000\b")
        permissions = self.init["init-permissions"]
        self.assertIn("beclab/aboveos-busybox:", permissions)
        self.assertRegex(permissions, r"runAsUser:\s+0\b")


if __name__ == "__main__":
    unittest.main()
