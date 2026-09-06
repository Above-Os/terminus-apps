import importlib.util
import io
import pathlib
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

    def test_quality_is_default_and_fast_is_explicit(self):
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
        self.assertEqual(payloads[0]["bpm"], 92)
        self.assertIn("Vocal character: warm female lead", payloads[0]["prompt"])
        self.assertEqual(fast.status_code, 202)
        self.assertEqual(payloads[1]["model"], "acestep-v15-xl-turbo")
        self.assertEqual(payloads[1]["inference_steps"], 8)

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
        self.assertEqual(profile.status_code, 400)
        self.assertEqual(profile.json()["error"]["code"], "invalid_quality_profile")
        self.assertEqual(guidance.status_code, 400)
        self.assertEqual(guidance.json()["error"]["code"], "invalid_guidance_scale")
        self.assertEqual(unknown.status_code, 400)
        self.assertEqual(unknown.json()["error"]["code"], "unknown_provider_option")


if __name__ == "__main__":
    unittest.main()
