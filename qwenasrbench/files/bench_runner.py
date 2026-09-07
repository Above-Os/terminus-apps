#!/usr/bin/env python3
"""A benchmark that runs on the machine it is measuring.

Why it lives here rather than in a script somebody runs from a laptop: reaching an Olares
app from outside needs the LarePass network, and `pod exec` does not exist on every Olares
version -- one of the two machines this was built against has neither. Anything that needs
a person's terminal to stay connected therefore cannot be relied on. This runs inside the
cluster, talks to the engine over its in-cluster Service, and keeps its results on a volume
that survives a restart, so the only thing that has to cross the network is starting a run
and reading a few hundred bytes back.

What it measures, and what that is worth:

  A speed figure alone is not a result. Every run here reports how long the engine spent
  and what the error rate was, because the switches being measured trade one against the
  other and either number on its own can be made to look good.

  The corpus it ships with is LibriSpeech test-clean, because its publisher reports a
  figure on it: Qwen3-ASR-1.7B is given as 1.63% WER. Landing on that number is what says
  a deployment is correct; a number measured only against itself cannot say that.

  🔴 Speed figures belong to the card they were measured on and to nothing else. Error
  rates belong to the corpus. Neither transfers, which is the entire reason this runs
  where it does instead of shipping somebody else's numbers.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tarfile
import threading
import time
import unicodedata
import urllib.request
import uuid
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = int(os.environ.get("BENCH_PORT", "8080"))
ENGINE = os.environ.get("BENCH_ENGINE_URL", "http://localhost:8000").rstrip("/")
MODEL = os.environ.get("BENCH_MODEL", "")
STORE = Path(os.environ.get("BENCH_STORE", "/bench"))
SHARED_CORPORA = Path(os.environ.get("BENCH_SHARED_CORPORA", "/corpora"))
# One request carries this much audio. It is also how much a single generate call gets, so
# it is a property of the measurement rather than a tuning knob: the caller this engine
# serves batches by duration, and holding it fixed is what keeps a window sweep honest.
BATCH_SECONDS = float(os.environ.get("BENCH_BATCH_SECONDS", "600"))
CONSOLE = os.environ.get("BENCH_CONSOLE_URL", "http://127.0.0.1:8090").rstrip("/")
#: host=replacement pairs tried when a download fails. Some networks cannot reach
#: huggingface.co at all -- the bench machine returns nothing at the TLS layer -- and a
#: mirror is the difference between a corpus this tool can fetch and one it cannot.
#: 🔴 Which host actually served a corpus is recorded with the run: a mirror is not
#: guaranteed to be byte-identical, and a rate measured on different bytes is a different
#: rate no matter what the file is called.
URL_FALLBACKS = [p.split("=", 1) for p in
                 os.environ.get("BENCH_URL_FALLBACKS", "huggingface.co=hf-mirror.com").split(",")
                 if "=" in p]

#: The switches that change what the engine does. Passed in by the same chart render that
#: configures the engine, so they say what was deployed -- 🔴 but they are NOT read back
#: out of the engine process, and the report labels them that way. The one thing that can
#: make them lie is the Model Console's Raw tab, which edits the model card and restarts
#: the engine without the chart knowing.
SWITCH_ENVS = ("ASR_BATCH_ONE_SHOT", "ASR_TOKENS_PER_AUDIO_SEC", "BENCH_REPETITION_DETECTION",
               "ASR_REPETITION_DETECTION", "BENCH_LLM_KWARGS", "ENGINE_ARGS")

RUNS = STORE / "runs"
CORPORA = STORE / "corpora"
#: One slot, so the install is attempted once per process rather than once per run.
_normaliser_install_tried: list = []

#: Corpora whose publisher reports a figure for this model, so a run can be held against
#: something other than itself. `wer` is what they report; None where nobody does.
CATALOG = {
    "librispeech-test-clean": {
        "title": "LibriSpeech test-clean",
        "layout": "librispeech",
        "files": {"archive": "https://www.openslr.org/resources/12/test-clean.tar.gz"},
        "language": "en",
        "unit": "word",
        "published": {
            "rate": 1.63,
            "metric": "WER",
            "model": "Qwen3-ASR-1.7B",
            "source": "https://arxiv.org/html/2601.21337v1",
            "note": "Table 3. The report does not name its text normaliser, so a match is "
                    "evidence the deployment costs nothing, not proof of one protocol.",
        },
    },
    "fleurs-zh-test": {
        "title": "FLEURS Chinese (cmn_hans_cn) test",
        "layout": "fleurs",
        "files": {
            "archive": "https://huggingface.co/datasets/google/fleurs/resolve/main"
                       "/data/cmn_hans_cn/audio/test.tar.gz",
            "transcripts": "https://huggingface.co/datasets/google/fleurs/resolve/main"
                           "/data/cmn_hans_cn/test.tsv",
        },
        "language": "zh",
        "unit": "char",
        "published": {
            "rate": 2.41,
            "metric": "CER",
            "model": "Qwen3-ASR-1.7B",
            "source": "https://arxiv.org/html/2601.21337v1",
            "note": "Table 3, Fleurs-zh. Scored per character; 🔴 this rate and an English "
                    "one are different units and must not be read against each other.",
        },
    },
    "aishell4-on-disk": {
        "title": "AISHELL-4 (already on this machine)",
        "layout": "textgrid",
        "audio_dir": "aishell4/wav",
        "reference_dir": "_archives/test/TextGrid",
        "language": "zh",
        "unit": "char",
        # 🔴 Nobody publishes a figure for this model on this corpus, so `published` is
        # absent and the report will not claim comparability. What it is for is comparing
        # configurations on the material the product actually meets: Mandarin meetings,
        # several people over one mixed channel.
        #
        # ⚠️ The spans here are the reference's own intervals, which is a third thing again
        # from diarized turns and from fixed windows, and kinder than both -- every span
        # starts and ends where somebody actually spoke. A rate from this corpus may be
        # read against another run of this corpus and against nothing else.
        "note": "spans are the reference's own intervals; comparable across runs here only",
    },
}


def log(msg: str) -> None:
    print("[bench] %s" % msg, flush=True)


# ---------------------------------------------------------------- scoring


TAG = re.compile(r"<[^>]*>")


def words(text: str) -> list[str]:
    """Lower-cased alphanumeric words.

    Punctuation goes because the engine invents it -- it hears none -- and counting it
    reports a formatting choice as a transcription error.
    """
    text = TAG.sub(" ", text)
    kept = "".join(c.lower() if unicodedata.category(c)[0] in "LN" else " " for c in text)
    return kept.split()


def chars(text: str) -> list[str]:
    text = TAG.sub("", text)
    return [c.lower() for c in text if unicodedata.category(c)[0] in "LN"]


def edit_counts(ref: list[str], hyp: list[str]) -> dict[str, int]:
    """Levenshtein with the operations kept apart, so a rate can be explained.

    Substitutions, deletions and insertions answer different questions: a model that drops
    the end of every window fails differently from one that mishears, and a single distance
    hides which happened. On this corpus the split is what shows that a long window costs
    deletions rather than accuracy.
    """
    previous = [(j, 0, 0, j) for j in range(len(hyp) + 1)]
    for i, r in enumerate(ref, 1):
        current = [(i, 0, i, 0)]
        for j, h in enumerate(hyp, 1):
            if r == h:
                current.append(previous[j - 1])
                continue
            sub, dele, ins = previous[j - 1], previous[j], current[j - 1]
            best = min(sub, dele, ins, key=lambda c: c[0])
            if best is sub:
                current.append((best[0] + 1, best[1] + 1, best[2], best[3]))
            elif best is dele:
                current.append((best[0] + 1, best[1], best[2] + 1, best[3]))
            else:
                current.append((best[0] + 1, best[1], best[2], best[3] + 1))
        previous = current
    cost, sub, dele, ins = previous[-1]
    return {"errors": cost, "substitutions": sub, "deletions": dele, "insertions": ins}


def _load_normaliser(unit: str):
    """English gets its own normaliser; everything else gets the basic one.

    🔴 They are not interchangeable. The English one spells numbers out and expands
    contractions, which is meaningless for a character-scored language; the basic one only
    strips punctuation and case, which is what a CER wants.
    """
    if unit == "word":
        from whisper_normalizer.english import EnglishTextNormalizer
        return EnglishTextNormalizer()
    from whisper_normalizer.basic import BasicTextNormalizer
    return BasicTextNormalizer()


def whisper_normaliser(unit: str = "word"):
    """The normaliser the field scores this corpus with, or None.

    🔴 Without it the rate is not comparable to a published figure and the report says so.
    The corpus writes references as spelled-out words in capitals; a current model writes
    numbers as digits. That difference is a convention, not an error, and it is worth
    about a quarter of a point here -- enough to turn "we landed on it" into "we did not".
    """
    try:
        return _load_normaliser(unit)
    except ImportError:
        pass
    if _normaliser_install_tried:
        return None
    # Fetched once, at the moment it is first needed, rather than baked into the image:
    # the image belongs to the engine and this is the only thing here that wants a
    # dependency. A machine with no route out still runs -- the report then says the rate
    # is not comparable instead of quietly reporting one that is not.
    _normaliser_install_tried.append(True)
    log("fetching whisper-normalizer (needed for a rate comparable to a published one)")
    try:
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "whisper-normalizer"],
                       check=True, timeout=300)
        import importlib
        importlib.invalidate_caches()
        return _load_normaliser(unit)
    except Exception as e:  # noqa: BLE001 - offline is a normal outcome, not a failure
        log("could not fetch whisper-normalizer (%s); rates will be marked not comparable" % e)
        return None


# ---------------------------------------------------------------- corpora


def fetch_corpus(name: str, progress) -> Path:
    """Download and lay out one corpus. Returns its directory.

    Resumable in the only sense that matters here: a file already on disk is not fetched
    again, and a corpus already laid out is not laid out again. A run interrupted by a
    restart therefore costs the download in flight, not all of it.
    """
    spec = CATALOG[name]
    root = CORPORA / name
    if (root / "manifest.tsv").exists():
        return root
    root.mkdir(parents=True, exist_ok=True)
    served = {}
    for label, url in (spec.get("files") or {}).items():
        dest = root / ("%s%s" % (label, ".tar.gz" if label == "archive" else ".tsv"))
        if dest.exists() and dest.stat().st_size:
            continue
        served[label] = download(url, dest, progress)
    if served:
        (root / "source.json").write_text(json.dumps(served, indent=1), encoding="utf-8")
    if spec.get("files"):
        progress("extracting")
        with tarfile.open(root / "archive.tar.gz") as t:
            t.extractall(root)
    LAYOUTS[spec["layout"]](root, progress)
    return root


def download(url: str, dest: Path, progress) -> str:
    """Fetch one file, falling back to a mirror. Returns the URL that actually served it."""
    attempts = [url]
    for host, replacement in URL_FALLBACKS:
        if host in url:
            attempts.append(url.replace(host, replacement))
    last = None
    for attempt in attempts:
        progress("downloading %s from %s" % (dest.name, attempt.split("/")[2]))
        tmp = dest.with_suffix(dest.suffix + ".part")
        try:
            with urllib.request.urlopen(attempt, timeout=180) as r, open(tmp, "wb") as f:
                shutil.copyfileobj(r, f, 1024 * 1024)
            tmp.rename(dest)
            return attempt
        except Exception as e:  # noqa: BLE001 - the next host is the point
            last = e
            log("%s failed from %s: %s" % (dest.name, attempt.split("/")[2], e))
            tmp.unlink(missing_ok=True)
    raise RuntimeError("could not fetch %s: %s" % (dest.name, last))


def concatenate(root: Path, items, progress) -> None:
    """Write the chunks and the manifest from (id, audio path) pairs, in order.

    The endpoint takes one file plus a list of spans and decodes those spans as one batch;
    that is the path worth measuring, and one request per utterance would measure fixed
    overhead instead. The spans are the corpus's own utterance boundaries, which is what
    makes the resulting rate comparable to a figure published on it.
    """
    import soundfile as sf
    import numpy as np

    chunks = root / "chunks"
    chunks.mkdir(exist_ok=True)
    budget = int(BATCH_SECONDS * 16000)
    manifest = []
    idx, held, samples = 0, [], 0
    for n, (uid, path) in enumerate(items):
        audio, rate = sf.read(str(path), dtype="int16")
        if rate != 16000:
            raise RuntimeError("%s is %d Hz, expected 16000" % (path.name, rate))
        if audio.ndim > 1:
            audio = audio[:, 0]
        start = samples
        held.append(audio)
        samples += len(audio)
        manifest.append((uid, idx, start / 16000.0, samples / 16000.0))
        if samples >= budget:
            write_wav(chunks / ("chunk_%d.wav" % idx), np.concatenate(held))
            idx, held, samples = idx + 1, [], 0
        if n % 200 == 0:
            progress("preparing audio %d/%d" % (n, len(items)))
    if held:
        write_wav(chunks / ("chunk_%d.wav" % idx), np.concatenate(held))
    with open(root / "manifest.tsv", "w", encoding="utf-8") as out:
        for row in manifest:
            out.write("%s\t%d\t%.3f\t%.3f\n" % row)
    progress("corpus ready: %d utterances, %d chunks" % (len(manifest), idx + 1))


def layout_librispeech(root: Path, progress) -> None:
    src = next(p for p in root.rglob("*") if p.is_dir() and p.name == "test-clean")
    with open(root / "reference.txt", "w", encoding="utf-8") as out:
        for t in sorted(src.rglob("*.trans.txt")):
            out.write(t.read_text(encoding="utf-8"))
    concatenate(root, [(f.stem, f) for f in sorted(src.rglob("*.flac"))], progress)


def layout_fleurs(root: Path, progress) -> None:
    """FLEURS ships audio and transcripts separately, and the transcript file has two.

    Column 3 is the sentence as written, with punctuation and Latin script left in place;
    column 4 is the corpus's own normalised form. The published figure is scored against
    the normalised one, so that is what is used here -- reading column 3 instead would
    charge the model for punctuation the corpus itself does not count.
    """
    rows = {}
    for line in (root / "transcripts.tsv").read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) > 3:
            rows[parts[1]] = parts[3]
    wavs = {p.name: p for p in root.rglob("*.wav")}
    missing = [n for n in rows if n not in wavs]
    if missing:
        progress("%d transcript rows have no audio; skipping them" % len(missing))
    names = [n for n in rows if n in wavs]
    names.sort()
    with open(root / "reference.txt", "w", encoding="utf-8") as out:
        for n in names:
            out.write("%s %s\n" % (n, rows[n]))
    concatenate(root, [(n, wavs[n]) for n in names], progress)


TEXTGRID_INTERVAL = re.compile(
    r'intervals \[\d+\]:\s*xmin = ([\d.]+)\s*xmax = ([\d.]+)\s*text = "(.*?)"\s*(?=intervals|item|\Z)',
    re.S)
TEXTGRID_TIER = re.compile(r'item \[\d+\]:.*?name = "([^"]*)"(.*?)(?=\n    item \[|\Z)', re.S)


def layout_textgrid(root: Path, progress) -> None:
    """A corpus already on the shared disk, with one TextGrid per recording.

    Nothing is downloaded and nothing is concatenated: the recordings are already long,
    and each one becomes its own chunk with the reference's intervals as its spans.
    """
    spec = CATALOG[root.name]
    audio = SHARED_CORPORA / spec["audio_dir"]
    refs = SHARED_CORPORA / spec["reference_dir"]
    if not audio.is_dir():
        raise RuntimeError("%s is not on this machine" % audio)
    chunks = root / "chunks"
    chunks.mkdir(exist_ok=True)
    manifest, reference = [], []
    for idx, wav in enumerate(sorted(audio.glob("*.wav"))):
        grid = refs / (wav.stem + ".TextGrid")
        if not grid.exists():
            continue
        spans = []
        raw = grid.read_text(encoding="utf-8")
        for _speaker, body in TEXTGRID_TIER.findall(raw):
            for a, b, text in TEXTGRID_INTERVAL.findall(body):
                if text.strip():
                    spans.append((float(a), float(b), text.strip()))
        spans.sort()
        # A symlink rather than a copy: these recordings are hundreds of megabytes each
        # and the shared disk already holds them.
        link = chunks / ("chunk_%d.wav" % idx)
        if not link.exists():
            link.symlink_to(wav)
        for n, (a, b, text) in enumerate(spans):
            uid = "%s_%04d" % (wav.stem, n)
            manifest.append((uid, idx, a, b))
            reference.append("%s %s" % (uid, text))
        progress("indexed %s: %d spans" % (wav.stem, len(spans)))
    if not manifest:
        raise RuntimeError("no recording under %s had a TextGrid in %s" % (audio, refs))
    (root / "reference.txt").write_text("\n".join(reference) + "\n", encoding="utf-8")
    with open(root / "manifest.tsv", "w", encoding="utf-8") as out:
        for row in manifest:
            out.write("%s\t%d\t%.3f\t%.3f\n" % row)
    progress("corpus ready: %d spans across %d recordings" % (len(manifest), idx + 1))


LAYOUTS = {"librispeech": layout_librispeech, "fleurs": layout_fleurs,
           "textgrid": layout_textgrid}


def write_wav(path: Path, samples) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(samples.tobytes())


# ---------------------------------------------------------------- engine


def post_transcription(wav: Path, spans: list[dict], language: str) -> dict:
    """One batch request, built by hand so this needs nothing outside the standard library."""
    boundary = "----bench%s" % uuid.uuid4().hex
    parts = []

    def field(name, value):
        parts.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                      % (boundary, name, value)).encode())

    field("model", MODEL)
    field("language", language)
    field("segments", json.dumps(spans))
    parts.append(("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\n"
                  "Content-Type: audio/wav\r\n\r\n" % (boundary, wav.name)).encode())
    parts.append(wav.read_bytes())
    parts.append(("\r\n--%s--\r\n" % boundary).encode())
    body = b"".join(parts)

    req = urllib.request.Request(
        ENGINE + "/v1/audio/transcriptions", data=body,
        headers={"Content-Type": "multipart/form-data; boundary=%s" % boundary})
    with urllib.request.urlopen(req, timeout=3600) as r:
        return json.loads(r.read())


def engine_ready() -> tuple[bool, str]:
    """A real transcription, not /v1/models.

    🔴 The model endpoint answers while the model is still loading, so it cannot be used to
    decide readiness. A run started against a half-loaded engine fails in a way that looks
    like a bad configuration.
    """
    import numpy as np
    probe = STORE / "probe.wav"
    if not probe.exists():
        t = np.arange(16000)
        write_wav(probe, (8000 * np.sin(2 * np.pi * 220 * t / 16000.0)).astype("int16"))
    try:
        post_transcription(probe, [{"start": 0.0, "end": 1.0}], "en")
        return True, "ok"
    except Exception as e:  # noqa: BLE001 - the message is the whole point
        return False, str(e)


def engine_facts() -> dict:
    """What produced a number, recorded beside it.

    🔴 A rate without the configuration that produced it can only be compared to itself.
    Two runs of this tool with different switches are otherwise indistinguishable in the
    table, which is the failure this exists to prevent.

    Two kinds of fact, kept apart on purpose. `declared` is what the chart deployed;
    `observed` is what the engine and the console say right now. They can disagree -- the
    Model Console can restart the engine with different arguments and the chart never
    hears about it -- and a reader has to be able to see which is which.
    """
    facts = {
        "declared": {k: os.environ.get(k, "") for k in SWITCH_ENVS},
        "declared_note": "from the chart that deployed the engine, not read back out of it",
        "batch_seconds": BATCH_SECONDS,
        "engine_url": ENGINE,
        "observed": {},
    }
    try:
        with urllib.request.urlopen(ENGINE + "/v1/models", timeout=10) as r:
            models = json.loads(r.read()).get("models") or []
        if models:
            facts["observed"]["model"] = models[0].get("name")
    except Exception as e:  # noqa: BLE001
        facts["observed"]["model_error"] = str(e)
    try:
        with urllib.request.urlopen(CONSOLE + "/api/diag/gpu", timeout=10) as r:
            gpu = json.loads(r.read())
        facts["observed"]["gpu"] = {k: gpu.get(k) for k in ("mode", "memory_bytes", "memory_human",
                                                            "utilization", "source") if k in gpu}
        if not facts["observed"]["gpu"]:
            facts["observed"]["gpu"] = gpu.get("gpu") or gpu.get("residency") or {}
    except Exception as e:  # noqa: BLE001
        facts["observed"]["gpu_error"] = str(e)
    return facts


# ---------------------------------------------------------------- runs


class Run:
    def __init__(self, corpus: str, window: float | None, language: str):
        self.id = "run_%s" % uuid.uuid4().hex[:12]
        self.state = {
            "id": self.id, "corpus": corpus, "window": window, "language": language,
            "status": "queued", "stage": "", "created": time.time(),
            "started": None, "finished": None, "result": None, "error": None,
            # Captured at submission rather than at scoring: a run has to carry the
            # configuration it actually ran under, even if it fails half way.
            "config": engine_facts(),
        }
        self.corpus_source: dict = {}
        self.save()

    def save(self) -> None:
        RUNS.mkdir(parents=True, exist_ok=True)
        (RUNS / (self.id + ".json")).write_text(
            json.dumps(self.state, ensure_ascii=False, indent=1), encoding="utf-8")

    def progress(self, stage: str) -> None:
        self.state["stage"] = stage
        self.save()
        log("%s %s" % (self.id, stage))

    def go(self) -> None:
        self.state["status"] = "running"
        self.state["started"] = time.time()
        self.progress("checking the engine")
        try:
            ok, detail = engine_ready()
            if not ok:
                raise RuntimeError("engine not ready: %s" % detail)
            self.state["result"] = self.measure()
            self.state["status"] = "succeeded"
        except Exception as e:  # noqa: BLE001
            self.state["status"] = "failed"
            self.state["error"] = "%s: %s" % (type(e).__name__, e)
            log("%s failed: %s" % (self.id, self.state["error"]))
        self.state["finished"] = time.time()
        self.save()

    def measure(self) -> dict:
        corpus = self.state["corpus"]
        spec = CATALOG[corpus]
        root = fetch_corpus(corpus, self.progress)
        source = root / "source.json"
        self.corpus_source = json.loads(source.read_text()) if source.exists() else {}

        rows = [l.split("\t") for l in (root / "manifest.tsv").read_text().splitlines()]
        by_chunk: dict[int, list] = {}
        for uid, chunk, start, end in rows:
            by_chunk.setdefault(int(chunk), []).append((uid, float(start), float(end)))
        reference = {}
        for line in (root / "reference.txt").read_text(encoding="utf-8").splitlines():
            if line.strip():
                key, _, text = line.partition(" ")
                reference[key] = text

        window = self.state["window"]
        pairs, engine_seconds, audio_seconds = [], 0.0, 0.0
        for n, chunk in enumerate(sorted(by_chunk)):
            wav = root / "chunks" / ("chunk_%d.wav" % chunk)
            entries = by_chunk[chunk]
            spans = ([{"start": s, "end": e} for _, s, e in entries] if window is None
                     else fixed_windows(entries, window))
            self.progress("transcribing chunk %d/%d" % (n + 1, len(by_chunk)))
            t0 = time.perf_counter()
            payload = post_transcription(wav, spans, self.state["language"])
            engine_seconds += time.perf_counter() - t0
            audio_seconds += sum(s["end"] - s["start"] for s in spans)
            texts = [r.get("text", "") for r in payload["results"]]
            if len(texts) != len(spans):
                raise RuntimeError("chunk %d: %d results against %d spans"
                                   % (chunk, len(texts), len(spans)))
            if window is None:
                for (uid, _, _), text in zip(entries, texts):
                    pairs.append((reference[uid], text))
            else:
                pairs.append((" ".join(reference[uid] for uid, _, _ in entries),
                              " ".join(texts)))

        self.progress("scoring")
        return self.score(pairs, spec, engine_seconds, audio_seconds)

    def score(self, pairs, spec, engine_seconds, audio_seconds) -> dict:
        unit = spec["unit"]
        tokenise = words if unit == "word" else chars
        # 🔴 What one row of `pairs` is depends on how the spans were cut, and the two are
        # not the same quantity. On the corpus's own boundaries a row is one utterance and
        # "word-perfect" counts utterances transcribed exactly. On fixed windows nothing
        # lines up with an utterance, so a row is a whole chunk compared end to end -- and
        # a whole chunk is never word-perfect, which would read as a catastrophic result
        # rather than as a meaningless one.
        blocks = self.state["window"] is not None
        report = {
            "compared_as": "block" if blocks else "utterance",
            "utterances": len(pairs),
            "audio_seconds": round(audio_seconds, 1),
            "engine_seconds": round(engine_seconds, 2),
            "realtime_factor": round(audio_seconds / engine_seconds, 1) if engine_seconds else None,
            "unit": unit,
            "published": spec.get("published"),
            "corpus_note": spec.get("note"),
            "corpus_source": self.corpus_source,
            "rates": {},
        }
        scorers = {"case and punctuation only": lambda t: tokenise(t)}
        normaliser = whisper_normaliser(unit)
        if normaliser is not None:
            scorers["whisper normalisation"] = (
                (lambda t: normaliser(t).split()) if unit == "word"
                else (lambda t: chars(normaliser(t))))
        else:
            report["comparable"] = False
            report["note"] = ("whisper-normalizer is not installed, so only this "
                              "repository's normalisation ran. 🔴 That rate is not "
                              "comparable to a published figure.")
        for label, tok in scorers.items():
            totals = {"errors": 0, "substitutions": 0, "deletions": 0, "insertions": 0}
            n = 0
            exact = 0
            for ref, hyp in pairs:
                r, h = tok(ref), tok(hyp)
                counts = edit_counts(r, h)
                for k in totals:
                    totals[k] += counts[k]
                n += len(r)
                exact += 1 if counts["errors"] == 0 else 0
            report["rates"][label] = {
                "rate_percent": round(totals["errors"] / n * 100, 2) if n else None,
                "substitutions_percent": round(totals["substitutions"] / n * 100, 2) if n else None,
                "deletions_percent": round(totals["deletions"] / n * 100, 2) if n else None,
                "insertions_percent": round(totals["insertions"] / n * 100, 2) if n else None,
                "reference_tokens": n,
                # Meaningless when a row is a whole chunk; left out rather than shown as 0.
                "exact": None if blocks else exact,
            }
        if normaliser is not None and spec.get("published"):
            ours = report["rates"]["whisper normalisation"]["rate_percent"]
            report["comparable"] = True
            report["against_published"] = round(ours - spec["published"]["rate"], 2)
        return report


def fixed_windows(entries, window: float) -> list[dict]:
    """Cut the chunk into equal windows instead of using the corpus's own boundaries.

    ⚠️ A rate measured this way is not comparable to a published one -- nobody publishes a
    figure over arbitrary cuts -- and it is not comparable to a run with window=None either.
    It exists to answer one question only: what does span length cost on this machine.
    """
    duration = max(e for _, _, e in entries)
    spans, a = [], 0.0
    while a < duration:
        b = min(a + window, duration)
        if b - a > 1:
            spans.append({"start": round(a, 3), "end": round(b, 3)})
        a = b
    return spans


# ---------------------------------------------------------------- serving


PAGE = """<!doctype html><meta charset=utf-8><title>ASR Bench</title>
<style>
:root{color-scheme:light dark}
body{font:14px/1.55 system-ui,sans-serif;max-width:1040px;margin:1.5rem auto;padding:0 1rem}
h1{margin:0 0 .2rem}
.sub{color:#777;margin:0 0 1.2rem}
fieldset{border:1px solid #ccc;border-radius:6px;margin:0 0 1rem;padding:.7rem 1rem}
legend{padding:0 .4rem;color:#777;font-size:12px;text-transform:uppercase;letter-spacing:.05em}
label{margin-right:1.2rem;white-space:nowrap}
input[type=number]{width:5rem}
button{padding:.4rem .9rem;font:inherit}
table{border-collapse:collapse;width:100%}
td,th{border-bottom:1px solid #ddd;padding:.4rem .5rem;text-align:left;vertical-align:top}
th{font-weight:600;color:#555;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
td.n{text-align:right;font-variant-numeric:tabular-nums}
code{font-size:12px}
tr.run{cursor:pointer}
tr.run:hover{background:rgba(127,127,127,.09)}
.detail td{background:rgba(127,127,127,.06);font-size:13px}
.muted{color:#777}
.bad{color:#b00}
.hit{color:#070;font-weight:600}
.kv{display:grid;grid-template-columns:auto 1fr;gap:.15rem .8rem;margin:0}
.kv dt{color:#777}
.kv dd{margin:0;font-family:ui-monospace,monospace;font-size:12px;word-break:break-all}
</style>
<h1>ASR Bench</h1>
<p class=sub>Runs on the machine it measures. <b>Speed belongs to this card; the error rate
belongs to the corpus.</b> Neither transfers &mdash; which is why this runs here instead of
shipping somebody else&rsquo;s numbers.</p>

<fieldset><legend>engine</legend><div id=engine class=muted>reading&hellip;</div></fieldset>

<fieldset><legend>new run</legend>
  <label>corpus <select id=corpus></select></label>
  <label><input type=radio name=spans value=own checked> the corpus&rsquo;s own utterance boundaries</label>
  <label><input type=radio name=spans value=fixed> fixed windows of
    <input type=number id=window value=30 min=2 max=600 step=1> s</label>
  <button id=go>Run</button>
  <div class=muted style="margin-top:.5rem" id=hint></div>
</fieldset>

<table><thead><tr>
  <th>run<th>corpus<th>spans<th>status<th class=n>rate<th class=n>published<th class=n>&Delta;<th class=n>speed
</tr></thead><tbody id=rows><tr><td colspan=8 class=muted>loading&hellip;</td></tr></tbody></table>

<script>
const $ = s => document.querySelector(s);
let open = null;

function pct(x){ return typeof x === 'number' ? x.toFixed(2) + '%' : ''; }

function best(r){
  if (!r || !r.rates) return null;
  return r.rates['whisper normalisation'] || r.rates['case and punctuation only'];
}

function spansOf(x){
  return x.window ? ('fixed ' + x.window + 's') : 'corpus';
}

function detail(x){
  const r = x.result, c = x.config || {}, d = c.declared || {}, o = c.observed || {};
  if (!r) return '<span class=muted>no result</span>';
  const blocks = r.compared_as === 'block';
  const rows = Object.entries(r.rates).map(([k, v]) =>
    '<tr><td>' + k + '<td class=n>' + pct(v.rate_percent) +
    '<td class=n>' + pct(v.substitutions_percent) + '<td class=n>' + pct(v.deletions_percent) +
    '<td class=n>' + pct(v.insertions_percent) +
    (blocks ? '' : '<td class=n>' + v.exact + ' / ' + r.utterances) +
    '</tr>').join('');
  return '<table style="margin:.3rem 0 .8rem"><thead><tr><th>normalisation<th class=n>rate' +
    '<th class=n>subs<th class=n>del<th class=n>ins' +
    (blocks ? '' : '<th class=n>word&#8209;perfect') + '</tr></thead>' +
    '<tbody>' + rows + '</tbody></table>' +
    (r.comparable === false ? '<p class=bad>' + (r.note || 'not comparable to a published figure') + '</p>' : '') +
    (r.corpus_note ? '<p class=bad>' + r.corpus_note + '</p>' : '') +
    '<dl class=kv>' +
      '<dt>audio<dd>' + r.audio_seconds + ' s, compared as ' + r.utterances + ' ' +
          r.compared_as + (r.utterances === 1 ? '' : 's') +
          (blocks ? ' &mdash; fixed windows do not line up with utterances, so each chunk is compared end to end' : '') +
      '<dt>engine time<dd>' + r.engine_seconds + ' s' +
      '<dt>switches (declared)<dd>' + Object.entries(d).filter(([,v])=>v)
          .map(([k,v]) => k + '=' + v).join('<br>') +
      '<dt>batch<dd>' + c.batch_seconds + ' s of audio per request' +
      '<dt>observed<dd>' + JSON.stringify(o) +
    '</dl>' +
    '<p class=muted>' + (c.declared_note || '') + '</p>';
}

function render(runs){
  if (!runs.length) { $('#rows').innerHTML = '<tr><td colspan=8 class=muted>no runs yet</td></tr>'; return; }
  $('#rows').innerHTML = runs.map(x => {
    const r = x.result, b = best(r);
    // 🔴 Records on disk outlive the code that wrote them. This page was handed a run
    // whose published figure had been stored under an older key, and reading it as a
    // number threw before a single row rendered -- one stale record blanked the entire
    // table. Anything read out of a stored run is checked for the type it needs.
    const raw = r && r.published ? (r.published.rate ?? r.published.wer) : null;
    const pub = typeof raw === 'number' ? raw : null;
    const delta = r && typeof r.against_published === 'number' ? r.against_published : null;
    const status = x.status === 'running' ? x.stage : x.status;
    const head = '<tr class=run data-id="' + x.id + '">' +
      '<td><code>' + x.id + '</code>' +
      '<td>' + (x.corpus || '').replace(/-test.*/, '') +
      '<td>' + spansOf(x) +
      '<td>' + status + (x.error ? '<br><span class=bad>' + x.error + '</span>' : '') +
      '<td class=n>' + (b ? pct(b.rate_percent) + (r.unit === 'char' ? ' CER' : ' WER') : '') +
      '<td class=n>' + (pub !== null ? pub.toFixed(2) + '%' : '') +
      '<td class="n' + (delta === 0 ? ' hit' : '') + '">' + (delta === null ? '' : (delta > 0 ? '+' : '') + delta.toFixed(2)) +
      '<td class=n>' + (r && r.realtime_factor ? r.realtime_factor + '\u00d7' : '') +
      '</tr>';
    return head + (open === x.id ? '<tr class=detail><td colspan=8>' + detail(x) + '</td></tr>' : '');
  }).join('');
  document.querySelectorAll('tr.run').forEach(tr => tr.onclick = () => {
    open = open === tr.dataset.id ? null : tr.dataset.id; refresh();
  });
}

async function refresh(){
  const r = await (await fetch('api/runs')).json();
  render(r.runs);
}

async function loadEngine(){
  const c = await (await fetch('api/engine')).json();
  const on = Object.entries(c.declared).filter(([,v]) => v);
  $('#engine').innerHTML = '<dl class=kv>' +
    '<dt>model<dd>' + (c.observed.model || '<span class=bad>' + (c.observed.model_error || 'unknown') + '</span>') +
    '<dt>switches<dd>' + (on.length ? on.map(([k,v]) => k + '=' + v).join('<br>') : '<span class=muted>none set</span>') +
    '<dt>batch<dd>' + c.batch_seconds + ' s of audio per request' +
    '<dt>gpu<dd>' + JSON.stringify(c.observed.gpu || c.observed.gpu_error || {}) +
    '</dl><p class=muted>Switches are ' + c.declared_note + '.</p>';
}

async function loadCorpora(){
  const c = await (await fetch('api/corpora')).json();
  $('#corpus').innerHTML = c.corpora.map(x =>
    '<option value="' + x.name + '">' + (x.title || x.name) + (x.ready ? '' : ' (fetches on first run)') + '</option>').join('');
  const first = c.corpora[0];
  if (first && !first.ready) $('#hint').textContent =
    'The first run downloads and prepares the corpus, which takes a few minutes. Later runs reuse it.';
}

$('#go').onclick = async () => {
  const fixed = document.querySelector('input[name=spans]:checked').value === 'fixed';
  await fetch('api/runs', {method:'POST', body: JSON.stringify({
    corpus: $('#corpus').value,
    window: fixed ? Number($('#window').value) : null,
  })});
  refresh();
};

loadEngine(); loadCorpora(); refresh(); setInterval(refresh, 3000);
</script>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # the server's own log is noise next to the run log
        pass

    def send_json(self, code: int, payload) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=1).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler's spelling
        path = self.path.split("?")[0].rstrip("/")
        if path in ("", "/index.html"):
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/healthz":
            self.send_json(200, {"ok": True})
        elif path == "/api/engine":
            self.send_json(200, engine_facts())
        elif path == "/api/corpora":
            self.send_json(200, {"corpora": [
                dict(name=k, ready=(CORPORA / k / "manifest.tsv").exists(), **{
                    x: v[x] for x in ("title", "language", "unit", "published") if x in v})
                for k, v in CATALOG.items()]})
        elif path == "/api/runs":
            self.send_json(200, {"runs": load_runs()})
        elif path.startswith("/api/runs/"):
            f = RUNS / (path.rsplit("/", 1)[-1] + ".json")
            if f.exists():
                self.send_json(200, json.loads(f.read_text()))
            else:
                self.send_json(404, {"error": "no such run"})
        else:
            self.send_json(404, {"error": "no such path"})

    def do_POST(self):  # noqa: N802
        if self.path.split("?")[0].rstrip("/") != "/api/runs":
            return self.send_json(404, {"error": "no such path"})
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self.send_json(400, {"error": "body is not JSON"})
        corpus = body.get("corpus") or "librispeech-test-clean"
        if corpus not in CATALOG:
            return self.send_json(400, {"error": "unknown corpus %r" % corpus})
        window = body.get("window")
        run = Run(corpus, float(window) if window else None,
                  body.get("language") or CATALOG[corpus]["language"])
        threading.Thread(target=run.go, daemon=True).start()
        self.send_json(202, run.state)


def load_runs() -> list[dict]:
    if not RUNS.exists():
        return []
    out = []
    for f in RUNS.glob("*.json"):
        try:
            out.append(json.loads(f.read_text()))
        except ValueError:
            continue
    return sorted(out, key=lambda r: r.get("created", 0), reverse=True)


def main() -> None:
    STORE.mkdir(parents=True, exist_ok=True)
    RUNS.mkdir(parents=True, exist_ok=True)
    CORPORA.mkdir(parents=True, exist_ok=True)
    # A run that was in flight when the container stopped is not resumed: its engine timing
    # would cover a gap it did not spend working. Marked so nobody reads it as a result.
    for state in load_runs():
        if state.get("status") in ("queued", "running"):
            state["status"] = "interrupted"
            state["error"] = "the runner restarted while this run was in flight"
            (RUNS / (state["id"] + ".json")).write_text(
                json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    log("serving on :%d, engine %s, model %r, store %s" % (PORT, ENGINE, MODEL, STORE))
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
