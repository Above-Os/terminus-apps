"""Prompt rewriting through an OpenAI-compatible chat endpoint (Olares Router)."""
import asyncio
import json
import logging
import os
import re
import time
import unicodedata

from aiohttp import ClientSession, ClientTimeout

from .graph import CJK

log = logging.getLogger("comfyapp.studio")

REF = re.compile(r"\{\{[^{}]+\}\}")
QUOTED = re.compile(r'''"[^"]*"|“[^”]*”|‘[^’]*’|「[^」]*」|『[^』]*』|(?<![A-Za-z])'[^']*'(?![A-Za-z])''')
WORD = re.compile(r"[^\W\d_]+")
LATIN_SENTENCE = re.compile(r"\b[A-Za-z]+(?:['’-][A-Za-z]+)*(?:[ \t]+[A-Za-z]+(?:['’-][A-Za-z]+)*){6}\b")
THINK = re.compile(r"<think>.*?</think>", re.S)
FENCE = re.compile(r"^```[\w-]*\n(.*?)\n```$", re.S)
USER_PROMPT_DIVIDER = "\n\nUser prompt:\n"
IMAGE_JOB_HEADER = re.compile(r"^(?:Task: (?:generate an image|edit the input images)[ \t]*(?:\r?\n|$)|Output language:|User prompt:)")
IMAGE_PROMPT_HEADING = re.compile(
    r"^[ \t]*(?:#{1,6}[ \t]+)?(?:\*\*)?"
    r"(?:最终提示词|润色后的提示词|提示词|final (?:image )?prompt|rewritten prompt)"
    r"[ \t]*(?:\*\*)?[:：][ \t]*(?:\*\*)?[ \t]*",
    re.I | re.M,
)
IMAGE_PROMPT_POSTSCRIPT = re.compile(
    r"^[ \t]*(?:[（(][ \t]*)?(?:提示词(?:已|中已)(?:包含|涵盖|保留)"
    r"|the (?:rewritten|enhanced|final) prompt (?:includes|preserves))[^\n]*\s*\Z",
    re.I | re.M,
)
IMAGE_TEMPLATE_NOTE = re.compile(
    r"语言决定\s*[（(]\s*[AB]\s*[）)]|\b(?:language\s+)?decision\s*\([AB]\)"
    r"|\boutput only the rewritten prompt\b|只输出(?:润色后的)?提示词正文|/思[维考]"
    r"|扩展内容如下\s*[:：]|^[ \t#*]*(?:参考图片中的内容|润色后的提示词|here is the (?:enhanced|rewritten) prompt)\s*[:：]",
    re.I | re.M,
)
SHORT_HAN_PROMPT = re.compile(r"[\u3400-\u9fff]{1,4}")
VIDEO_JOB_HEADER = re.compile(r"^(?:Mode: [\w-]+[ \t]*(?:\r?\n|$)|Output language:|User prompt:)")
USER_PROMPT_LINE = re.compile(r"^User prompt:[ \t]*\r?\n", re.M)
VIDEO_DIALOGUE = re.compile(r"<d>.*?</d>", re.I | re.S)
VIDEO_SYNTAX = re.compile(r"""(?mx)
    ^[ \t]*(?:subject_definitions|summary|retention_analysis|detailed_description|
             integrated_multimodal_description|overall_soundscape|non_diegetic_music):
    | ^[ \t]*(?:For\ the\ target\ video,\ at\ [^\n]*\ is\ fully\ referenced\.
              | How\ the\ reference\ pictures\ align\ with\ the\ target\ video\ [^\n]*)$
    | <(?:(?:Subject|Picture|Video|Audio)\ \d+|scenetrans|cutoff)>
    | \[(?:Shot\ \d+|reference\ generation|keyframe\ completion|audio\ reuse|audio\ reference)\]
    | \(S\d+(?:,\s*S\d+)*\)
    | \b(?:fully_preserved|partially_preserved|attribute_transfer|weak_reference|fully_copy|partially_copy|N/A)\b
""")
DEFAULT_MODEL = "default-chat"

REFS = ("- Keep every token written as {{...}} exactly as it appears, character for character. They are references to the "
        "user's uploaded assets. Do not translate, rename or drop them.")
ONLY = "- Output only the rewritten prompt. Omit the job details, the User prompt heading, explanations and code fences."
IMAGE_EN = ("Rewrite the entire description in English. Translate the original description and write all added detail "
            "in English. Keep text that must appear in the image in its specified language and wording. "
            "This replaces any other language rule.")
SAME = "Write in the same language as the user's text."
STRUCTURE = """You rewrite a video generation prompt into the structure below.

Rules:
%s
- Keep the user's subjects, characters and actions. Do not add or remove characters or change who they are.
- You may fill in camera work, lighting and sound that fit the description, briefly and concretely.
- %s
%s

Structure:
"""
GENERATE = """You rewrite a short image description into a detailed prompt for a text-to-image model.

Rules:
%s
- Keep the user's subject, the people and objects, and any text they want shown. Do not add or remove subjects.
- Add concrete visual detail that fits: composition and framing, setting, lighting, colors, materials, style or medium.
- Put any words that must appear in the image in double quotes, exactly as the user wrote them.
- One paragraph, at most about 120 words.
- %s
%s
"""
EDIT = """You rewrite an image editing instruction so an image editing model follows it precisely.

Rules:
%s
- The {{...}} tokens are the input images; the first image in the instruction is the one being edited unless the user says otherwise.
- State what to change and where, then what must stay the same (identity, pose, framing, the rest of the scene).
- Do not invent changes the user did not ask for.
- Keep it short: one to three sentences.
- %s
%s
"""
TEXT_EDIT = """Polish the user's image prompt. The reference images are unavailable to you.

%s
- Treat the user's message as the source of truth. Preserve every named subject and requested change.
- If the user gives only a subject, make it the main subject and add concrete details about its appearance, setting and lighting.
- For an editing instruction, clarify the requested change. Describe a reference image only using details the user provides.
- Keep any text the user wants visible in the image verbatim in quotes.
- %s
%s
"""
TEXT_EDIT_ZH = (
    "把用户的文字润色成一段自然的中文生图提示词。保留原文的主体和具体要求，补充与主体有关的可见细节。"
    "有修改要求时，写清要改的内容。参考图的信息以用户的描述为准。"
    "沿用原文的简繁字形和指定的画面文字。直接写润色后的正文。"
)
TRANSLATE = """You translate %s prompt into English.

Rules:
%s
- Translate faithfully. Keep the structure, line breaks and order; do not add, expand or summarize anything.
%s- Text that is already English stays as it is.
%s
"""
IN_IMAGE = ("- Translate all descriptive text under the User prompt heading into English.\n"
            "- Text that must appear in the image, usually in quotes, stays in its original language.\n")
VIDEO_LITERALS = ("Keep field names, shot and speaker markers, reference alignment lines and asset tokens as specified. "
                  "Keep spoken dialogue and text to be shown on screen in their original language and wording.")
IN_VIDEO = "- Translate all descriptive text in the user's message into English. " + VIDEO_LITERALS + "\n"

# Appended to an app's own system prompt (profile.prompts); these win over it.
STUDIO_RULES = """

## Studio rules (these take precedence over anything above)

- The user's message starts with the job: the mode, duration or aspect ratio, and the assets. Assets are written as {{...}} tokens, and the list says what each one is and which label the model will see in its place. Attached images follow the user's prompt, each introduced by its token.
- Keep every {{...}} token from the user's prompt exactly as written, character for character, and refer to the user's assets only by their tokens: never write the label a token turns into, and never translate, rename or drop a token.
- %s
""" + ONLY
LANG_EN = ("Write every descriptive section in English. Translate the original description and write all added detail "
           "in English. " + VIDEO_LITERALS)
LANG_SAME = ("Write the prompt's descriptive text in the same language as the text under the User prompt heading. "
             "Keep the specified field names and fixed markers, and the original language of words shown in the picture "
             "or spoken aloud. "
             "This replaces any other language rule.")

ROLE_TEXT = {"first_frame": "first frame", "last_frame": "last frame", "ref_image": "reference image",
             "ref_video": "reference video", "ref_audio": "reference audio", "mask": "mask"}


def modes(kind, template, prompts=None):
    """The rewrite modes a studio offers: video needs the app's prompts or
    its prompt template, image always has them."""
    if kind == "image":
        return ("enhance_en", "enhance", "translate_en")
    if prompts or template:
        return ("structure_en", "structure", "translate_en")
    return ()


def system_prompt(mode, kind, template, task="generate", flow="", prompts=None, text=None, *, has_image=True):
    """The system prompt for mode, or None when the studio does not offer it.
    task (image): generate or edit. flow (video): the flow's mode, whose
    prompts entry is used after prompts["shared"]. text: the user's prompt;
    translate mentions tokens only when it has some, since a small model
    otherwise writes made-up ones."""
    prompts = prompts or {}
    if mode not in modes(kind, template, prompts):
        return None
    if mode == "translate_en":
        refs = REFS if text is None or REF.search(text) else ""
        if kind == "image":
            return TRANSLATE % ("an image generation or editing", refs, IN_IMAGE, ONLY)
        return TRANSLATE % ("a video generation", refs, IN_VIDEO, ONLY)
    english = mode.endswith("_en")
    own = prompts.get(task) if kind == "image" else prompts.get(flow)
    if kind == "image" and task == "edit" and not has_image:
        refs = REFS if text is None or REF.search(text) else ""
        if not english and source_language(text, kind) == "Chinese":
            if SHORT_HAN_PROMPT.fullmatch(text.rstrip("。.!！")):
                return "围绕用户给出的主体写一段具体的中文画面描述。保留原文的主体名称，从画面本身写起，直接输出一个段落。"
            return TEXT_EDIT_ZH + ("逐字保留 {{...}} 素材引用。" if refs else "")
        return TEXT_EDIT % (refs, IMAGE_EN if english else SAME, ONLY)
    language_header = ""
    if mode in ("enhance", "structure"):
        language_header = same_language_header(text, kind)
    elif mode == "structure_en":
        language_header = LANG_EN + "\n\n"
    if own:
        shared = prompts.get("shared", "") if kind != "image" else ""
        app_prompt = (shared + "\n\n" if shared else "") + own
        english_rule = IMAGE_EN if kind == "image" else LANG_EN
        return language_header + app_prompt + STUDIO_RULES % (english_rule if english else LANG_SAME)
    if kind == "image":
        return language_header + (EDIT if task == "edit" else GENERATE) % (REFS, IMAGE_EN if english else SAME, ONLY)
    if not template:
        return None
    return language_header + STRUCTURE % (REFS, LANG_EN if english else LANG_SAME, ONLY) + template


def job_text(prompt, kind, flow="", duration=None, aspect="", task="", assets=(), *, mode=""):
    """The user message: the job, the assets and the prompt. Repeat the
    selected output language next to the prompt. assets: dicts
    with token, role, kind, duration, label (what the model sees in
    place of the token) and attached (what follows the prompt for it, e.g.
    "image attached")."""
    lines = []
    if kind == "image":
        lines.append("Task: %s" % ("edit the input images" if task == "edit" else "generate an image"))
    else:
        lines.append("Mode: %s" % (flow or "video"))
        if duration:
            lines.append("Duration: %g seconds" % float(duration))
    if aspect and aspect != "auto":
        lines.append("Aspect ratio: %s (already set; do not write it in the prompt)" % aspect)
    if assets:
        lines.append("Assets:")
        for a in assets:
            bits = [ROLE_TEXT.get(a.get("role"), a.get("role") or a.get("kind") or "asset")]
            if a.get("name") and a.get("kind") != "image":
                bits.append('"%s"' % a["name"])
            if a.get("duration"):
                bits.append("%.1f s" % float(a["duration"]))
            if a.get("label"):
                bits.append("the model sees it as %s" % a["label"])
            if a.get("attached"):
                bits.append(a["attached"])
            lines.append("- %s: %s" % (a["token"], ", ".join(bits)))
        if kind == "image" and task == "edit":
            lines.append("The first image is the one being edited.")
    if mode in ("enhance_en", "structure_en"):
        lines.append("Output language: English, whatever language the user prompt is in. Text to be shown in the "
                     "image and spoken lines keep their original language.")
    elif mode in ("enhance", "structure"):
        language = source_language(prompt, kind)
        if language == "Chinese":
            if kind == "image":
                lines.append("Output language: 中文。用中文扩写下方原文，沿用原文的简体或繁体字形。画面文字按指定原样保留。")
            else:
                lines.append("Output language: 中文。用中文写所有描述正文，沿用原文的简繁字形。字段名、结构标记、画面文字和对白原样保留。")
        else:
            target = language or 'the same language as the descriptive text under "User prompt"'
            literals = VIDEO_LITERALS if kind == "video" else "Keep any text to be shown in the image in its specified language."
            lines.append(f"Output language: {target}. {literals}")
    return "\n".join(lines) + USER_PROMPT_DIVIDER + prompt


def sampling(mode, kind, task, model, effort="auto", info=None):
    """Request fields for mode. Video structuring and image edit think,
    with Qwen3.5's thinking preset (temperature 1.0, top_p 0.95); edit
    drops the presence penalty so the rewrite stays with what the user
    named. Without thinking a 9B model wrote the edit guide's thinking
    steps into its answer. Image generation skips thinking (the
    non-thinking preset, 0.7 and 0.8): it kept its quality and took about
    3 s instead of a minute. effort: the level picked in Settings, sent to
    the thinking modes; "auto" leaves the model's default. Router turns
    reasoning_effort "none" into each engine's thinking switch. info: the
    model's Router row; a model Router says cannot reason gets no effort.
    Qwen-only fields go to Qwen3.5 and 3.6 models alone, since other
    vendors reject unknown fields."""
    edit = kind == "image" and task == "edit"
    think = mode != "translate_en" and (kind != "image" or edit)
    if think:
        body = {"temperature": 1.0, "top_p": 0.95, "presence_penalty": 0.0 if edit else 1.5, "max_tokens": 8192}
    elif mode != "translate_en":
        body = {"temperature": 0.7, "top_p": 0.8, "presence_penalty": 1.5, "max_tokens": 4096}
    else:
        body = {"temperature": 0.7, "top_p": 0.8, "presence_penalty": 0.0, "max_tokens": 2048}
    m = (model or "").lower()
    if any(k in m for k in ("qwen3.5", "qwen3_5", "qwen3.6", "qwen3_6")):
        body.update(top_k=20, min_p=0.0)
    if not info or info.get("reasoning"):
        if not think:
            body["reasoning_effort"] = "none"
        elif effort and effort != "auto":
            body["reasoning_effort"] = effort
    return body


class LlmError(Exception):
    def __init__(self, code, message, status=502):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def clean(text):
    text = THINK.sub("", text or "").strip()
    m = FENCE.match(text)
    return (m.group(1) if m else text).strip()


def rewrite_reply_text(reply, kind):
    """Extract the prompt from a reply with a Studio job or final-prompt heading."""
    job_header = IMAGE_JOB_HEADER if kind == "image" else VIDEO_JOB_HEADER
    if job_header.match(reply):
        heading = USER_PROMPT_LINE.search(reply)
        reply = clean(reply[heading.end():]) if heading else ""
        if not reply or job_header.match(reply):
            raise LlmError("rewrite_format", "The AI reply included job details without a usable prompt", 422)
    if kind == "image":
        headings = list(IMAGE_PROMPT_HEADING.finditer(reply))
        if headings:
            reply = reply[headings[-1].end():]
        reply = clean(IMAGE_PROMPT_POSTSCRIPT.sub("", reply))
        if not reply:
            raise LlmError("rewrite_format", "The AI reply did not include a usable prompt", 422)
    return reply


def descriptive_text(prompt, kind, *, exclude_quotes=True):
    prose = REF.sub(" ", prompt)
    if kind == "video":
        prose = VIDEO_SYNTAX.sub(" ", VIDEO_DIALOGUE.sub(" ", prose))
    return QUOTED.sub(" ", prose) if exclude_quotes else prose


def image_template_echo(source, result):
    return (IMAGE_TEMPLATE_NOTE.search(descriptive_text(result, "image")) is not None
            and IMAGE_TEMPLATE_NOTE.search(descriptive_text(source, "image")) is None)


def keeps_image_subject(source, result, mode, task):
    """Require a short subject prompt to stay verbatim in same-language edits."""
    subject = REF.sub("", source).strip().rstrip("。.!！")
    if mode == "enhance" and task == "edit" and SHORT_HAN_PROMPT.fullmatch(subject):
        return subject in descriptive_text(result, "image")
    return True


def is_cjk_description(prompt, kind="image"):
    letters = [c for c in descriptive_text(prompt, kind) if c.isalpha()]
    return 2 * sum(bool(CJK.fullmatch(c)) for c in letters) > len(letters)


def source_language(prompt, kind):
    """Infer a CJK language from the scripts in the descriptive text."""
    if not prompt or not is_cjk_description(prompt, kind):
        return None
    scripts = {unicodedata.name(c, "").partition(" ")[0] for c in descriptive_text(prompt, kind) if c.isalpha()}
    kana = bool(scripts & {"HIRAGANA", "KATAKANA"})
    hangul = "HANGUL" in scripts
    if kana and hangul:
        return None
    if kana:
        return "Japanese"
    return "Korean" if hangul else "Chinese"


def same_language_header(prompt, kind):
    language = source_language(prompt, kind)
    if language == "Chinese":
        if kind == "video":
            return ("【输出语言】分镜、场景和声音等描述正文都用中文。简体原文用简体中文，繁体原文用繁体中文。"
                    "下方英文示例用于说明结构，按要求保留字段名、分镜和说话人标记、参考帧对齐行与素材占位符。"
                    "逐字保留指定的画面文字和对白。保留原文中的主体、动作和限制，只输出改写后的提示词。\n\n")
        return ("【输出语言】这次润色的整段画面描述使用中文：简体原文用简体中文，繁体原文用繁体中文。"
                "用中文表达下面的示例句式，从第一句起直接描写画面。"
                "保留原文指定的主体、动作、位置和其他限制，逐字保留画面中指定出现的文字。"
                "只输出润色后的中文正文。\n\n")
    language = language or "the language of the original description under User prompt"
    literals = VIDEO_LITERALS if kind == "video" else "Preserve the language of any text to be shown in the image."
    return (f"Output language: Write the entire descriptive prompt in {language}. "
            f"Use the examples for structure. {literals}\n\n")


def rewrite_language_mismatch(kind, mode, prompt, result):
    """Check prose while allowing literals, asset tokens and video structure."""
    english = mode.endswith("_en")
    if not english and not is_cjk_description(prompt, kind):
        return False
    prose = descriptive_text(result, kind)
    # Also check replies that incorrectly wrap the entire rewrite in quotes.
    if not any(c.isalpha() for c in prose) and any(c.isalpha() for c in descriptive_text(prompt, kind)):
        prose = descriptive_text(result, kind, exclude_quotes=False)
    cjk = sum(c.isalpha() and bool(CJK.fullmatch(c)) for c in prose)
    if english:
        return cjk > 0
    # Count Latin words and CJK letters so terms like brand names do not
    # outweigh a shorter Chinese sentence just because of word length.
    latin = sum(all("LATIN " in unicodedata.name(c, "") for c in word) for word in WORD.findall(prose))
    return latin > cjk or (bool(LATIN_SENTENCE.search(prose)) and
                           not LATIN_SENTENCE.search(descriptive_text(prompt, kind)))


def language_correction_prompt(kind, mode, original):
    """Translate a completed rewrite without expanding it again."""
    language = "English" if mode.endswith("_en") else source_language(original, kind)
    if not language:
        return None
    if language == "Chinese":
        return ("把用户消息里的整段描述统一翻译成中文。逐句翻译，保留每一处细节和段落顺序。"
                "保留字段名、分镜标记和 {{...}} 素材占位符。"
                "引号里的画面文字和 <d> 标签里的对白逐字保留。只输出改好的提示词正文。")
    literals = VIDEO_LITERALS if kind == "video" else "Keep any quoted text to be shown in the image verbatim."
    return (f"Translate the entire description in the user's message into {language}. "
            f"Keep the existing details, paragraph breaks and sequence. {literals}\n{REFS}\n{ONLY}")


def chat_models(data):
    """The chat models of a /models reply: id, vision, context, and whether
    it reasons with the effort levels it takes besides "none"."""
    out = []
    for m in (data or {}).get("data") or []:
        if not isinstance(m, dict) or not m.get("id"):
            continue
        if m.get("mode") not in (None, "", "chat"):
            continue
        sup = m.get("supports") or []
        if isinstance(sup, dict):
            sup = [k for k, v in sup.items() if v]
        sup = {str(s).replace("supports_", "") for s in sup}
        levels = [str(v) for v in (m.get("reasoning_levels") or []) if v and v != "none"]
        out.append({"id": m["id"], "vision": "vision" in sup or bool(m.get("supports_vision")),
                    "context": m.get("context_size") or 0, "reasoning": bool(m.get("reasoning")),
                    "levels": levels, "default_level": m.get("default_reasoning_level") or ""})
    return out


class Llm:
    """state: a json file keeping the model and thinking effort picked in
    Settings."""

    def __init__(self, base, model, key="", ttl=60, state=""):
        self.base = (base or "").rstrip("/")
        self.default = model or DEFAULT_MODEL
        self.key = key or ""
        self.ttl = ttl
        self.state = state
        self.selected = self.default
        self.chosen = "auto"
        if state and os.path.exists(state):
            try:
                with open(state) as f:
                    saved = json.load(f)
                self.selected = saved.get("model") or self.default
                self.chosen = saved.get("effort") or "auto"
            except (OSError, ValueError, AttributeError):
                pass
        self.ready = False
        self.listed = False
        self.models = []
        self.checked = 0.0
        self.probing = None

    @property
    def model(self):
        """The model requests go to: the selection while Router lists it,
        else default-chat. Before the first list the selection stands."""
        if self.selected == DEFAULT_MODEL or not self.listed or any(m["id"] == self.selected for m in self.models):
            return self.selected
        return DEFAULT_MODEL

    def info(self, model=None):
        model = model or self.model
        return next((m for m in self.models if m["id"] == model), None)

    @property
    def effort(self):
        """The chosen effort while the model in use takes it, else auto."""
        info = self.info()
        return self.chosen if info and self.chosen in info["levels"] else "auto"

    def select(self, model, effort=None):
        """effort None keeps the current choice."""
        self.selected = model or DEFAULT_MODEL
        if effort is not None:
            self.chosen = effort or "auto"
        if self.state:
            os.makedirs(os.path.dirname(self.state), exist_ok=True)
            tmp = self.state + ".tmp"
            with open(tmp, "w") as f:
                json.dump({"model": self.selected, "effort": self.chosen}, f)
            os.replace(tmp, self.state)

    def headers(self):
        return {"Authorization": "Bearer " + self.key} if self.key else {}

    def status(self):
        """The cached readiness; starts a background probe when stale. A
        failed probe is retried sooner, so Router installed later shows up."""
        ttl = self.ttl if self.ready else min(self.ttl, 15)
        if self.base and time.time() - self.checked > ttl and self.probing is None:
            self.probing = asyncio.ensure_future(self.probe())
        model = self.model
        info = self.info(model)
        return {"ready": self.ready, "model": model, "selected": self.selected,
                "fallback": model != self.selected, "vision": info["vision"] if info else None,
                "effort": self.effort, "levels": info["levels"] if info else [],
                "default_level": info["default_level"] if info else ""}

    async def probe(self):
        models = None
        try:
            async with ClientSession(timeout=ClientTimeout(total=5)) as s:
                async with s.get(self.base + "/models", headers=self.headers()) as r:
                    data = await r.json(content_type=None) if r.status == 200 else None
            if isinstance(data, dict):
                models = chat_models(data)
        except Exception as e:
            log.info("studio: llm probe %s: %s", self.base, e)
        ready = bool(models)
        if ready != self.ready:
            log.info("studio: llm %s at %s", "ready" if ready else "unavailable", self.base)
        if models is not None:
            self.models, self.listed = models, True
        self.ready, self.checked, self.probing = ready, time.time(), None
        return ready

    async def rewrite(self, prompt, system, user=None, images=(), fields=None, timeout=180, labels=None, *,
                      kind="", fallback_system=None):
        """user: the message text (default: prompt); images: (token,
        data URL) pairs attached after it. A model that turns the images
        down gets the text alone, with fallback_system when provided. labels: what the image model sees for
        each token ({"<Picture 1>": "{{id}}"}); an app prompt written
        around those labels makes the chat model write them, so they are
        turned back into tokens."""
        if not self.base or not self.ready:
            raise LlmError("llm_unavailable", "No chat model is available", 503)
        model = self.model
        info = self.info(model)
        if info and not info["vision"]:
            images = ()
        try:
            out = await self._chat(model, system, user or prompt, images, fields, timeout)
        except LlmError as e:
            if not images or e.code != "llm_rejected":
                raise
            log.info("studio: llm %s refused images (%s), retrying with text", model, e.message)
            out = await self._chat(model, fallback_system or system, prompt if fallback_system else user or prompt,
                                   (), fields, timeout)
        if kind in ("image", "video"):
            out = rewrite_reply_text(out, kind)
        for label in sorted(labels or {}, key=len, reverse=True):
            out = out.replace(label, labels[label])
        lost = set(REF.findall(prompt)) - set(REF.findall(out))
        if lost:
            raise LlmError("refs_lost", "The rewrite dropped asset references", 422)
        known = set(REF.findall(prompt)) | set(REF.findall(user or ""))
        made_up = set(REF.findall(out)) - known
        if made_up:
            log.info("studio: llm %s made up %s, removed", model, sorted(made_up))
            out = REF.sub(lambda m: m.group(0) if m.group(0) in known else "", out)
            out = re.sub(r"[ \t]{2,}", " ", re.sub(r"[ \t]+([,.;:!?])", r"\1", out)).strip()
        return out

    async def _chat(self, model, system, user, images, fields, timeout):
        content = user
        if images:
            content = [{"type": "text", "text": user}]
            for tok, url in images:
                content += [{"type": "text", "text": tok + ":"}, {"type": "image_url", "image_url": {"url": url}}]
        body = {"model": model, "stream": False, **(fields or {"temperature": 0.3}),
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}]}
        try:
            async with ClientSession(timeout=ClientTimeout(total=timeout)) as s:
                async with s.post(self.base + "/chat/completions", json=body, headers=self.headers()) as r:
                    data = await r.json(content_type=None)
                    if r.status != 200:
                        err = data.get("error") if isinstance(data, dict) else None
                        msg = (err.get("message") if isinstance(err, dict) else err) or "HTTP %d" % r.status
                        raise LlmError("llm_rejected" if 400 <= r.status < 500 else "llm_failed", str(msg)[:500])
        except asyncio.TimeoutError:
            raise LlmError("llm_timeout", "The chat model did not answer in time", 504)
        except LlmError:
            raise
        except Exception as e:
            raise LlmError("llm_failed", str(e)[:500])
        try:
            msg = data["choices"][0]["message"]
            out = clean(msg["content"])
        except (KeyError, IndexError, TypeError):
            raise LlmError("llm_failed", "The chat model returned no text")
        if not out:
            raise LlmError("llm_failed", "The chat model returned no text")
        reasoning = msg.get("reasoning_content") or ""
        log.info("studio: llm %s answered: %d chars, %d reasoning chars, finish=%s, usage=%s", model, len(out),
                 len(reasoning), data["choices"][0].get("finish_reason"), data.get("usage"))
        return out
