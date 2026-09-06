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


if __name__ == "__main__":
    unittest.main()
