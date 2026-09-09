import json
import pathlib
import re
import unittest


CHART_ROOT = pathlib.Path(__file__).parents[1]


class ChartContractTest(unittest.TestCase):
    def test_persisted_model_card_without_draft_is_refreshed(self):
        downloader = (CHART_ROOT / "templates" / "download.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("elif ! grep -Eq '\"draft\"' \"$card\"; then", downloader)
        self.assertIn(
            "replacing ACE-Step card without music draft support", downloader
        )
        self.assertIn('cp /etc/olares/model-spec.json "$card"', downloader)

        seed = json.loads(
            (CHART_ROOT / "files" / "model-spec.json").read_text(encoding="utf-8")
        )
        self.assertEqual(seed["name"], "ACE-Step/acestep-v15-xl-sft")
        self.assertEqual(seed["mode"], "music_generation")
        self.assertEqual(
            seed["extensions"]["creative"]["operations"],
            ["generate", "repaint", "format", "draft"],
        )
        self.assertIn("zh", seed["extensions"]["music"]["vocal_languages"])
        self.assertTrue(seed["supports"]["supports_music_lyrics_alignment"])
        self.assertIn(
            "replacing ACE-Step card without lyrics alignment support", downloader
        )

    def test_native_alignment_runs_before_save_memory_payload_cleanup(self):
        launcher = (CHART_ROOT / "templates" / "stage-configmap.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("dit_handler.get_lyric_timestamp(", launcher)
        self.assertIn("_build_generate_music_success_payload", launcher)
        self.assertIn("_write_alignment_sidecars(result, captured_alignment)", launcher)
        self.assertLess(
            launcher.index("dit_handler.get_lyric_timestamp("),
            launcher.index("return original_builder(*builder_args, **builder_kwargs)"),
        )

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
        self.assertIn('or getattr(app_state, "_llm_init_error", None) is not None', launcher)
        self.assertIn('app_state._llm_init_error = None', launcher)
        patched_at = launcher.index(
            "route_setup.register_sample_format_routes = "
            "_register_sample_format_routes_with_rearm"
        )
        # api_server builds the app at import time, so a patch applied after
        # that import would never reach the registered routes.
        self.assertLess(patched_at, launcher.index("from acestep.api_server import main"))

    def test_draft_sampling_has_conservative_repetition_defaults(self):
        launcher = (CHART_ROOT / "templates" / "stage-configmap.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn('if kwargs.get("top_p") is None:', launcher)
        self.assertIn('kwargs["top_p"] = 0.9', launcher)
        self.assertIn('if kwargs.get("repetition_penalty") in (None, 1.0):', launcher)
        self.assertIn('kwargs["repetition_penalty"] = 1.08', launcher)
        patched_at = launcher.index("inference.create_sample = _stable_create_sample")
        self.assertLess(patched_at, launcher.index("from acestep.api_server import main"))


if __name__ == "__main__":
    unittest.main()
