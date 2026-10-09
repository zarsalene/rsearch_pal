"""Start the backend with a fake AI. The end-to-end tests (Playwright) use it, so they need no API key and no network.
Usage: python scripts/fake_server.py [--port 8001] [--origin http://localhost:5174] [--pdf-dir DIR]
The data goes to a temporary folder. The script also writes the test PDFs (a.pdf, b.pdf) to --pdf-dir, so the browser tests can upload them."""
import argparse, os, sys, tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BACKEND), str(BACKEND / "tests")]

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=8001)
ap.add_argument("--origin", default="http://localhost:5174")
ap.add_argument("--pdf-dir", default="")
args = ap.parse_args()

# These settings win over backend/.env, so a real key never reaches this server.
os.environ.update(
    DATA_DIR=tempfile.mkdtemp(prefix="research-pal-e2e-"), APP_PASSWORD="e2e-password-123", SECRET_KEY="e" * 40, EMBEDDING_BACKEND="hash",
    GROQ_API_KEY="fake", GEMINI_API_KEY="", OPENROUTER_API_KEY="", LLM_PROVIDER="gemini", LLM_FALLBACK="groq",
    LLM_MODEL="", LLM_API_KEY="", LLM_BASE_URL="", GEMINI_MODEL="", GROQ_MODEL="", MIN_TEXT_CHARS="200", FRONTEND_ORIGIN=args.origin,
)

import uvicorn

from app import llm
from fake_ai import FakeAI
from pdfs import PAPERS, make_pdf

llm.chat_json = FakeAI()  # every module calls llm.chat_json, so this one line replaces the AI

if args.pdf_dir:
    out = Path(args.pdf_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, (_, pages) in PAPERS.items():
        make_pdf(out / name, pages)

if __name__ == "__main__":
    print(f"Fake server on http://localhost:{args.port}. Password: e2e-password-123", flush=True)
    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port, log_level="warning")
