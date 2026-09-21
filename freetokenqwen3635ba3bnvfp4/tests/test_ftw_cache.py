import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location(
    "prepare_ftw", Path(__file__).parents[1] / "files" / "prepare-ftw.py"
)
ftw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ftw)


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "model.safetensors").write_bytes(b"source")
        self.cache = self.root / "cache"
        self.calls = 0

    def convert(self, out):
        self.calls += 1
        out.mkdir()
        (out / "config.json").write_text("{}")
        (out / "weights.ftw").write_bytes(b"1234")
        (out / "freetoken_weight.json").write_text(json.dumps({
            "tensors": [{"name": "weight"}],
            "shards": [{"file": "weights.ftw", "nbytes": 4}],
        }))

    def prepare(self, identity=None, convert=None):
        return ftw.prepare(self.source, self.cache, identity or {"snapshot": "a"},
                           convert or self.convert)

    def test_complete_cache_is_reused(self):
        first = self.prepare()
        self.assertEqual(first, self.prepare())
        self.assertEqual(self.calls, 1)
        self.assertTrue((first / ".complete").is_file())
        self.assertEqual((self.source / "model.safetensors").read_bytes(), b"source")

    def test_incompatible_source_gets_separate_cache(self):
        first = self.prepare()
        second = self.prepare({"snapshot": "b"})
        self.assertNotEqual(first, second)
        self.assertEqual(self.calls, 2)
        self.assertTrue(first.exists())

    def test_truncated_cache_is_rebuilt(self):
        target = self.prepare()
        (target / "weights.ftw").write_bytes(b"1")
        self.assertEqual(target, self.prepare())
        self.assertEqual(self.calls, 2)
        self.assertTrue(ftw.valid_checkpoint(target))

    def test_failed_or_incomplete_conversion_is_not_published(self):
        def failed(out):
            out.mkdir()
            (out / "weights.ftw").write_bytes(b"partial")
            raise RuntimeError("interrupted")

        with self.assertRaisesRegex(RuntimeError, "interrupted"):
            self.prepare(convert=failed)
        self.assertFalse(list(self.cache.glob("*/.complete")))
        self.assertFalse(list(self.cache.glob("*.partial")))
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            self.prepare(convert=lambda out: out.mkdir())
        self.assertTrue((self.prepare() / ".complete").exists())


if __name__ == "__main__":
    unittest.main()
