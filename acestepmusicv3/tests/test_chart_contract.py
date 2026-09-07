import pathlib
import re
import unittest


CHART_ROOT = pathlib.Path(__file__).parents[1]


class ChartContractTest(unittest.TestCase):
    def test_single_worker_never_enables_turbo_loading(self):
        server = (CHART_ROOT / "templates" / "server.yaml").read_text(encoding="utf-8")
        downloader = (CHART_ROOT / "templates" / "download.yaml").read_text(encoding="utf-8")
        self.assertNotIn("ACESTEP_ON_DEMAND_MODEL_LOAD", server)
        self.assertNotIn("models--ACE-Step--acestep-v15-xl-turbo", server)
        self.assertNotIn("hf://ACE-Step/acestep-v15-xl-turbo", downloader)
        for name in ("ACESTEP_API_WORKERS", "ACESTEP_QUEUE_WORKERS"):
            self.assertRegex(
                server,
                rf"name: {re.escape(name)}\s+value: \"1\"",
            )

    def test_xl_sft_generation_forces_dcw_off(self):
        launcher = (CHART_ROOT / "templates" / "stage-configmap.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn('params.dcw_enabled = False', launcher)
        self.assertIn('disabling DCW for XL-SFT', launcher)

    def test_text_only_lm_routes_are_rearmed_before_the_api_server_loads(self):
        launcher = (CHART_ROOT / "templates" / "stage-configmap.yaml").read_text(
            encoding="utf-8"
        )
        for name in ("format_sample", "create_sample_fn"):
            self.assertIn(
                f'kwargs["{name}"] = _with_rearm(kwargs["{name}"])', launcher
            )
        patched_at = launcher.index(
            "route_setup.register_sample_format_routes = "
            "_register_sample_format_routes_with_rearm"
        )
        # api_server builds the app at import time, so a patch applied after
        # that import would never reach the registered routes.
        self.assertLess(patched_at, launcher.index("from acestep.api_server import main"))


if __name__ == "__main__":
    unittest.main()
