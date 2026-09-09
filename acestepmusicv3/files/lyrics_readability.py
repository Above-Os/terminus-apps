"""Keep ACE phonetic conditioning separate from readable Chinese lyrics."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


LANGUAGE_TAG = re.compile(r"^\[(?:zh|yue)\]\s*", re.IGNORECASE)
BRACKET_TAG = re.compile(r"\[[^\]\r\n]+\]")
PINYIN_TOKEN = re.compile(r"^[a-züv]+[1-5]$", re.IGNORECASE)
WORD_TOKEN = re.compile(r"[A-Za-züÜvV]+[1-5]?", re.UNICODE)
ENGLISH_HOOK_WORDS = frozenset({"baby", "hey", "i", "la", "love", "na", "oh", "tonight", "woo", "yeah", "you"})


def _is_han(character: str) -> bool:
    value = ord(character)
    return (
        0x3400 <= value <= 0x4DBF
        or 0x4E00 <= value <= 0x9FFF
        or 0xF900 <= value <= 0xFAFF
        or 0x20000 <= value <= 0x323AF
    )


def _is_latin(character: str) -> bool:
    return character.isalpha() and "LATIN" in unicodedata.name(character, "")


def _latin_words(line: str) -> list[str]:
    words: list[str] = []
    current: list[str] = []
    for character in line:
        if _is_latin(character):
            current.append(character)
        elif current:
            words.append("".join(current).lower())
            current = []
    if current:
        words.append("".join(current).lower())
    return words


def _has_disallowed_latin_line(lines: list[str]) -> bool:
    for line in lines:
        words = _latin_words(line)
        if not words:
            continue
        if any(word not in ENGLISH_HOOK_WORDS for word in words) or len(words) > 4:
            return True
    return False


def content_lines(lyrics: str) -> list[str]:
    lines: list[str] = []
    for raw in str(lyrics or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        without_language = LANGUAGE_TAG.sub("", line)
        without_tags = BRACKET_TAG.sub("", without_language).strip()
        if without_tags:
            lines.append(without_tags)
    return lines


def section_tags(lyrics: str) -> list[str]:
    return [
        tag
        for tag in BRACKET_TAG.findall(str(lyrics or ""))
        if tag.lower() not in {"[zh]", "[yue]"}
    ]


def phonetic_kind(lyrics: str, language: str) -> str:
    """Return ``han``, ``phonetic`` or ``invalid`` for Chinese-language text."""
    if language not in {"zh", "yue"}:
        return "han"
    lines = content_lines(lyrics)
    if not lines:
        return "invalid"
    letters = [character for line in lines for character in line if character.isalpha()]
    han = sum(1 for character in letters if _is_han(character))
    words = [token for line in lines for token in WORD_TOKEN.findall(line)]
    toned = sum(1 for token in words if PINYIN_TOKEN.fullmatch(token))
    tagged_lines = sum(
        1 for raw in str(lyrics or "").splitlines() if LANGUAGE_TAG.match(raw.strip())
    )
    if words and toned / len(words) >= 0.70 and tagged_lines >= max(1, len(lines) // 2):
        return "phonetic"
    if han >= 20 and letters and han / len(letters) >= 0.70 and not _has_disallowed_latin_line(lines):
        return "han"
    return "invalid"


def validate_readable(phonetic: str, readable: str, language: str) -> None:
    if phonetic_kind(readable, language) != "han":
        raise ValueError("converted lyrics are not readable Chinese characters")
    if len(content_lines(phonetic)) != len(content_lines(readable)):
        raise ValueError("converted lyrics changed the sung line count")
    if section_tags(phonetic) != section_tags(readable):
        raise ValueError("converted lyrics changed the section structure")


def _restore_structure(phonetic: str, readable: str) -> str:
    """Put converted sung lines back into the exact source section structure."""
    converted = iter(content_lines(readable))
    output: list[str] = []
    for raw in str(phonetic or "").splitlines():
        stripped = raw.strip()
        if not stripped:
            output.append("")
            continue
        source_content = BRACKET_TAG.sub("", LANGUAGE_TAG.sub("", stripped)).strip()
        tags = [
            tag for tag in BRACKET_TAG.findall(stripped)
            if tag.lower() not in {"[zh]", "[yue]"}
        ]
        if source_content:
            if tags:
                output.append(" ".join(tags))
            output.append(next(converted))
        elif tags:
            output.append(" ".join(tags))
    try:
        next(converted)
    except StopIteration:
        return "\n".join(output).strip()
    raise ValueError("converted lyrics added sung lines")


def _conversion_prompt(tokenizer: Any, phonetic: str, language: str) -> str:
    dialect = "natural written Cantonese" if language == "yue" else "natural Simplified Chinese"
    if language == "yue":
        example_phonetic = """[Verse 1]
[yue] maan5 fung1 ceoi1 gwo3 gaai1 hau2
[yue] jat1 zaan2 dang1 ziu3 zoeng6 nei5"""
        example_readable = """[Verse 1]
晚风吹过街口
一盏灯照着你"""
    else:
        example_phonetic = """[Verse 1]
[zh] ye4 se4 luo4 zai4 jian1 shang4
[zh] lu4 deng1 ba3 ying3 zi5 la1 chang2

[Chorus]
[zh] zai4 zou3 yi1 duan4 jiu4 dao4 jia1 le5"""
        example_readable = """[Verse 1]
夜色落在肩上
路灯把影子拉长

[Chorus]
再走一段就到家了"""
    return tokenizer.apply_chat_template(
        [
            {
                "role": "system",
                "content": (
                    "# Instruction\nConvert the supplied tone-number Hanyu Pinyin song script into "
                    f"{dialect}. Answer under the heading '# Readable Lyric'. Remove [zh] and [yue] pronunciation "
                    "markers, preserve every other bracketed section tag in the same order, preserve "
                    "the exact number and order of sung lines, and do not add, remove, summarize, or "
                    "rewrite any lyric. Never output Pinyin, explanations, Markdown fences, or JSON."
                ),
            },
            {"role": "user", "content": "# Phonetic Lyric\n" + example_phonetic},
            {"role": "assistant", "content": "# Readable Lyric\n" + example_readable},
            {"role": "user", "content": "# Phonetic Lyric\n" + phonetic},
        ],
        tokenize=False,
        add_generation_prompt=True,
    )


def _clean_output(value: str) -> str:
    text = str(value or "").strip()
    if "</think>" in text:
        text = text.split("</think>", 1)[1].strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        text = text[first_newline + 1 :] if first_newline >= 0 else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    lines = text.strip().splitlines()
    if lines and lines[0].strip().lower() in {"# readable lyric", "# readable lyrics"}:
        text = "\n".join(lines[1:])
    return text.strip()


def render_readable_lyrics(llm_handler: Any, phonetic: str, language: str) -> str:
    """Use the already-loaded ACE 5Hz LM, never an external chat model."""
    prompt = _conversion_prompt(llm_handler.llm_tokenizer, phonetic, language)
    last_error: Exception | None = None
    for temperature in (0.2, 0.1):
        output, status = llm_handler.generate_from_formatted_prompt(
            formatted_prompt=prompt,
            cfg={
                "temperature": temperature,
                # ACE's bundled sampler requires a strictly positive top_k.
                # Forty keeps conversion deterministic enough at 0.2/0.1
                # without tripping the native assertion.
                "top_k": 40,
                "top_p": 0.9,
                "repetition_penalty": 1.08,
                # This API has no max_tokens argument. In ACE 0.1.8 the
                # supported target_duration field bounds CoT output to
                # duration*5+500 tokens. Keep it fixed at the minimum because
                # this is transcription, not open-ended song generation.
                "target_duration": 10,
                "generation_phase": "understand",
            },
            use_constrained_decoding=False,
            constrained_decoding_debug=False,
            stop_at_reasoning=False,
        )
        try:
            readable = _clean_output(output)
            if phonetic_kind(readable, language) != "han":
                raise ValueError("converted lyrics are not readable Chinese characters")
            if len(content_lines(phonetic)) != len(content_lines(readable)):
                raise ValueError("converted lyrics changed the sung line count")
            restored = _restore_structure(phonetic, readable)
            validate_readable(phonetic, restored, language)
            return restored
        except ValueError as exc:
            last_error = exc
            print(
                f"[lyrics-readability] conversion_failed temperature={temperature:.1f} "
                f"reason={str(exc).replace(' ', '_')} status={status}",
                flush=True,
            )
    raise ValueError("ACE 5Hz LM could not render readable lyrics") from last_error
