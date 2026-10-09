"""Download the Piper voice file at build time, so the first Listen click does not wait. Run from backend/: python scripts/get_voice.py
If the download fails, the build still works: the server tries again at the first Listen click."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config, tts  # noqa: E402

try:
    config.TTS_DIR.mkdir(parents=True, exist_ok=True)
    for name in (f"{config.TTS_VOICE}.onnx", f"{config.TTS_VOICE}.onnx.json"):
        dest = config.TTS_DIR / name
        if not dest.exists():
            tts._download(f"{config.TTS_VOICE_URL}/{name}", dest)
    print("Voice ready:", config.TTS_DIR)
except Exception as e:
    print("Voice download skipped:", e)
