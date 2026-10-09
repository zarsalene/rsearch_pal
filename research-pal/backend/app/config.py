"""Settings. All values come from environment variables."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Read backend/.env if it exists. Real environment variables keep priority.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", "./data")).resolve()
PDF_DIR = DATA_DIR / "pdfs"
CHROMA_DIR = DATA_DIR / "chroma"
DB_PATH = DATA_DIR / "research_pal.sqlite3"

APP_PASSWORD = os.getenv("APP_PASSWORD", "")
SECRET_KEY = os.getenv("SECRET_KEY", "")
FRONTEND_ORIGINS = [o.strip().rstrip("/") for o in os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").split(",") if o.strip()]
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 14  # 14 days

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024
MAX_PAGES = int(os.getenv("MAX_PAGES", "80"))
MIN_TEXT_CHARS = int(os.getenv("MIN_TEXT_CHARS", "800"))  # less text = scanned PDF

PROVIDERS = {
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "key_env": "GEMINI_API_KEY", "model": "gemini-flash-latest"},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "key_env": "GROQ_API_KEY", "model": "llama-3.3-70b-versatile"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "key_env": "OPENROUTER_API_KEY", "model": "meta-llama/llama-3.3-70b-instruct"},
    "ollama": {"base_url": "http://localhost:11434/v1", "key_env": "", "model": "llama3.1:8b"},
}


# Models that you can pick in Settings. You can also type any other model name that the provider knows.
MODEL_SUGGESTIONS = {
    "gemini": ["gemini-flash-latest", "gemini-3.5-flash", "gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.5-pro"],
    "groq": ["llama-3.3-70b-versatile", "openai/gpt-oss-120b", "openai/gpt-oss-20b"],
    "openrouter": ["meta-llama/llama-3.3-70b-instruct"],
    "ollama": ["llama3.1:8b"],
}


def _provider(name: str, primary: bool, model: str | None = None, legacy: bool = True) -> dict:
    """Settings of one provider. GEMINI_MODEL, GROQ_MODEL ... set the model of one provider.
    LLM_MODEL, LLM_BASE_URL and LLM_API_KEY (old names) apply to the first provider only.
    model: the model that the student chose in Settings. It has priority over the environment.
    The API keys always come from the environment. They never go through the web page."""
    p = PROVIDERS[name]
    old = primary and legacy
    return {
        "name": name,
        "base_url": ((os.getenv("LLM_BASE_URL") if old else "") or p["base_url"]).rstrip("/"),
        "model": model or os.getenv(f"{name.upper()}_MODEL") or (os.getenv("LLM_MODEL") if old else "") or p["model"],
        "key": ((os.getenv("LLM_API_KEY") if old else "") or (os.getenv(p["key_env"], "") if p["key_env"] else "")),
    }


def build_chain(names: list[str], models: dict[str, str] | None = None, legacy: bool = True) -> list[dict]:
    models = models or {}
    return [_provider(n, i == 0, models.get(n), legacy) for i, n in enumerate(names)]


# The first provider is the default. If it fails, the server tries the next one. The next call tries the first one again.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
if LLM_PROVIDER not in PROVIDERS:
    LLM_PROVIDER = "gemini"
_names = [LLM_PROVIDER]
for _n in os.getenv("LLM_FALLBACK", "groq").replace(";", ",").split(","):
    _n = _n.strip().lower()
    if _n in PROVIDERS and _n not in _names:
        _names.append(_n)
LLM_CHAIN = build_chain(_names)
# After a provider fails (limit, outage, wrong key), the server skips it for this time. Then it tries it again. 0 = never skip.
LLM_COOLDOWN = float(os.getenv("LLM_COOLDOWN", "60"))
# Old names: they describe the first provider.
LLM_BASE_URL, LLM_MODEL, LLM_API_KEY = LLM_CHAIN[0]["base_url"], LLM_CHAIN[0]["model"], LLM_CHAIN[0]["key"]
# The paper body goes to the AI in full if it fits in this limit (4 characters = about 1 token).
# If the provider refuses the size (free-tier limit), the server tries again with a smaller part.
LLM_CONTEXT_CHARS = int(os.getenv("LLM_CONTEXT_CHARS", "90000"))
LLM_MIN_CONTEXT_CHARS = int(os.getenv("LLM_MIN_CONTEXT_CHARS", "20000"))
# The chat sends only the best passages of the selected papers, so it needs less text than a card.
CHAT_CONTEXT_CHARS = int(os.getenv("CHAT_CONTEXT_CHARS", "24000"))
# Reasoning models (gpt-oss) use output tokens to think. A small limit cuts the JSON.
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "8000"))
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "medium").strip().lower()  # low|medium|high|"" (off)
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))

EMBEDDING_BACKEND = os.getenv("EMBEDDING_BACKEND", "default").strip().lower()  # default | gemini | hash
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")
GEMINI_EMBED_DIM = int(os.getenv("GEMINI_EMBED_DIM", "768"))
LINK_THRESHOLD = float(os.getenv("LINK_THRESHOLD", "0.40"))


def check_required() -> None:
    """Stop at start-up if a security setting is missing. The app must never run without a password."""
    problems = []
    if len(APP_PASSWORD) < 8:
        problems.append("APP_PASSWORD must have at least 8 characters.")
    if len(SECRET_KEY) < 24:
        problems.append("SECRET_KEY must have at least 24 characters.")
    if problems:
        raise RuntimeError("Configuration error: " + " ".join(problems))
