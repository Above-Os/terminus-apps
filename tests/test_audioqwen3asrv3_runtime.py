"""Run with python3 -m unittest discover -s tests -p test_audioqwen3asrv3_runtime.py."""
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]


def render():
    return list(yaml.safe_load_all(subprocess.check_output([
        "helm", "template", "audioqwen3asrv3", str(ROOT / "audioqwen3asrv3"),
        "--set", "domain.audioqwen3asrv3=asr.example.com",
        "--set", "userspace.appCommon=/data/Common",
        "--set", "userspace.appCache=/data/Cache/asr",
        "--set", "userspace.appData=/data/Data/asr",
        "--set", "olaresEnv.MODEL_NAME=Qwen/Qwen3-ASR-1.7B",
    ], text=True)))


class RuntimeMigrationTest(unittest.TestCase):
    def setUp(self):
        docs = render()
        pods = {d["metadata"]["name"]: d["spec"]["template"]["spec"]
                for d in docs if d and d["kind"] == "Deployment"}
        init = pods["llminit"]["initContainers"][0]
        self.generation = init["env"][0]["value"]
        engine_env = pods["audioqwen3asrv3"]["containers"][0]["env"]
        self.assertEqual(self.generation, next(e["value"] for e in engine_env
                                              if e["name"] == "RUN_STATE_GENERATION"))
        self.init = init["command"][-1]
        self.wrapper = next(d["data"]["qwen.sh"] for d in docs
                            if d and d["kind"] == "ConfigMap")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name) / "run"
        self.legacy = Path(self.temp.name) / "legacy"
        self.run.mkdir()
        self.legacy.mkdir()
        self.env = dict(os.environ, RUN_STATE_GENERATION=self.generation,
                        WRAPPER_COMMON=str(self.run / "wrappers/common.sh"))

    def cleanup_state(self):
        # Exercise the rendered script without requiring root on the test host.
        script = self.init.replace("/run/llm-init", str(self.run)).replace(
            "/legacy-run-state", str(self.legacy)).replace("chown 1000:1000", "true")
        subprocess.run(["sh", "-ec", script], env=self.env, check=True)

    def test_only_config_migrates_and_common_config_wins(self):
        (self.legacy / "model-spec.json").write_text('{"model":"old"}')
        (self.legacy / "model_download_finish").write_text("stale")
        self.cleanup_state()
        self.assertEqual((self.run / "model-spec.json").read_text(), '{"model":"old"}')
        self.assertFalse((self.run / "model_download_finish").exists())
        (self.run / "model-spec.json").write_text('{"model":"current"}')
        for name in ("model_download_finish", "model_path", "extra_model_path",
                     "engine_args", "engine_restart", "engine_restart_state", "progress_state.json"):
            (self.run / name).write_text("stale")
        self.cleanup_state()
        self.assertEqual((self.run / "model-spec.json").read_text(), '{"model":"current"}')
        self.assertEqual(sorted(p.name for p in self.run.iterdir()),
                         ["model-spec.json", "run_state_generation"])

    def test_engine_started_first_waits_for_cleanup_and_download(self):
        marker = self.run / "launched"
        helper = self.run / "wrappers/common.sh"
        helper.parent.mkdir()
        helper.write_text(f"touch '{marker}'; exit 99\n")
        (self.run / "model_download_finish").write_text("stale")
        (self.run / "run_state_generation").write_text("previous-deployment")
        script = self.wrapper.replace("/run/llm-init", str(self.run)).replace("sleep 5", "sleep 0.02")
        log = open(self.run / "wrapper.log", "w+")
        self.addCleanup(log.close)
        proc = subprocess.Popen(["sh", "-c", script], env=self.env, stdout=log, stderr=log)
        self.addCleanup(lambda: (proc.kill(), proc.wait()) if proc.poll() is None else None)
        deadline = time.monotonic() + 3
        while "waiting for runtime state cleanup" not in (self.run / "wrapper.log").read_text():
            self.assertIsNone(proc.poll())
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.01)
        self.assertFalse(marker.exists())
        self.cleanup_state()
        # llm-init publishes helpers before downloading; this must still not launch.
        helper.write_text(f"wait_for_sentinel() {{ while [ ! -f '{self.run}/model_download_finish' ]; do sleep 0.02; done; }}\n"
                          f"supervise_engine() {{ touch '{marker}'; }}\n")
        time.sleep(0.1)
        self.assertFalse(marker.exists())
        (self.run / "model_download_finish").write_text("new-download-complete")
        self.assertEqual(proc.wait(timeout=3), 0)
        self.assertTrue(marker.exists())


if __name__ == "__main__":
    unittest.main()
