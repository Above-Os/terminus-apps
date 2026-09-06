import importlib.util
import base64
import io
import pathlib
import tempfile
import unittest
from email.message import Message
from unittest import mock

from fastapi.testclient import TestClient


MODULE_PATH = pathlib.Path(__file__).parents[1] / "files" / "music_adapter.py"
SPEC = importlib.util.spec_from_file_location("music_adapter", MODULE_PATH)
adapter = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(adapter)


class AudioResponse(io.BytesIO):
    def __init__(self, body: bytes):
        super().__init__(body)
        self.headers = Message()
        self.headers["Content-Type"] = "audio/wav"


class MusicAdapterContractTest(unittest.TestCase):
    def setUp(self):
        adapter.TASKS.clear()
        self.client = TestClient(adapter.app)
        self.temp_directory = tempfile.TemporaryDirectory()
        self.temp_dir = pathlib.Path(self.temp_directory.name)

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_create_poll_content_and_contract_errors(self):
        def native(path, _payload=None):
            if path == "/release_task":
                return {"code": 200, "data": {"task_id": "task-1"}}
            if path == "/query_result":
                return {
                    "code": 200,
                    "data": [{
                        "task_id": "task-1",
                        "status": 1,
                        "result": '[{"file":"/v1/audio?path=%2Ftmp%2Fsong.wav","metas":{"duration":240}}]',
                    }],
                }
            raise AssertionError(path)

        with mock.patch.object(adapter, "_native_json", side_effect=native):
            created = self.client.post(
                "/v1/music/generations",
                json={"model": "ace", "prompt": "Mandarin indie pop", "lyrics": "[Verse 1]\n雨", "duration_seconds": 240},
            )
            self.assertEqual(created.status_code, 202)
            self.assertEqual(created.json()["status"], "queued")

            completed = self.client.get("/v1/music/generations/task-1")
            self.assertEqual(completed.status_code, 200)
            body = completed.json()
            self.assertEqual(body["status"], "completed")
            self.assertEqual(body["outputs"][0]["duration_seconds"], 240)
            output_id = body["outputs"][0]["id"]

        with mock.patch.object(adapter.urllib.request, "urlopen", return_value=AudioResponse(b"RIFFmusic")):
            content = self.client.get(f"/v1/music/generations/task-1/content?output_id={output_id}")
            self.assertEqual(content.status_code, 200)
            self.assertEqual(content.headers["content-type"], "audio/wav")
            self.assertEqual(content.content, b"RIFFmusic")

        cancel = self.client.delete("/v1/music/generations/task-1")
        self.assertEqual(cancel.status_code, 422)
        self.assertEqual(cancel.json()["error"]["code"], "cancellation_unsupported")
        lost = self.client.get("/v1/music/generations/from-old-process")
        self.assertEqual(lost.status_code, 410)
        self.assertEqual(lost.json()["error"]["code"], "task_lost")

    def test_instrumental_rejects_lyrics_and_engine_spec_is_single_worker(self):
        response = self.client.post(
            "/v1/music/generations",
            json={"prompt": "ambient", "lyrics": "words", "instrumental": True},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "lyrics_not_allowed")
        spec = self.client.get("/api/engine-spec").json()
        self.assertEqual(spec["mode"], "music_generation")
        self.assertEqual(spec["max_concurrency"], 1)
        self.assertEqual(spec["serves"], ["music.generate", "music.repaint"])
        self.assertEqual(spec["extensions"]["music"]["default_quality_profile"], "high_quality")
        self.assertEqual(spec["extensions"]["music"]["default_production_profile"], "clean")
        self.assertEqual(spec["extensions"]["music"]["default_caption_mode"], "preserve")

    def test_quality_profiles_use_xl_sft_without_repeating_structure_in_caption(self):
        payloads = []

        def native(path, payload=None):
            self.assertEqual(path, "/release_task")
            payloads.append(payload)
            return {"code": 200, "data": {"task_id": f"task-{len(payloads)}"}}

        with mock.patch.object(adapter, "_native_json", side_effect=native):
            quality = self.client.post(
                "/v1/music/generations",
                json={
                    "prompt": "Mandarin pop",
                    "duration_seconds": 180,
                    "provider_options": {
                        "quality_profile": "quality",
                        "bpm": 92,
                        "key_scale": "D major",
                        "time_signature": "4",
                        "vocal_language": "zh",
                        "vocal_type": "warm female lead",
                        "section_structure": "intro, verse, chorus, bridge, chorus, outro",
                    },
                },
            )
            fast = self.client.post(
                "/v1/music/generations",
                json={"prompt": "pop", "provider_options": {"quality_profile": "fast"}},
            )

        self.assertEqual(quality.status_code, 202)
        self.assertEqual(payloads[0]["model"], "acestep-v15-xl-sft")
        self.assertEqual(payloads[0]["inference_steps"], 50)
        self.assertEqual(payloads[0]["guidance_scale"], 7.0)
        self.assertEqual(payloads[0]["shift"], 1.0)
        self.assertFalse(payloads[0]["use_adg"])
        self.assertFalse(payloads[0]["use_cot_caption"])
        self.assertFalse(payloads[0]["use_cot_lyrics"])
        self.assertIn("background hiss", payloads[0]["lm_negative_prompt"])
        self.assertEqual(payloads[0]["bpm"], 92)
        self.assertIn("Vocal character: warm female lead", payloads[0]["prompt"])
        self.assertNotIn("Song structure:", payloads[0]["prompt"])
        self.assertEqual(fast.status_code, 400)
        self.assertEqual(fast.json()["error"]["code"], "invalid_quality_profile")
        self.assertEqual(len(payloads), 1)

        with mock.patch.object(adapter, "_native_json", side_effect=native):
            high = self.client.post(
                "/v1/music/generations",
                json={"prompt": "Mandarin pop", "provider_options": {"quality_profile": "high_quality"}},
            )
        self.assertEqual(high.status_code, 202)
        self.assertEqual(payloads[1]["model"], "acestep-v15-xl-sft")
        self.assertEqual(payloads[1]["inference_steps"], 64)
        self.assertTrue(payloads[1]["use_adg"])
        self.assertEqual(payloads[1]["guidance_scale"], 8.0)
        self.assertEqual(payloads[1]["shift"], 3.0)

    def test_clean_and_textured_production_and_caption_modes(self):
        payloads = []

        def native(path, payload=None):
            self.assertEqual(path, "/release_task")
            payloads.append(payload)
            return {"code": 200, "data": {"task_id": f"task-{len(payloads)}"}}

        with mock.patch.object(adapter, "_native_json", side_effect=native):
            clean = self.client.post(
                "/v1/music/generations",
                json={"prompt": "polished Mandarin pop", "provider_options": {"production_profile": "clean", "caption_mode": "preserve"}},
            )
            textured = self.client.post(
                "/v1/music/generations",
                json={"prompt": "lo-fi rainy folk", "provider_options": {"production_profile": "textured", "caption_mode": "enhance"}},
            )

        self.assertEqual(clean.status_code, 202)
        self.assertFalse(payloads[0]["use_cot_caption"])
        self.assertIn("clean studio recording", payloads[0]["prompt"])
        self.assertIn("background hiss", payloads[0]["lm_negative_prompt"])
        self.assertEqual(textured.status_code, 202)
        self.assertTrue(payloads[1]["use_cot_caption"])
        self.assertNotIn("lm_negative_prompt", payloads[1])
        self.assertNotIn("clean studio recording", payloads[1]["prompt"])

    def test_repaint_decodes_audio_and_maps_native_range(self):
        payloads = []

        def native(path, payload=None):
            self.assertEqual(path, "/release_task")
            payloads.append(payload)
            return {"code": 200, "data": {"task_id": "repaint-1"}}

        with mock.patch.object(adapter, "_native_json", side_effect=native), mock.patch.object(
            adapter, "REPAINT_INPUT_DIR", str(self.temp_dir)
        ):
            response = self.client.post(
                "/v1/music/generations",
                json={
                    "operation": "repaint",
                    "prompt": "Mandarin indie pop with a clean vocal pickup",
                    "input_audio": "data:audio/wav;base64," + base64.b64encode(b"RIFFaudio").decode(),
                    "duration_seconds": 240,
                    "provider_options": {"repaint_start_seconds": 32, "repaint_end_seconds": 48},
                },
            )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(payloads[0]["task_type"], "repaint")
        self.assertEqual(payloads[0]["repainting_start"], 32)
        self.assertEqual(payloads[0]["repainting_end"], 48)
        self.assertTrue(payloads[0]["src_audio_path"].startswith(str(self.temp_dir)))

    def test_rejects_invalid_quality_controls(self):
        profile = self.client.post(
            "/v1/music/generations",
            json={"prompt": "pop", "provider_options": {"quality_profile": "ultra"}},
        )
        guidance = self.client.post(
            "/v1/music/generations",
            json={"prompt": "pop", "provider_options": {"guidance_scale": 12}},
        )
        unknown = self.client.post(
            "/v1/music/generations",
            json={"prompt": "pop", "provider_options": {"magic": True}},
        )
        production = self.client.post(
            "/v1/music/generations",
            json={"prompt": "pop", "provider_options": {"production_profile": "dusty"}},
        )
        caption = self.client.post(
            "/v1/music/generations",
            json={"prompt": "pop", "provider_options": {"caption_mode": "rewrite"}},
        )
        self.assertEqual(profile.status_code, 400)
        self.assertEqual(profile.json()["error"]["code"], "invalid_quality_profile")
        self.assertEqual(guidance.status_code, 400)
        self.assertEqual(guidance.json()["error"]["code"], "invalid_guidance_scale")
        self.assertEqual(unknown.status_code, 400)
        self.assertEqual(unknown.json()["error"]["code"], "unknown_provider_option")
        self.assertEqual(production.json()["error"]["code"], "invalid_production_profile")
        self.assertEqual(caption.json()["error"]["code"], "invalid_caption_mode")


if __name__ == "__main__":
    unittest.main()
