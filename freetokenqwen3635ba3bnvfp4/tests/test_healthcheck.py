from contextlib import redirect_stderr
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "files" / "freetoken-healthcheck.py"
spec = importlib.util.spec_from_file_location("healthcheck", SCRIPT)
healthcheck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(healthcheck)


class HealthcheckTests(unittest.TestCase):
    def check_response(self, state, *, live=False):
        # HTTP success alone must not imply model readiness.
        response = io.BytesIO(json.dumps(state).encode())
        error = io.StringIO()
        with patch.object(healthcheck.urllib.request, "build_opener") as opener:
            opener.return_value.open.return_value = response
            with patch.object(healthcheck.sys, "argv", ["healthcheck"] + (["--live"] if live else [])):
                with redirect_stderr(error):
                    result = healthcheck.main()
        return result, error.getvalue()

    def test_loading_is_unready_but_alive(self):
        state = {"status": "loading", "phase": "experts"}
        code, error = self.check_response(state)
        self.assertEqual(code, 1)
        self.assertIn("status=loading", error)
        self.assertIn("phase=experts", error)
        self.assertEqual(self.check_response(state, live=True)[0], 0)

    def test_failed_maintenance_is_not_alive_despite_ok_status(self):
        state = {"status": "ok", "maintenance": "failed"}
        self.assertEqual(self.check_response(state)[0], 1)
        self.assertEqual(self.check_response(state, live=True)[0], 1)

    def test_rebuild_is_alive_but_unready(self):
        state = {"status": "ok", "maintenance": "rebuilding"}
        self.assertEqual(self.check_response(state)[0], 1)
        self.assertEqual(self.check_response(state, live=True)[0], 0)

    def test_serving_is_ready(self):
        state = {"status": "ok", "maintenance": "serving"}
        self.assertEqual(self.check_response(state), (0, ""))
        self.assertEqual(self.check_response(state, live=True), (0, ""))

    def test_errors_and_invalid_json_shapes_fail_closed(self):
        for state in ({"status": "error"}, {}, None, [], True):
            for live in (False, True):
                with self.subTest(state=state, live=live):
                    self.assertEqual(self.check_response(state, live=live)[0], 1)

    def test_chart_and_image_scripts_stay_in_sync(self):
        source = Path(__file__).parents[2] / "deploy" / "freetoken" / "healthcheck.py"
        if not source.is_file():
            self.skipTest("FreeToken image source is not included in this chart repository")
        self.assertEqual(SCRIPT.read_bytes(), source.read_bytes())


if __name__ == "__main__":
    unittest.main()
