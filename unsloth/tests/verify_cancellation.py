"""Run in the pinned image: python tests/verify_cancellation.py SOURCE PATCH_SCRIPT.

Uses real Linux processes, including a descendant that ignores SIGTERM. No model,
GPU, application history or authentication data is touched.
"""

import ast
import importlib.util
import logging
import multiprocessing as mp
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest

import psutil


SOURCE = Path(sys.argv.pop(1)).read_text(encoding="utf-8")
PATCH = Path(sys.argv.pop(1))
spec = importlib.util.spec_from_file_location("prepare_runtime", PATCH)
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)


def method_namespace(source):
    tree = ast.parse(source)
    selected = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                and node.name in {"force_terminate", "_olares_terminate_descendants",
                                  "_olares_reap_descendants", "_terminate_descendants",
                                  "_reap_descendants"}]
    namespace = {"logger": logging.getLogger("test"), "account_is_retired": lambda: False}
    exec(compile(ast.Module(body=selected, type_ignores=[]), "training.py", "exec"), namespace)
    return namespace


def blocked_worker(pid_file):
    # A nested installer/compiler survives termination of just its training parent.
    code = ("import os,signal,time; from pathlib import Path; "
            "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
            f"Path({pid_file!r}).write_text(str(os.getpid())); time.sleep(300)")
    installer = subprocess.Popen([sys.executable, "-c", code])
    installer.wait()


class RuntimeTests(unittest.TestCase):
    def test_patch_compiles_and_preserves_every_other_method(self):
        patched = patcher.patch_training(SOURCE)
        old, new = ast.parse(SOURCE), ast.parse(patched)
        def functions(tree):
            return {node.name: ast.dump(node) for node in ast.walk(tree)
                    if isinstance(node, ast.FunctionDef) and node.name != "force_terminate"}
        original, result = functions(old), functions(new)
        for name, body in original.items():
            self.assertEqual(body, result[name], name)

    def test_unknown_source_is_rejected(self):
        with self.assertRaises(ValueError):
            patcher.patch_training("def unrelated(): pass\n")
        if "def _terminate_descendants(" in SOURCE:
            self.assertEqual(patcher.patch_training(SOURCE), SOURCE)
        else:
            with self.assertRaises(ValueError):
                patcher.patch_training(patcher.patch_training(SOURCE))

    def test_superseded_worker_is_not_touched(self):
        namespace = method_namespace(patcher.patch_training(SOURCE))
        namespace["_olares_terminate_descendants"] = lambda pid: self.fail("Stale run killed children")
        namespace["_terminate_descendants"] = lambda pid: self.fail("Stale run killed children")
        backend = types.SimpleNamespace(_lock=threading.RLock(), _proc=object())
        namespace["force_terminate"](backend, target_proc=object())

    @unittest.skipUnless(sys.platform == "linux", "Linux process regression")
    def test_force_cancel_reaps_blocked_installer(self):
        self.check_cancel(patcher.patch_training(SOURCE), expect_reaped=True)

    @unittest.skipUnless(sys.platform == "linux", "Linux process regression")
    def test_unmodified_source_descendant_cleanup(self):
        self.check_cancel(SOURCE, expect_reaped="def _terminate_descendants(" in SOURCE)

    def check_cancel(self, source, *, expect_reaped):
        namespace = method_namespace(source)
        with tempfile.TemporaryDirectory() as temp:
            pid_file = str(Path(temp) / "installer.pid")
            proc = mp.get_context("fork").Process(target=blocked_worker, args=(pid_file,))
            proc.start()
            child = None
            try:
                deadline = time.monotonic() + 10
                while not Path(pid_file).exists() and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue(Path(pid_file).exists(), "Installer did not start")
                child = psutil.Process(int(Path(pid_file).read_text()))
                backend = types.SimpleNamespace(
                    _lock=threading.RLock(), _proc=proc, _cancel_requested=False,
                    _cancel_cleanup_output_dir=None, _output_dir=None, _pump_thread=None,
                )
                namespace["force_terminate"](backend, target_proc=proc)
                self.assertFalse(proc.is_alive(), "Training worker survived")
                if expect_reaped:
                    try:
                        child.wait(timeout=2)
                    except psutil.TimeoutExpired:
                        pass
                reaped = not child.is_running() or child.status() == psutil.STATUS_ZOMBIE
                self.assertEqual(reaped, expect_reaped,
                                 "Unexpected installer liveness after cancellation")
            finally:
                if child is not None and child.is_running():
                    try:
                        child.kill()
                    except psutil.NoSuchProcess:
                        pass
                if proc.is_alive():
                    proc.kill()
                proc.join(5)


if __name__ == "__main__":
    unittest.main()
