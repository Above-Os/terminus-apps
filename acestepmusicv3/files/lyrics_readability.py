"""Keep ACE phonetic conditioning separate from readable Chinese lyrics."""

from __future__ import annotations

import re
from typing import Any


LANGUAGE_TAG = re.compile(r"^\[(?:zh|yue)\]\s*", re.IGNORECASE)
BRACKET_TAG = re.compile(r"\[[^\]\r\n]+\]")
PINYIN_TOKEN = re.compile(r"^[a-züv]+[1-5]$", re.IGNORECASE)
WORD_TOKEN = re.compile(r"[A-Za-züÜvV]+[1-5]?", re.UNICODE)


def _is_han(character: str) -> bool:
    value = ord(character)
    return (
        0x3400 <= value <= 0x4DBF
        or 0x4E00 <= value <= 0x9FFF
        or 0xF900 <= value <= 0xFAFF
        or 0x20000 <= value <= 0x323AF
    )


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
    if han >= 20 and letters and han / len(letters) >= 0.70:
        return "han"
    words = [token for line in lines for token in WORD_TOKEN.findall(line)]
    toned = sum(1 for token in words if PINYIN_TOKEN.fullmatch(token))
    tagged_lines = sum(
        1 for raw in str(lyrics or "").splitlines() if LANGUAGE_TAG.match(raw.strip())
    )
    if words and toned / len(words) >= 0.70 and tagged_lines >= max(1, len(lines) // 2):
        return "phonetic"
    return "invalid"


def validate_readable(phonetic: str, readable: str, language: str) -> None:
    if phonetic_kind(readable, language) != "han":
        raise ValueError("converted lyrics are not readable Chinese characters")
    if len(content_lines(phonetic)) != len(content_lines(readable)):
        raise ValueError("converted lyrics changed the sung line count")
    if section_tags(phonetic) != section_tags(readable):
        raise ValueError("converted lyrics changed the section structure")


def _conversion_prompt(tokenizer: Any, phonetic: str, language: str) -> str:
    dialect = "natural written Cantonese" if language == "yue" else "natural Simplified Chinese"
    return tokenizer.apply_chat_template(
        [
            {
                "role": "system",
                "content": (
                    "# Instruction\nConvert the supplied tone-number Hanyu Pinyin song script into "
                    f"{dialect}. Output only the converted lyrics. Remove [zh] and [yue] pronunciation "
                    "markers, preserve every other bracketed section tag in the same order, preserve "
                    "the exact number and order of sung lines, and do not add, remove, summarize, or "
                    "rewrite any lyric. Never output Pinyin, explanations, Markdown fences, or JSON."
                ),
            },
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
                "top_k": 0,
                "top_p": 0.9,
                "repetition_penalty": 1.0,
                "generation_phase": "understand",
            },
            use_constrained_decoding=False,
            constrained_decoding_debug=False,
            stop_at_reasoning=False,
        )
        try:
            readable = _clean_output(output)
            validate_readable(phonetic, readable, language)
            return readable
        except ValueError as exc:
            last_error = exc
            print(
                f"[lyrics-readability] conversion_failed temperature={temperature:.1f} status={status}",
                flush=True,
            )
    raise ValueError("ACE 5Hz LM could not render readable lyrics") from last_error
