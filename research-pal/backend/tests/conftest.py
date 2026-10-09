"""Shared fixtures. Each test gets its own empty data folder, its own search index and a fake AI.
No test calls a real AI or the network."""
import io
import os
import re
import tempfile
import uuid
from types import SimpleNamespace

# The settings must be in place before the app is imported: config.py reads them one time.
# A value that is set here has priority over backend/.env, so a real key in .env never reaches a test.
os.environ.update(
    DATA_DIR=tempfile.mkdtemp(), APP_PASSWORD="test-password-123", SECRET_KEY="x" * 40, EMBEDDING_BACKEND="hash",
    GROQ_API_KEY="fake", GEMINI_API_KEY="", OPENROUTER_API_KEY="", LLM_PROVIDER="gemini", LLM_FALLBACK="groq",
    LLM_MODEL="", LLM_API_KEY="", LLM_BASE_URL="", GEMINI_MODEL="", GROQ_MODEL="", OPENROUTER_MODEL="", OLLAMA_MODEL="",
    LLM_COOLDOWN="60", LLM_CONTEXT_CHARS="90000", LLM_MIN_CONTEXT_CHARS="20000", CHAT_CONTEXT_CHARS="24000",
    LLM_MAX_TOKENS="8000", LLM_REASONING_EFFORT="medium", LINK_THRESHOLD="0.40", MIN_TEXT_CHARS="200",
    FRONTEND_ORIGIN="http://localhost:5173",
    SUPABASE_URL="", SUPABASE_SERVICE_KEY="", DATABASE_URL="", ALLOWED_EMAILS="",  # one-user mode, whatever is in .env
)
# RP_TEST_PG=1 runs the same tests on Postgres (Supabase). Set RP_PG_URL, RP_PG_SERVICE_KEY and RP_PG_DATABASE_URL. See tests/run_pg.py.
PG_MODE = os.environ.get("RP_TEST_PG") == "1"
if PG_MODE:
    os.environ.update(SUPABASE_URL=os.environ["RP_PG_URL"], SUPABASE_SERVICE_KEY=os.environ["RP_PG_SERVICE_KEY"],
                      DATABASE_URL=os.environ["RP_PG_DATABASE_URL"], EMBEDDING_BACKEND="gemini")

import pytest
from fastapi.testclient import TestClient

# Tests that cannot apply to Postgres (multi-user mode). They test the password login, an old SQLite file or ChromaDB.
PG_SKIP = {
    "test_features.py::test_an_old_database_keeps_its_rows": "an old SQLite file",
    "test_direction.py::test_an_old_database_moves_its_question_into_the_project": "an old SQLite file",
    "test_review.py::test_old_review_items_get_a_date": "an old SQLite file",
    "test_understand.py::test_words_saved_before_this_sprint_get_a_review_item": "an old SQLite file",
    "test_vectors_real.py": "ChromaDB (one-user mode)",
    "test_settings.py::test_login": "password login is off in multi-user mode",
    "test_settings.py::test_wrong_password_is_limited": "password login is off in multi-user mode",
}


def pytest_collection_modifyitems(config, items):
    if not PG_MODE:
        return
    for item in items:
        for key, why in PG_SKIP.items():
            if item.nodeid.replace("\\", "/").endswith(key) or ("::" not in key and key in item.nodeid.replace("\\", "/")):
                item.add_marker(pytest.mark.skip(reason="Postgres run: " + why))

from app import auth, config, db, llm, main, vectors
from fake_ai import FakeAI
from fake_vectors import FakeIndex
from helpers import login
from pdfs import PAPERS, make_pdf

REAL_CHAT_JSON = llm.chat_json  # the real function, for the tests of llm.py itself
REAL_COL = vectors._col  # the real ChromaDB collection, for tests/test_vectors_real.py


def _no_network(*args, **kwargs):
    raise AssertionError("A test tried to call the network. Use the fake AI or give the test its own fake of httpx.post.")


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """An empty data folder, an empty search index and clean state in each test. No real network call."""
    data = tmp_path / "data"
    for name, value in (("DATA_DIR", data), ("PDF_DIR", data / "pdfs"), ("CHROMA_DIR", data / "chroma"), ("DB_PATH", data / "research_pal.sqlite3")):
        monkeypatch.setattr(config, name, value)
    # A fake collection in memory. See tests/fake_vectors.py for the reason. The code of vectors.py still runs.
    monkeypatch.setattr(vectors, "_col", FakeIndex().col)
    monkeypatch.setattr(llm, "_choices", {})
    monkeypatch.setattr(llm.httpx, "post", _no_network)
    llm._down_until.clear()
    auth._attempts.clear()
    if PG_MODE:
        yield from _pg_isolation(monkeypatch)
        llm._down_until.clear()
        return
    yield
    llm._down_until.clear()


def _pg_isolation(monkeypatch):
    """Postgres: each test is a new user, so it gets a new schema. The schema is dropped at the end.
    The PDF files and the vectors of the embeddings are fakes in memory (the real ones are tested in the real Supabase test)."""
    import hashlib
    import math

    from app import files

    uid = str(uuid.uuid4())

    async def who(token):
        return uid
    monkeypatch.setattr(auth, "_supabase_user", who)
    auth.set_user(uid)

    def fake_embed(texts, query=False):
        out = []
        for text in texts:
            v = [0.0] * config.GEMINI_EMBED_DIM
            for w in re.findall(r"[a-z0-9]+", text.lower()):
                h = int(hashlib.md5(w.encode()).hexdigest(), 16)
                v[h % len(v)] += 1.0 if (h >> 20) & 1 else -1.0
                v[(h >> 8) % len(v)] += 0.5
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out
    monkeypatch.setattr(vectors, "embed", fake_embed)

    store = {}
    monkeypatch.setattr(files, "save", lambda pid, data: store.__setitem__((uid, pid), data))
    monkeypatch.setattr(files, "read", lambda pid: store.get((uid, pid)))
    monkeypatch.setattr(files, "source", lambda pid: io.BytesIO(store[(uid, pid)]) if (uid, pid) in store else None)
    monkeypatch.setattr(files, "exists", lambda pid: (uid, pid) in store)
    monkeypatch.setattr(files, "ids", lambda: {p for (u, p) in store if u == uid})
    monkeypatch.setattr(files, "delete", lambda pid: store.pop((uid, pid), None))
    yield
    schema = db._schema_name(uid)
    pool = db._get_pool()
    raw = pool.getconn()
    try:
        raw.cursor().execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        raw.commit()
    finally:
        pool.putconn(raw)
        db._ready.discard(schema)


@pytest.fixture
def client():
    """A test client with the real app. The start-up code runs (database, AI choice)."""
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    """The headers of a signed-in user."""
    return login(client)


@pytest.fixture
def fake_ai(monkeypatch):
    """Replaces the AI call (llm.chat_json). Give an answer with fake_ai.when("text", answer). See tests/fake_ai.py."""
    ai = FakeAI()
    monkeypatch.setattr(llm, "chat_json", ai)
    return ai


@pytest.fixture
def real_chat_json():
    """The real llm.chat_json. Use it with a fake of httpx.post to test llm.py."""
    return REAL_CHAT_JSON


class HttpAI:
    """A fake AI provider behind the real llm.py. The saved answers and the AI use log work as in the real app.
    Give http_ai.answer a dict, or a function(body) that returns a dict. http_ai.calls lists each request. Call http_ai.activate() to start."""

    def __init__(self, monkeypatch, real_chat_json):
        self.calls, self.answer, self._mp, self._real = [], {}, monkeypatch, real_chat_json

    def post(self, url, json=None, headers=None, timeout=None):
        import json as jsonlib
        self.calls.append(json)
        out = self.answer(json) if callable(self.answer) else self.answer

        class R:
            status_code, headers = 200, {}
            def json(_): return {"choices": [{"message": {"content": jsonlib.dumps(out)}, "finish_reason": "stop"}]}

        return R()

    def activate(self):
        self._mp.setattr(llm, "chat_json", self._real)
        self._mp.setattr(llm.httpx, "post", self.post)
        return self


@pytest.fixture
def http_ai(monkeypatch, real_chat_json):
    return HttpAI(monkeypatch, real_chat_json)


@pytest.fixture
def sample_pdfs(tmp_path):
    """The test PDFs of tests/pdfs.py. {"a.pdf": obj, "b.pdf": obj}. Each obj has path, title and pages (the text of each page)."""
    out = {}
    for name, (title, pages) in PAPERS.items():
        path = tmp_path / name
        make_pdf(path, pages)
        out[name] = SimpleNamespace(path=path, title=title, pages=pages)
    return out


@pytest.fixture
def real_vectors(monkeypatch):
    """The real ChromaDB in a temporary folder, for the one test that checks it. Other tests use a fake index."""
    monkeypatch.setattr(vectors, "_col", REAL_COL)
    monkeypatch.setattr(vectors, "_client", None)
    yield vectors
    try:  # let go of the index files before the folder is removed
        from chromadb.api.shared_system_client import SharedSystemClient
        SharedSystemClient.clear_system_cache()
    except Exception:
        pass


@pytest.fixture
def clock(monkeypatch):
    """A clock that the test controls. clock.t is the time in seconds. The server uses it through db.now()."""
    class Clock:
        t = 1_000_000.0
    monkeypatch.setattr(db, "now", lambda: Clock.t)
    return Clock
