import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "files" / "lyrics_readability.py"
SPEC = importlib.util.spec_from_file_location("lyrics_readability", MODULE_PATH)
readability = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(readability)


PHONETIC = """[Verse 1]
[zh] ye4 se4 luo4 zai4 jian1 shang4
[zh] lu4 deng1 ba3 ying3 zi5 la1 chang2

[Chorus]
[zh] zai4 zou3 yi1 duan4
[zh] jiu4 dao4 jia1 le5"""

READABLE = """[Verse 1]
夜色落在肩上
路灯把影子拉长

[Chorus]
再走一段
就到家了再见故乡"""


class FakeTokenizer:
    def apply_chat_template(self, messages, **_kwargs):
        return "\n".join(message["content"] for message in messages)


class FakeHandler:
    def __init__(self, outputs):
        self.llm_tokenizer = FakeTokenizer()
        self.outputs = iter(outputs)
        self.calls = []

    def generate_from_formatted_prompt(self, **kwargs):
        self.calls.append(kwargs)
        return next(self.outputs), "ok"


class ConstrainedFakeHandler:
    def __init__(self):
        self.llm_tokenizer = FakeTokenizer()
        self.calls = []
        self.transcriptions = {
            "ye4 se4 luo4 zai4 jian1 shang4": "夜色落在肩上",
            "lu4 deng1 ba3 ying3 zi5 la1 chang2": "路灯把影子拉长",
            "zai4 zou3 yi1 duan4": "再走一段",
            "jiu4 dao4 jia1 le5": "就到家了再见故乡",
        }

    def olares_generate_han_line(self, prompt, **kwargs):
        self.calls.append({"prompt": prompt, **kwargs})
        source = next(key for key in self.transcriptions if prompt.rstrip().endswith(key))
        return self.transcriptions[source]


class LyricsReadabilityTest(unittest.TestCase):
    def test_recognizes_official_tone_number_phonetics(self):
        self.assertEqual(readability.phonetic_kind(PHONETIC, "zh"), "phonetic")
        self.assertEqual(readability.phonetic_kind(READABLE, "zh"), "han")
        self.assertEqual(readability.phonetic_kind("[Verse]\nloram ipsum dolor sit amet", "zh"), "invalid")

    def test_rejects_a_pure_latin_gibberish_line_inside_han_lyrics(self):
        mixed = READABLE.replace("再走一段", "théwēi yīfān lìch gōng")
        self.assertEqual(readability.phonetic_kind(mixed, "zh"), "invalid")
        hook = READABLE.replace("再走一段", "yeah oh")
        self.assertEqual(readability.phonetic_kind(hook, "zh"), "han")

    def test_converts_with_the_same_ace_handler(self):
        handler = FakeHandler(["<think>done</think>\n# Readable Lyric\n" + READABLE])
        self.assertEqual(readability.render_readable_lyrics(handler, PHONETIC, "zh"), READABLE)
        self.assertEqual(len(handler.calls), 1)
        self.assertFalse(handler.calls[0]["use_constrained_decoding"])
        self.assertEqual(handler.calls[0]["cfg"]["target_duration"], 10)
        self.assertEqual(handler.calls[0]["cfg"]["repetition_penalty"], 1.08)
        self.assertIn("夜色落在肩上", handler.calls[0]["formatted_prompt"])
        self.assertIn("[zh] ye4 se4 luo4", handler.calls[0]["formatted_prompt"])

    def test_converts_each_line_through_han_constrained_ace_sampling(self):
        handler = ConstrainedFakeHandler()
        self.assertEqual(readability.render_readable_lyrics(handler, PHONETIC, "zh"), READABLE)
        self.assertEqual(len(handler.calls), 4)
        self.assertTrue(all(call["temperature"] == 0.2 for call in handler.calls))
        self.assertTrue(all("[zh]" not in call["prompt"] for call in handler.calls))
        self.assertIn("夜色落在肩上", handler.calls[0]["prompt"])

    def test_uses_cantonese_few_shot_example(self):
        prompt = readability._conversion_prompt(FakeTokenizer(), PHONETIC, "yue")
        self.assertIn("晚风吹过街口", prompt)
        self.assertIn("[yue] maan5 fung1", prompt)

    def test_restores_source_structure_instead_of_trusting_generated_tags(self):
        bad = READABLE.replace("[Chorus]", "[Bridge]")
        handler = FakeHandler([bad])
        self.assertEqual(readability.render_readable_lyrics(handler, PHONETIC, "zh"), READABLE)
        self.assertEqual(len(handler.calls), 1)

    def test_retries_low_temperature_after_changed_line_count(self):
        handler = FakeHandler([READABLE + "\n多出一行中文歌词", READABLE])
        self.assertEqual(readability.render_readable_lyrics(handler, PHONETIC, "zh"), READABLE)
        self.assertEqual([call["cfg"]["temperature"] for call in handler.calls], [0.2, 0.1])

    def test_rejects_changed_line_count(self):
        with self.assertRaisesRegex(ValueError, "line count"):
            readability.validate_readable(PHONETIC, READABLE + "\n多出一行中文歌词", "zh")


if __name__ == "__main__":
    unittest.main()
