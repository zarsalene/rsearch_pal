"""Text to speech ("Listen" button). It uses Piper: a small voice model that runs on the CPU with onnxruntime.
No AI provider and no API key. The voice file is about 60 MB. It needs about 150 MB of memory, so it fits on a free Render plan.
The model loads on the first call, not at start-up. The server downloads the voice file one time, if it is not on the disk."""
import io, re, threading, wave

import httpx

from . import config

MAX_CHARS = 1500  # a long text on 0.1 CPU takes too much time. The page sends one passage at a time.
_lock = threading.Lock()
_voice = None


class TTSError(Exception):
    """The message is for the user."""


def clean(text: str) -> str:
    """Plain text for the voice: no link, no brackets with a citation number, one space between words."""
    text = re.sub(r"https?://\S+", " ", str(text or ""))
    text = re.sub(r"\[\d+(?:[,\u2013-]\s*\d+)*\]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        raise TTSError("There is no text to read.")
    if len(text) > MAX_CHARS:
        cut = text[:MAX_CHARS]
        text = cut[: cut.rfind(". ") + 1] if ". " in cut else cut  # stop at the end of a sentence
    return text


def passages(page_text: str, limit: int = 900) -> list[str]:
    """Split the text of one PDF page into short passages for the voice. Each passage ends at a sentence end.
    The page can play passage by passage, so the first sound starts fast. Hyphens at a line end are joined."""
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", str(page_text or ""))
    out, cur = [], ""
    for para in re.split(r"\n\s*\n", text):
        try:
            para = clean(para)
        except TTSError:
            continue
        for s in re.split(r"(?<=[.!?])\s+", para):
            if cur and len(cur) + len(s) + 1 > limit:
                out.append(cur)
                cur = ""
            cur = f"{cur} {s}".strip()
            while len(cur) > MAX_CHARS:  # a very long sentence without a stop
                out.append(cur[:limit])
                cur = cur[limit:]
    if cur:
        out.append(cur)
    return out


def _download(url: str, dest) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    tmp.replace(dest)


def _load():
    global _voice
    if _voice is not None:
        return _voice
    try:
        from piper import PiperVoice
    except ImportError:
        raise TTSError("The voice is not installed on this server (package piper-tts).")
    name = config.TTS_VOICE
    model = config.TTS_DIR / f"{name}.onnx"
    try:
        config.TTS_DIR.mkdir(parents=True, exist_ok=True)
        for path in (model, model.with_name(model.name + ".json")):
            if not path.exists():
                _download(f"{config.TTS_VOICE_URL}/{path.name}", path)
        _voice = PiperVoice.load(model)
    except TTSError:
        raise
    except Exception as e:
        raise TTSError(f"The voice cannot load: {e}")
    return _voice


def available() -> bool:
    try:
        import piper  # noqa: F401
        return True
    except ImportError:
        return False


def speak(text: str) -> bytes:
    """WAV bytes. One call at a time: a second call waits, so the memory stays small."""
    text = clean(text)
    with _lock:
        voice = _load()
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            voice.synthesize_wav(text, w)
    return buf.getvalue()
