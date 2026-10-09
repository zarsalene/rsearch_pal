"""Storage: papers, page texts, cards, the game, the project, settings.
One-user mode and tests: SQLite.
Multi-user mode (SUPABASE_URL + DATABASE_URL): Postgres on Supabase. Each user has a schema of his own ("u_<user id>") with all the tables.
A user can only reach his own schema, so a query can never read the data of another user. The SQL below is the same for both."""
import json, re, sqlite3, threading, time, uuid
from contextlib import contextmanager

from . import auth, config

_lock = threading.Lock()  # SQLite only: one writer at a time
_ready: set[str] = set()  # SQLite files that have their tables, and Postgres schemas that have their tables
_pool = None
_pool_lock = threading.Lock()
_prepare_lock = threading.Lock()
_last_used: dict[int, float] = {}  # Postgres connection -> time of the last use

INTEGRITY_ERRORS: tuple = (sqlite3.IntegrityError,)
if config.USE_PG:
    import psycopg2, psycopg2.extras, psycopg2.pool
    INTEGRITY_ERRORS = (sqlite3.IntegrityError, psycopg2.IntegrityError)

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS papers(
  id TEXT PRIMARY KEY, filename TEXT, title TEXT, status TEXT, error TEXT,
  purpose TEXT, n_pages INTEGER DEFAULT 0, created_at REAL, updated_at REAL);
CREATE TABLE IF NOT EXISTS pages(
  paper_id TEXT, page INTEGER, text TEXT, PRIMARY KEY(paper_id, page));
CREATE TABLE IF NOT EXISTS cards(
  paper_id TEXT PRIMARY KEY, data TEXT, updated_at REAL);
CREATE TABLE IF NOT EXISTS extra_cards(
  id TEXT PRIMARY KEY, paper_id TEXT, focus TEXT, purpose TEXT, status TEXT, error TEXT,
  data TEXT, created_at REAL, updated_at REAL);
CREATE TABLE IF NOT EXISTS features(
  name TEXT PRIMARY KEY, enabled INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS project(
  id INTEGER PRIMARY KEY CHECK (id = 1), title TEXT NOT NULL DEFAULT '', question TEXT NOT NULL DEFAULT '',
  stage TEXT NOT NULL DEFAULT '', updated_at REAL);
CREATE TABLE IF NOT EXISTS sub_questions(
  id TEXT PRIMARY KEY, text TEXT NOT NULL, position INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS project_history(
  id INTEGER PRIMARY KEY AUTOINCREMENT, field TEXT NOT NULL, old_value TEXT, new_value TEXT, changed_at REAL);
CREATE TABLE IF NOT EXISTS paper_tags(
  paper_id TEXT NOT NULL, card_id TEXT NOT NULL DEFAULT '', sub_question_id TEXT NOT NULL,
  PRIMARY KEY(paper_id, card_id, sub_question_id));
CREATE TABLE IF NOT EXISTS glossary(
  id TEXT PRIMARY KEY, term TEXT, explanation TEXT, source TEXT, paper_id TEXT, page INTEGER DEFAULT 0, created_at REAL);
CREATE TABLE IF NOT EXISTS explanations(
  id TEXT PRIMARY KEY, paper_id TEXT, card_id TEXT, text TEXT, result_json TEXT, score INTEGER, created_at REAL);
CREATE TABLE IF NOT EXISTS review_items(
  id TEXT PRIMARY KEY, kind TEXT, paper_id TEXT, question TEXT, answer TEXT, quote TEXT, page INTEGER DEFAULT 0, created_at REAL,
  card_id TEXT DEFAULT '', ref_id TEXT DEFAULT '', last_mark TEXT DEFAULT '', tries INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS goals(
  id TEXT PRIMARY KEY, date TEXT, text TEXT, kind TEXT, target INTEGER DEFAULT 0, done INTEGER DEFAULT 0, created_at REAL);
CREATE TABLE IF NOT EXISTS wins(
  id TEXT PRIMARY KEY, date TEXT, text TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS focus_sessions(
  id TEXT PRIMARY KEY, start REAL, "end" REAL, minutes INTEGER DEFAULT 0, task_text TEXT, paper_id TEXT DEFAULT '',
  date TEXT, planned INTEGER DEFAULT 0, goal_id TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS quests_active(
  id TEXT PRIMARY KEY, code TEXT, week TEXT, chosen_at REAL, done_at REAL, UNIQUE(code, week));
CREATE TABLE IF NOT EXISTS activity(
  id TEXT PRIMARY KEY, time REAL, date TEXT, kind TEXT, ref_id TEXT);
CREATE TABLE IF NOT EXISTS xp_events(
  id TEXT PRIMARY KEY, time REAL, date TEXT, action TEXT, ref_id TEXT, xp INTEGER, UNIQUE(action, ref_id));
CREATE TABLE IF NOT EXISTS badges(
  id TEXT PRIMARY KEY, code TEXT UNIQUE, earned_at REAL);
CREATE TABLE IF NOT EXISTS rewards(
  id TEXT PRIMARY KEY, text TEXT, condition TEXT, earned_at REAL, claimed INTEGER DEFAULT 0, created_at REAL);
CREATE TABLE IF NOT EXISTS ai_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, time REAL, feature TEXT, paper_id TEXT, provider TEXT, model TEXT);

CREATE TABLE IF NOT EXISTS review_doc(
  id TEXT PRIMARY KEY, title TEXT, updated_at REAL);
CREATE TABLE IF NOT EXISTS review_sections(
  id TEXT PRIMARY KEY, doc_id TEXT, position INTEGER, heading TEXT, sub_question_id TEXT DEFAULT '', text TEXT DEFAULT '', updated_at REAL);
CREATE TABLE IF NOT EXISTS writing_log(
  id TEXT PRIMARY KEY, date TEXT, section_id TEXT, delta INTEGER, time REAL);
CREATE TABLE IF NOT EXISTS play_rounds(
  id TEXT PRIMARY KEY, game TEXT, questions_json TEXT, created_at REAL, date TEXT, finished INTEGER DEFAULT 0, score INTEGER DEFAULT 0, coins INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS play_items(
  code TEXT PRIMARY KEY, bought_at REAL, x INTEGER DEFAULT -1, y INTEGER DEFAULT -1);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS llm_cache(key TEXT PRIMARY KEY, tag TEXT, provider TEXT, model TEXT, response TEXT, created_at REAL);

"""

# Columns that older SQLite databases get later (Postgres has them from the start, see PG_EXTRA).
_REVIEW_COLUMNS = (("due", "REAL"), ("stability", "REAL"), ("difficulty", "REAL"), ("reps", "INTEGER DEFAULT 0"), ("lapses", "INTEGER DEFAULT 0"),
                   ("last_review", "REAL"), ("fsrs_json", "TEXT"))
_PAPER_COLUMNS = (("is_boss", "INTEGER DEFAULT 0"), ("boss_defeated_at", "REAL"), ("focus", "TEXT DEFAULT ''"),
                  ("authors", "TEXT DEFAULT '[]'"), ("year", "TEXT DEFAULT ''"), ("venue", "TEXT DEFAULT ''"), ("doi", "TEXT DEFAULT ''"),
                  ("cite_key", "TEXT DEFAULT ''"), ("meta_check", "TEXT DEFAULT '[]'"), ("meta_source", "TEXT DEFAULT ''"))


def _pg_ddl() -> str:
    """The Postgres version of SQLITE_SCHEMA. REAL becomes DOUBLE PRECISION (a 4-byte REAL cannot keep a time stamp).
    Each table also gets a "rowid" column, because the SQL orders by rowid. The rows hide it (see _Cur)."""
    d = SQLITE_SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY")
    d = re.sub(r"\bREAL\b", "DOUBLE PRECISION", d)
    d = re.sub(r"CREATE TABLE IF NOT EXISTS (\w+)\(", r"CREATE TABLE IF NOT EXISTS \1(rowid BIGINT GENERATED ALWAYS AS IDENTITY, ", d)
    extra = "".join(f"ALTER TABLE review_items ADD COLUMN IF NOT EXISTS {n} {t.replace('REAL', 'DOUBLE PRECISION')};\n" for n, t in _REVIEW_COLUMNS)
    extra += "".join(f"ALTER TABLE papers ADD COLUMN IF NOT EXISTS {n} {t.replace('REAL', 'DOUBLE PRECISION')};\n" for n, t in _PAPER_COLUMNS)
    extra += f"""
CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY, paper_id TEXT NOT NULL, page INTEGER, idx INTEGER, document TEXT, embedding vector({config.GEMINI_EMBED_DIM}));
CREATE INDEX IF NOT EXISTS chunks_paper_idx ON chunks(paper_id);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE TABLE IF NOT EXISTS card_vectors(paper_id TEXT PRIMARY KEY, document TEXT, embedding vector({config.GEMINI_EMBED_DIM}));
"""
    return d + extra


def _schema_name(uid: str) -> str:
    """The Postgres schema of one user. The id is checked, so it can never carry SQL."""
    h = str(uid).replace("-", "").lower()
    if not re.fullmatch(r"[0-9a-f]{32}", h):
        raise RuntimeError("Bad user id.")
    return "u_" + h


_MESSAGE = "Processing stopped (server restart). Click Retry."


def _after_tables(c) -> None:
    """Fixes that run when the tables are ready (SQLite: at start-up, Postgres: the first time a user is seen after a restart)."""
    # The thesis has one row. An older database keeps its research question: it moves from the settings into the project one time.
    if not c.execute("SELECT 1 FROM project WHERE id=1").fetchone():
        old = c.execute("SELECT value FROM settings WHERE key='thesis_question'").fetchone()
        c.execute("INSERT INTO project(id,title,question,stage,updated_at) VALUES(1,'',?,'',?)", ((old["value"] if old else "") or "", time.time()))
    # A restart can stop a job in the middle. Mark such papers, so you can retry them.
    c.execute("UPDATE extra_cards SET status='error', error=? WHERE status IN ('processing','queued')", (_MESSAGE,))
    c.execute("UPDATE papers SET status='error', error=? WHERE status IN ('processing','queued')", (_MESSAGE,))


def _sqlite_ready(c: sqlite3.Connection) -> None:
    key = str(config.DB_PATH)
    if key in _ready:
        return
    c.executescript(SQLITE_SCHEMA)
    # Older databases miss some columns. Add them one time.
    cols = {r["name"] for r in c.execute("PRAGMA table_info(review_items)")}
    for name, typ in _REVIEW_COLUMNS:
        if name not in cols:
            c.execute(f"ALTER TABLE review_items ADD COLUMN {name} {typ}")
    c.execute("UPDATE review_items SET due=created_at WHERE due IS NULL")
    paper_cols = {r["name"] for r in c.execute("PRAGMA table_info(papers)")}
    for name, typ in _PAPER_COLUMNS:
        if name not in paper_cols:
            c.execute(f"ALTER TABLE papers ADD COLUMN {name} {typ}")
    _after_tables(c)
    # A word in the glossary is also a review item (kind "glossary"). Words saved before Sprint 02 get their item now.
    c.execute("INSERT INTO review_items(id,kind,paper_id,question,answer,quote,page,created_at,ref_id,due) "
              "SELECT id,'glossary',paper_id,term,explanation,CASE WHEN source='paper' THEN explanation ELSE '' END,page,created_at,id,created_at FROM glossary "
              "WHERE id NOT IN (SELECT ref_id FROM review_items WHERE kind='glossary')")
    _ready.add(key)


class _Row(dict):
    """A row that works like a dict, and also by number (row[0]), as a SQLite row does."""

    def __getitem__(self, k):
        return list(self.values())[k] if isinstance(k, int) else dict.__getitem__(self, k)


class _Cur:
    """A cursor that gives rows as dicts, without the helper column "rowid"."""

    def __init__(self, cur):
        self.cur = cur
        self.rowcount = cur.rowcount

    @staticmethod
    def _clean(r):
        if r is None:
            return None
        r = _Row(r)
        r.pop("rowid", None)
        return r

    def fetchone(self):
        return self._clean(self.cur.fetchone())

    def fetchall(self):
        return [self._clean(r) for r in self.cur.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())


class _PgConn:
    """Gives Postgres the same small interface as SQLite: execute(sql, params) with ? marks, and rows that work like dicts."""

    def __init__(self, raw, schema: str):
        self.raw = raw
        # extra_float_digits=3: Postgres gives a time stamp with all its digits. Without it, a value that comes back is a little different.
        self.path = f'SET LOCAL search_path TO "{schema}", public, extensions; SET LOCAL extra_float_digits = 3'
        self._set = False

    @staticmethod
    def _sql(sql: str) -> str:
        sql = sql.strip().rstrip(";")
        if re.match(r"INSERT OR IGNORE INTO", sql, re.I):
            sql = re.sub(r"INSERT OR IGNORE INTO", "INSERT INTO", sql, count=1, flags=re.I) + " ON CONFLICT DO NOTHING"
        sql = sql.replace("FROM sqlite_master WHERE type='table' AND name=", "FROM information_schema.tables WHERE table_schema=current_schema() AND table_name=")
        return sql.replace("%", "%%").replace("?", "%s")

    def _prefix(self) -> str:
        if self._set:
            return ""
        self._set = True
        return self.path + "; "

    def execute(self, sql: str, params=()):
        cur = self.raw.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(self._prefix() + self._sql(sql), tuple(params))
        return _Cur(cur)

    def executemany(self, sql: str, rows) -> None:
        cur = self.raw.cursor()
        pre = self._prefix()
        if pre:
            cur.execute(pre.rstrip("; "))
        psycopg2.extras.execute_batch(cur, self._sql(sql), list(rows))


def _get_pool():
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = psycopg2.pool.ThreadedConnectionPool(1, 8, config.DATABASE_URL, connect_timeout=15, keepalives=1, keepalives_idle=30)
    return _pool


def _checkout(pool):
    raw = pool.getconn()
    if raw.closed or time.time() - _last_used.get(id(raw), 0) > 30:  # a long-idle connection may be closed by the server
        try:
            raw.cursor().execute("SELECT 1")
            raw.rollback()
        except Exception:
            pool.putconn(raw, close=True)
            raw = pool.getconn()
    return raw


def _pg_prepare(pool, schema: str) -> None:
    """Make the schema and the tables of one user, one time for each start of the server."""
    with _prepare_lock:
        if schema in _ready:
            return
        raw = _checkout(pool)
        try:
            cur = raw.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (schema,))
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            cur.execute(f'SET LOCAL search_path TO "{schema}", public, extensions; SET LOCAL extra_float_digits = 3')
            cur.execute(_pg_ddl())
            _after_tables(_PgConnPrepared(cur))
            raw.commit()
            _ready.add(schema)
        except BaseException:
            try:
                raw.rollback()
            except Exception:
                pass
            raise
        finally:
            _last_used[id(raw)] = time.time()
            pool.putconn(raw, close=bool(raw.closed))


class _PgConnPrepared:
    """The same interface on one open cursor (used when the tables are made)."""

    def __init__(self, cur):
        self.cur = cur

    def execute(self, sql: str, params=()):
        self.cur.execute(_PgConn._sql(sql), tuple(params))
        return _Cur(self.cur)


@contextmanager
def conn():
    if config.USE_PG:
        schema = _schema_name(auth.current_user())
        pool = _get_pool()
        if schema not in _ready:
            _pg_prepare(pool, schema)
        raw = _checkout(pool)
        try:
            try:
                yield _PgConn(raw, schema)
                raw.commit()
            except BaseException:
                try:
                    raw.rollback()
                except Exception:
                    pass
                raise
        finally:
            _last_used[id(raw)] = time.time()
            pool.putconn(raw, close=bool(raw.closed))
        return
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(config.DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    try:
        with _lock:
            _sqlite_ready(c)
            yield c
            c.commit()
    finally:
        c.close()


def ping() -> None:
    """Postgres: one small query, so a free Supabase project is not paused for lack of use. It never raises."""
    if not config.USE_PG:
        return
    try:
        pool = _get_pool()
        raw = _checkout(pool)
        try:
            raw.cursor().execute("SELECT 1")
            raw.rollback()
        finally:
            _last_used[id(raw)] = time.time()
            pool.putconn(raw, close=bool(raw.closed))
    except Exception:
        pass


def init() -> None:
    """Start-up. SQLite: make the tables. Postgres: the tables of a user are made when the user is first seen."""
    if not config.USE_PG:
        with conn():
            pass


def now() -> float:
    """The clock of the server. A test can replace it."""
    return time.time()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def add_paper(pid: str, filename: str, purpose: str, focus: str = "") -> None:
    now = time.time()
    with conn() as c:
        c.execute("INSERT INTO papers(id,filename,title,status,error,purpose,focus,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                  (pid, filename, filename.rsplit(".", 1)[0], "queued", "", purpose, focus, now, now))


def update_paper(pid: str, **fields) -> None:
    if not fields:
        return
    fields["updated_at"] = time.time()
    cols = ", ".join(f"{k}=?" for k in fields)
    with conn() as c:
        c.execute(f"UPDATE papers SET {cols} WHERE id=?", (*fields.values(), pid))


def get_paper(pid: str):
    with conn() as c:
        r = c.execute("SELECT * FROM papers WHERE id=?", (pid,)).fetchone()
    return dict(r) if r else None


def list_papers():
    with conn() as c:
        rows = c.execute("SELECT p.*, c.data AS card FROM papers p LEFT JOIN cards c ON c.paper_id=p.id ORDER BY p.created_at DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        card = json.loads(d.pop("card")) if d.get("card") else None
        d["verdict"] = (card or {}).get("verdict", "")
        d["keywords"] = (card or {}).get("keywords", [])
        out.append(d)
    return out


def save_pages(pid: str, pages: list[str]) -> None:
    with conn() as c:
        c.execute("DELETE FROM pages WHERE paper_id=?", (pid,))
        c.executemany("INSERT INTO pages(paper_id,page,text) VALUES(?,?,?)", [(pid, i + 1, t) for i, t in enumerate(pages)])


def get_pages(pid: str) -> list[str]:
    with conn() as c:
        rows = c.execute("SELECT text FROM pages WHERE paper_id=? ORDER BY page", (pid,)).fetchall()
    return [r["text"] for r in rows]


def save_card(pid: str, card: dict) -> None:
    with conn() as c:
        c.execute("INSERT INTO cards(paper_id,data,updated_at) VALUES(?,?,?) ON CONFLICT(paper_id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
                  (pid, json.dumps(card, ensure_ascii=False), time.time()))


def get_card(pid: str):
    with conn() as c:
        r = c.execute("SELECT data FROM cards WHERE paper_id=?", (pid,)).fetchone()
    return json.loads(r["data"]) if r else None


def delete_paper(pid: str) -> None:
    _ensure_settings_table()
    _ensure_cache_table()
    with conn() as c:
        for t in ("pages", "cards", "paper_tags"):
            c.execute(f"DELETE FROM {t} WHERE paper_id=?", (pid,))
        c.execute("DELETE FROM papers WHERE id=?", (pid,))
        c.execute("DELETE FROM settings WHERE key LIKE ?", (f"link:%{pid}%",))  # saved link explanations of this paper
        c.execute("DELETE FROM llm_cache WHERE tag=?", (pid,))  # saved AI answers of this paper
        c.execute("DELETE FROM extra_cards WHERE paper_id=?", (pid,))
        c.execute("DELETE FROM explanations WHERE paper_id=?", (pid,))
        c.execute("DELETE FROM review_items WHERE paper_id=? AND kind IN ('quiz','idea')", (pid,))  # the words of the glossary stay


# ---------- more cards for one paper ----------
# The first card of a paper is in the table "cards". Each other card has its own focus, status and data.
MAX_EXTRA_CARDS = 12


def add_extra(pid: str, focus: str, purpose: str, cid: str | None = None, card: dict | None = None) -> str:
    """card is given when a backup is restored. Then the card is ready at once."""
    cid, now = cid or new_id(), time.time()
    with conn() as c:
        c.execute("INSERT INTO extra_cards(id,paper_id,focus,purpose,status,error,data,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                  (cid, pid, focus, purpose, "ready" if card else "queued", "", json.dumps(card, ensure_ascii=False) if card else None, now, now))
    return cid


def _extra_row(r) -> dict:
    d = dict(r)
    d["card"] = json.loads(d.pop("data")) if d.get("data") else None
    return d


def get_extra(pid: str, cid: str):
    with conn() as c:
        r = c.execute("SELECT * FROM extra_cards WHERE id=? AND paper_id=?", (cid, pid)).fetchone()
    return _extra_row(r) if r else None


def list_extra(pid: str) -> list[dict]:
    with conn() as c:
        rows = c.execute("SELECT * FROM extra_cards WHERE paper_id=? ORDER BY created_at", (pid,)).fetchall()
    return [_extra_row(r) for r in rows]


def update_extra(cid: str, **fields) -> None:
    if "card" in fields:
        fields["data"] = json.dumps(fields.pop("card"), ensure_ascii=False)
    fields["updated_at"] = time.time()
    cols = ", ".join(f"{k}=?" for k in fields)
    with conn() as c:
        c.execute(f"UPDATE extra_cards SET {cols} WHERE id=?", (*fields.values(), cid))


def delete_extra(pid: str, cid: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM extra_cards WHERE id=? AND paper_id=?", (cid, pid))
        c.execute("DELETE FROM review_items WHERE paper_id=? AND kind='idea' AND card_id=?", (pid, cid))
        c.execute("DELETE FROM paper_tags WHERE paper_id=? AND card_id=?", (pid, cid))

# ---------- saved AI answers ----------
CACHE_MAX = 1000  # the oldest answers go first


def _ensure_cache_table() -> None:
    """The table is in the schema. This function stays, so the callers do not change."""


def cache_get(key: str):
    _ensure_cache_table()
    with conn() as c:
        r = c.execute("SELECT response FROM llm_cache WHERE key=?", (key,)).fetchone()
    try:
        return json.loads(r["response"]) if r else None
    except ValueError:
        return None


def cache_put(key: str, tag: str, provider: str, model: str, response: dict) -> None:
    _ensure_cache_table()
    with conn() as c:
        c.execute("INSERT INTO llm_cache(key,tag,provider,model,response,created_at) VALUES(?,?,?,?,?,?) "
                  "ON CONFLICT(key) DO UPDATE SET tag=excluded.tag, provider=excluded.provider, model=excluded.model, response=excluded.response, created_at=excluded.created_at",
                  (key, tag, provider, model, json.dumps(response, ensure_ascii=False), time.time()))
        c.execute("DELETE FROM llm_cache WHERE key NOT IN (SELECT key FROM llm_cache ORDER BY created_at DESC LIMIT ?)", (CACHE_MAX,))


def cache_count() -> int:
    _ensure_cache_table()
    with conn() as c:
        return c.execute("SELECT COUNT(*) AS n FROM llm_cache").fetchone()["n"]


def cache_clear() -> None:
    _ensure_cache_table()
    with conn() as c:
        c.execute("DELETE FROM llm_cache")


# ---------- thesis: title, question, stage, sub-questions and paper tags ----------
STAGES = {"": "Not set", "year_1": "Year 1", "year_2_3": "Year 2-3", "final_year": "Final year"}
MAX_SUB_QUESTIONS = 10


def get_project() -> dict:
    with conn() as c:
        r = c.execute("SELECT title, question, stage, updated_at FROM project WHERE id=1").fetchone()
    return dict(r) if r else {"title": "", "question": "", "stage": "", "updated_at": None}


def thesis_question() -> str:
    return get_project()["question"]


def save_project(changes: dict, record: bool = True) -> dict:
    """changes: any of title, question, stage. A change of the title or the question writes one row in the history (the old value stays).
    record=False is for a restore from a backup."""
    now = time.time()
    with conn() as c:
        old = dict(c.execute("SELECT title, question, stage FROM project WHERE id=1").fetchone())
        for field, new in changes.items():
            if new == old[field]:
                continue
            if record and field in ("title", "question"):
                c.execute("INSERT INTO project_history(field,old_value,new_value,changed_at) VALUES(?,?,?,?)", (field, old[field], new, now))
            c.execute(f"UPDATE project SET {field}=?, updated_at=? WHERE id=1", (new, now))
    return get_project()


def project_history() -> list[dict]:
    """The newest change first."""
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT id, field, old_value, new_value, changed_at FROM project_history ORDER BY id DESC")]


def list_sub_questions() -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT id, text, position FROM sub_questions ORDER BY position, rowid")]


def get_sub_question(sid: str):
    with conn() as c:
        r = c.execute("SELECT id, text, position FROM sub_questions WHERE id=?", (sid,)).fetchone()
    return dict(r) if r else None


def add_sub_question(text: str, sid: str | None = None) -> dict:
    sid = sid or new_id()
    with conn() as c:
        n = c.execute("SELECT COUNT(*) AS n FROM sub_questions").fetchone()["n"]
        c.execute("INSERT INTO sub_questions(id,text,position) VALUES(?,?,?)", (sid, text, n))
    return get_sub_question(sid)


def update_sub_question(sid: str, text: str | None = None, position: int | None = None) -> dict | None:
    """position is the new place in the list (0 is the first). The other items move, so the places stay 0, 1, 2 ..."""
    with conn() as c:
        if not c.execute("SELECT 1 FROM sub_questions WHERE id=?", (sid,)).fetchone():
            return None
        if text is not None:
            c.execute("UPDATE sub_questions SET text=? WHERE id=?", (text, sid))
        if position is not None:
            ids = [r["id"] for r in c.execute("SELECT id FROM sub_questions ORDER BY position, rowid")]
            ids.remove(sid)
            ids.insert(max(0, min(position, len(ids))), sid)
            c.executemany("UPDATE sub_questions SET position=? WHERE id=?", [(i, x) for i, x in enumerate(ids)])
    return get_sub_question(sid)


def delete_sub_question(sid: str) -> bool:
    with conn() as c:
        if not c.execute("DELETE FROM sub_questions WHERE id=?", (sid,)).rowcount:
            return False
        c.execute("DELETE FROM paper_tags WHERE sub_question_id=?", (sid,))
        c.executemany("UPDATE sub_questions SET position=? WHERE id=?",
                      [(i, r["id"]) for i, r in enumerate(c.execute("SELECT id FROM sub_questions ORDER BY position, rowid").fetchall())])
    return True


def set_tags(pid: str, card_id: str, sub_question_ids: list[str]) -> None:
    """The tags of one card of a paper (card_id "" = the first card). The new list replaces the old list."""
    with conn() as c:
        c.execute("DELETE FROM paper_tags WHERE paper_id=? AND card_id=?", (pid, card_id))
        c.executemany("INSERT INTO paper_tags(paper_id,card_id,sub_question_id) VALUES(?,?,?)", [(pid, card_id, s) for s in dict.fromkeys(sub_question_ids)])


def all_tags() -> dict[str, dict[str, list[str]]]:
    """{paper id: {card id: [sub-question ids]}}. The ids follow the order of the sub-questions."""
    out: dict[str, dict[str, list[str]]] = {}
    with conn() as c:
        rows = c.execute("SELECT t.paper_id, t.card_id, t.sub_question_id FROM paper_tags t JOIN sub_questions s ON s.id=t.sub_question_id "
                         "ORDER BY s.position").fetchall()
    for r in rows:
        out.setdefault(r["paper_id"], {}).setdefault(r["card_id"], []).append(r["sub_question_id"])
    return out


def coverage() -> dict:
    """For each sub-question: the number of papers with a tag (a paper counts one time, also with several tagged cards)."""
    with conn() as c:
        rows = c.execute("SELECT s.id, s.text, s.position, COUNT(DISTINCT t.paper_id) AS papers FROM sub_questions s "
                         "LEFT JOIN paper_tags t ON t.sub_question_id=s.id GROUP BY s.id ORDER BY s.position, s.rowid").fetchall()
        total = c.execute("SELECT COUNT(*) AS n FROM papers").fetchone()["n"]
        tagged = c.execute("SELECT COUNT(DISTINCT paper_id) AS n FROM paper_tags").fetchone()["n"]
    return {"sub_questions": [dict(r) for r in rows], "papers": total, "untagged": total - tagged}
# ---------- literature review: one document, sections, the words of each day (Sprint 08) ----------
def review_doc() -> dict:
    with conn() as c:
        r = c.execute("SELECT * FROM review_doc ORDER BY rowid LIMIT 1").fetchone()
        if not r:
            c.execute("INSERT INTO review_doc(id,title,updated_at) VALUES(?,?,?)", (new_id(), "Literature review", now()))
            r = c.execute("SELECT * FROM review_doc ORDER BY rowid LIMIT 1").fetchone()
    return dict(r)


def review_doc_title(title: str) -> None:
    d = review_doc()
    with conn() as c:
        c.execute("UPDATE review_doc SET title=?, updated_at=? WHERE id=?", (title, now(), d["id"]))


def review_sections(doc_id: str) -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM review_sections WHERE doc_id=? ORDER BY position, rowid", (doc_id,))]


def review_section_get(sid: str):
    with conn() as c:
        r = c.execute("SELECT * FROM review_sections WHERE id=?", (sid,)).fetchone()
    return dict(r) if r else None


def review_section_add(doc_id: str, heading: str, sub_question_id: str = "", text: str = "", sid: str | None = None) -> dict:
    sid = sid or new_id()
    with conn() as c:
        n = c.execute("SELECT COUNT(*) AS n FROM review_sections WHERE doc_id=?", (doc_id,)).fetchone()["n"]
        c.execute("INSERT INTO review_sections(id,doc_id,position,heading,sub_question_id,text,updated_at) VALUES(?,?,?,?,?,?,?)", (sid, doc_id, n, heading, sub_question_id, text, now()))
    return review_section_get(sid)


def review_section_update(sid: str, **fields) -> None:
    allowed = {k: v for k, v in fields.items() if k in ("text", "heading")}
    if allowed:
        with conn() as c:
            c.execute(f"UPDATE review_sections SET {', '.join(f'{k}=?' for k in allowed)}, updated_at=? WHERE id=?", (*allowed.values(), now(), sid))


def review_section_delete(sid: str) -> bool:
    with conn() as c:
        return c.execute("DELETE FROM review_sections WHERE id=?", (sid,)).rowcount > 0


def review_sections_order(doc_id: str, ids: list[str]) -> None:
    with conn() as c:
        have = [r["id"] for r in c.execute("SELECT id FROM review_sections WHERE doc_id=? ORDER BY position, rowid", (doc_id,))]
        final = [i for i in ids if i in have] + [i for i in have if i not in ids]
        c.executemany("UPDATE review_sections SET position=? WHERE id=?", [(n, i) for n, i in enumerate(final)])


def sections_written(min_words: int) -> int:
    """Sections with at least this many words of the student (quote lines do not count)."""
    n = 0
    for s in review_sections(review_doc()["id"]):
        if sum(len(line.split()) for line in (s["text"] or "").splitlines() if not line.lstrip().startswith(">")) >= min_words:
            n += 1
    return n


def writing_log_add(date: str, section_id: str, delta: int) -> None:
    with conn() as c:
        c.execute("INSERT INTO writing_log(id,date,section_id,delta,time) VALUES(?,?,?,?,?)", (new_id(), date, section_id, delta, now()))


def words_on(date: str) -> int:
    with conn() as c:
        return c.execute("SELECT COALESCE(SUM(delta),0) AS n FROM writing_log WHERE date=?", (date,)).fetchone()["n"]


# ---------- quests, bosses, activity (Sprint 07) ----------
def quests_week(week: str) -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM quests_active WHERE week=? ORDER BY rowid", (week,))]


def quests_recent_offers(week: str, weeks: int = 3) -> list[dict]:
    """The quests that were offered in the last weeks (not this week). The picker puts them last, so the offers change."""
    with conn() as c:
        rows = c.execute("SELECT DISTINCT week FROM quests_active WHERE week<? ORDER BY week DESC LIMIT ?", (week, weeks)).fetchall()
        return [dict(r) for w in rows for r in c.execute("SELECT * FROM quests_active WHERE week=?", (w["week"],))]


def quest_offer(code: str, week: str, qid: str | None = None, chosen_at: float | None = None, done_at: float | None = None) -> None:
    with conn() as c:
        c.execute("INSERT OR IGNORE INTO quests_active(id,code,week,chosen_at,done_at) VALUES(?,?,?,?,?)", (qid or new_id(), code, week, chosen_at, done_at))


def quest_choose(qid: str, when: float) -> None:
    with conn() as c:
        c.execute("UPDATE quests_active SET chosen_at=? WHERE id=?", (when, qid))


def quest_unchoose(qid: str) -> None:
    with conn() as c:
        c.execute("UPDATE quests_active SET chosen_at=NULL WHERE id=? AND done_at IS NULL", (qid,))


def quest_done(qid: str, when: float) -> None:
    with conn() as c:
        c.execute("UPDATE quests_active SET done_at=? WHERE id=? AND done_at IS NULL", (when, qid))


def quests_done() -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM quests_active WHERE done_at IS NOT NULL ORDER BY done_at DESC")]


def quests_all() -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM quests_active ORDER BY week, rowid")]


def paper_set_boss(pid: str, flag: bool) -> None:
    update_paper(pid, is_boss=int(flag))


def paper_boss_defeated(pid: str, when: float) -> None:
    with conn() as c:
        c.execute("UPDATE papers SET boss_defeated_at=? WHERE id=?", (when, pid))


def activity_add(kind: str, ref_id: str, aid: str | None = None, when: float | None = None, date: str | None = None) -> None:
    """A small record of something that the student did and that is not points (for example: the view "like I am 12" of a paper)."""
    import datetime as dt
    when = when or now()
    with conn() as c:
        c.execute("INSERT OR IGNORE INTO activity(id,time,date,kind,ref_id) VALUES(?,?,?,?,?)", (aid or new_id(), when, date or dt.date.fromtimestamp(when).isoformat(), kind, ref_id))


def activity_list(kind: str | None = None) -> list[dict]:
    with conn() as c:
        if kind:
            return [dict(r) for r in c.execute("SELECT * FROM activity WHERE kind=? ORDER BY time", (kind,))]
        return [dict(r) for r in c.execute("SELECT * FROM activity ORDER BY time")]


def settings_like(pattern: str) -> list[tuple[str, str]]:
    _ensure_settings_table()
    with conn() as c:
        return [(r["key"], r["value"]) for r in c.execute("SELECT key, value FROM settings WHERE key LIKE ?", (pattern,))]


# ---------- the game: XP events, badges, own rewards. Only the server writes XP (see game.py). ----------
def xp_add(action: str, ref_id: str, xp: int, when: float, date: str) -> bool:
    """False if this (action, ref_id) has XP already. The table has a UNIQUE key, so a second row is never possible."""
    with conn() as c:
        return c.execute("INSERT OR IGNORE INTO xp_events(id,time,date,action,ref_id,xp) VALUES(?,?,?,?,?,?)", (new_id(), when, date, action, ref_id, xp)).rowcount > 0


def xp_total() -> int:
    with conn() as c:
        return c.execute("SELECT COALESCE(SUM(xp),0) AS n FROM xp_events").fetchone()["n"]


def xp_counts() -> dict[str, int]:
    with conn() as c:
        return {r["action"]: r["n"] for r in c.execute("SELECT action, COUNT(*) AS n FROM xp_events GROUP BY action")}


def xp_days() -> set[str]:
    with conn() as c:
        return {r["date"] for r in c.execute("SELECT DISTINCT date FROM xp_events")}


def xp_by_day(action: str | None = None, count: bool = False) -> dict[str, int]:
    q = "SELECT date, " + ("COUNT(*)" if count else "SUM(xp)") + " AS n FROM xp_events" + (" WHERE action=?" if action else "") + " GROUP BY date"
    with conn() as c:
        return {r["date"]: r["n"] for r in c.execute(q, (action,) if action else ())}


def xp_recent(n: int = 10) -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT id, time, date, action, ref_id, xp FROM xp_events ORDER BY time DESC, rowid DESC LIMIT ?", (n,))]


def xp_all() -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT id, time, date, action, ref_id, xp FROM xp_events ORDER BY time, rowid")]


def focus_minutes_by_day() -> dict[str, int]:
    with conn() as c:
        return {r["date"]: r["n"] for r in c.execute("SELECT date, SUM(minutes) AS n FROM focus_sessions WHERE \"end\" IS NOT NULL GROUP BY date")}


def badge_add(code: str, when: float) -> bool:
    with conn() as c:
        return c.execute("INSERT OR IGNORE INTO badges(id,code,earned_at) VALUES(?,?,?)", (new_id(), code, when)).rowcount > 0


def badges_list() -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM badges ORDER BY earned_at, rowid")]


def reward_add(text: str, condition: str, rid: str | None = None, earned_at: float | None = None, claimed: bool = False, created_at: float | None = None) -> dict:
    rid = rid or new_id()
    with conn() as c:
        c.execute("INSERT INTO rewards(id,text,condition,earned_at,claimed,created_at) VALUES(?,?,?,?,?,?)", (rid, text, condition, earned_at, int(claimed), created_at or now()))
        return reward_row(c.execute("SELECT * FROM rewards WHERE id=?", (rid,)).fetchone())


def reward_row(r) -> dict:
    return {**dict(r), "claimed": bool(r["claimed"])}


def rewards_list() -> list[dict]:
    with conn() as c:
        return [reward_row(r) for r in c.execute("SELECT * FROM rewards ORDER BY created_at, rowid")]


def reward_get(rid: str):
    with conn() as c:
        r = c.execute("SELECT * FROM rewards WHERE id=?", (rid,)).fetchone()
    return reward_row(r) if r else None


def reward_earn(rid: str, when: float) -> None:
    with conn() as c:
        c.execute("UPDATE rewards SET earned_at=? WHERE id=? AND earned_at IS NULL", (when, rid))


def reward_claim(rid: str) -> None:
    with conn() as c:
        c.execute("UPDATE rewards SET claimed=1 WHERE id=? AND earned_at IS NOT NULL", (rid,))


def reward_delete(rid: str) -> bool:
    with conn() as c:
        return c.execute("DELETE FROM rewards WHERE id=?", (rid,)).rowcount > 0


def xp_restore(row: dict) -> None:
    with conn() as c:
        c.execute("INSERT OR IGNORE INTO xp_events(id,time,date,action,ref_id,xp) VALUES(?,?,?,?,?,?)", (row["id"], row["time"], row["date"], row["action"], row["ref_id"], row["xp"]))


def badge_restore(code: str, when: float) -> None:
    badge_add(code, when)


# ---------- goals, wins and focus sessions (the Today page) ----------
def goals_list(date: str) -> list[dict]:
    """The goals of one day. A goal of the kind "words" shows the words that you wrote in the literature review today."""
    with conn() as c:
        rows = c.execute("SELECT * FROM goals WHERE date=? ORDER BY created_at, rowid", (date,)).fetchall()
    words = words_on(date) if any(r["kind"] == "words" for r in rows) else 0
    return [{**dict(r), "done": bool(r["done"]), "progress": words if r["kind"] == "words" else None} for r in rows]


def goal_add(date: str, text: str, kind: str, target: int, gid: str | None = None, done: bool = False, created_at: float | None = None) -> dict:
    gid = gid or new_id()
    with conn() as c:
        c.execute("INSERT INTO goals(id,date,text,kind,target,done,created_at) VALUES(?,?,?,?,?,?,?)", (gid, date, text, kind, target, int(done), created_at or now()))
    return goal_get(gid)


def goal_get(gid: str):
    with conn() as c:
        r = c.execute("SELECT * FROM goals WHERE id=?", (gid,)).fetchone()
    return {**dict(r), "done": bool(r["done"])} if r else None


def goal_update(gid: str, **fields) -> dict | None:
    allowed = {k: (int(v) if k == "done" else v) for k, v in fields.items() if k in ("text", "target", "done") and v is not None}
    if allowed:
        with conn() as c:
            c.execute(f"UPDATE goals SET {', '.join(f'{k}=?' for k in allowed)} WHERE id=?", (*allowed.values(), gid))
    return goal_get(gid)


def goal_delete(gid: str) -> bool:
    with conn() as c:
        return c.execute("DELETE FROM goals WHERE id=?", (gid,)).rowcount > 0


def goals_all() -> list[dict]:
    with conn() as c:
        return [{**dict(r), "done": bool(r["done"])} for r in c.execute("SELECT * FROM goals ORDER BY date, created_at")]


def win_add(date: str, text: str, wid: str | None = None, created_at: float | None = None) -> dict:
    wid = wid or new_id()
    with conn() as c:
        c.execute("INSERT INTO wins(id,date,text,created_at) VALUES(?,?,?,?)", (wid, date, text, created_at or now()))
        return dict(c.execute("SELECT * FROM wins WHERE id=?", (wid,)).fetchone())


def wins_list(limit: int = 50, date: str | None = None, before: str | None = None) -> list[dict]:
    """The newest first. date: only this day. before: only the days before this date."""
    q, args = "SELECT * FROM wins WHERE 1=1", []
    if date:
        q += " AND date=?"
        args.append(date)
    if before:
        q += " AND date<?"
        args.append(before)
    with conn() as c:
        return [dict(r) for r in c.execute(q + " ORDER BY date DESC, created_at DESC LIMIT ?", (*args, limit))]


def win_get(wid: str):
    with conn() as c:
        r = c.execute("SELECT * FROM wins WHERE id=?", (wid,)).fetchone()
    return dict(r) if r else None


def win_random(before: str):
    with conn() as c:
        r = c.execute("SELECT * FROM wins WHERE date<? ORDER BY RANDOM() LIMIT 1", (before,)).fetchone()
    return dict(r) if r else None


def win_delete(wid: str) -> bool:
    with conn() as c:
        return c.execute("DELETE FROM wins WHERE id=?", (wid,)).rowcount > 0


def focus_active():
    with conn() as c:
        r = c.execute("SELECT * FROM focus_sessions WHERE \"end\" IS NULL ORDER BY start DESC LIMIT 1").fetchone()
    return dict(r) if r else None


def focus_start(task_text: str, paper_id: str, planned: int, goal_id: str, date: str) -> dict:
    sid = new_id()
    with conn() as c:
        c.execute("INSERT INTO focus_sessions(id,start,\"end\",minutes,task_text,paper_id,date,planned,goal_id) VALUES(?,?,NULL,0,?,?,?,?,?)",
                  (sid, now(), task_text, paper_id, date, planned, goal_id))
        return dict(c.execute("SELECT * FROM focus_sessions WHERE id=?", (sid,)).fetchone())


def focus_stop(max_minutes: int = 600):
    """Close the running session. The server counts the minutes from its own clock."""
    s = focus_active()
    if not s:
        return None
    end = now()
    minutes = max(0, min(int(round((end - s["start"]) / 60)), max_minutes))
    with conn() as c:
        c.execute("UPDATE focus_sessions SET \"end\"=?, minutes=? WHERE id=?", (end, minutes, s["id"]))
        return dict(c.execute("SELECT * FROM focus_sessions WHERE id=?", (s["id"],)).fetchone())


def focus_list(date: str | None = None) -> list[dict]:
    with conn() as c:
        if date:
            rows = c.execute("SELECT * FROM focus_sessions WHERE date=? AND \"end\" IS NOT NULL ORDER BY start", (date,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM focus_sessions WHERE \"end\" IS NOT NULL ORDER BY start").fetchall()
    return [dict(r) for r in rows]


def focus_minutes(date: str) -> int:
    return sum(s["minutes"] for s in focus_list(date))


def focus_restore(row: dict) -> None:
    with conn() as c:
        c.execute("INSERT OR IGNORE INTO focus_sessions(id,start,\"end\",minutes,task_text,paper_id,date,planned,goal_id) VALUES(?,?,?,?,?,?,?,?,?)",
                  (row["id"], row["start"], row["end"], row["minutes"], row["task_text"], row["paper_id"], row["date"], row["planned"], row["goal_id"]))


# ---------- attempts of the Feynman check ----------
def explanation_add(paper_id: str, card_id: str, text: str, result: dict, score: int, eid: str | None = None, created_at: float | None = None) -> str:
    eid = eid or new_id()
    with conn() as c:
        c.execute("INSERT INTO explanations(id,paper_id,card_id,text,result_json,score,created_at) VALUES(?,?,?,?,?,?,?)",
                  (eid, paper_id, card_id or "", text, json.dumps(result, ensure_ascii=False), int(score), created_at or time.time()))
    return eid


def _explanation_row(r) -> dict:
    d = dict(r)
    d["result"] = json.loads(d.pop("result_json") or "{}")
    return d


def explanation_list(paper_id: str, card_id: str | None = None) -> list[dict]:
    """Newest first. card_id None = all cards of the paper."""
    with conn() as c:
        if card_id is None:
            rows = c.execute("SELECT * FROM explanations WHERE paper_id=? ORDER BY created_at DESC", (paper_id,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM explanations WHERE paper_id=? AND card_id=? ORDER BY created_at DESC", (paper_id, card_id)).fetchall()
    return [_explanation_row(r) for r in rows]


def explanation_list_all() -> list[dict]:
    with conn() as c:
        return [_explanation_row(r) for r in c.execute("SELECT * FROM explanations ORDER BY created_at")]


def explanation_get(eid: str):
    with conn() as c:
        r = c.execute("SELECT * FROM explanations WHERE id=?", (eid,)).fetchone()
    return _explanation_row(r) if r else None


def explanation_delete(eid: str) -> bool:
    with conn() as c:
        return c.execute("DELETE FROM explanations WHERE id=?", (eid,)).rowcount > 0


# ---------- review items: quiz questions and glossary words (the spaced review of a later sprint uses them) ----------
def review_add(kind: str, paper_id: str, question: str, answer: str, quote: str, page: int, card_id: str = "", ref_id: str = "",
               rid: str | None = None, created_at: float | None = None) -> str:
    rid = rid or new_id()
    with conn() as c:
        c.execute("INSERT INTO review_items(id,kind,paper_id,question,answer,quote,page,created_at,card_id,ref_id,due) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                  (rid, kind, paper_id, question, answer, quote, int(page or 0), created_at or now(), card_id or "", ref_id, created_at or now()))
    return rid


def review_get(rid: str):
    with conn() as c:
        r = c.execute("SELECT * FROM review_items WHERE id=?", (rid,)).fetchone()
    return dict(r) if r else None


def review_list(paper_id: str | None = None, kind: str | None = None) -> list[dict]:
    q, args = "SELECT * FROM review_items WHERE 1=1", []
    if paper_id is not None:
        q += " AND paper_id=?"
        args.append(paper_id)
    if kind:
        q += " AND kind=?"
        args.append(kind)
    with conn() as c:
        return [dict(r) for r in c.execute(q + " ORDER BY created_at, rowid", args)]


def review_apply(rid: str, s: dict) -> None:
    """Save the FSRS state after an answer."""
    with conn() as c:
        c.execute("UPDATE review_items SET due=?, stability=?, difficulty=?, reps=?, lapses=?, last_review=?, fsrs_json=? WHERE id=?",
                  (s["due"], s["stability"], s["difficulty"], s["reps"], s["lapses"], s["last_review"], s["fsrs_json"], rid))


def review_state_rows() -> list[dict]:
    """The schedule of every item, for the backup."""
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT id, kind, ref_id, paper_id, due, stability, difficulty, reps, lapses, last_review, fsrs_json FROM review_items "
                                           "WHERE reps > 0 OR fsrs_json IS NOT NULL")]


def review_restore_state(row: dict) -> bool:
    """Put a saved schedule on the item with the same id, or the same kind and ref_id (the words and the main ideas get new ids when they are made again)."""
    with conn() as c:
        r = c.execute("SELECT id FROM review_items WHERE id=?", (row["id"],)).fetchone() or \
            (c.execute("SELECT id FROM review_items WHERE kind=? AND ref_id=? AND ref_id!=''", (row["kind"], row["ref_id"])).fetchone() if row.get("ref_id") else None)
        if not r:
            return False
        c.execute("UPDATE review_items SET due=?, stability=?, difficulty=?, reps=?, lapses=?, last_review=?, fsrs_json=? WHERE id=?",
                  (row["due"], row["stability"], row["difficulty"], row["reps"], row["lapses"], row["last_review"], row["fsrs_json"], r["id"]))
        return True


def xp_events_of(action: str) -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT id, date, ref_id, xp FROM xp_events WHERE action=?", (action,))]


def review_mark(rid: str, mark: str) -> None:
    with conn() as c:
        c.execute("UPDATE review_items SET last_mark=?, tries=tries+1 WHERE id=?", (mark, rid))


# ---------- glossary: the words that the student looked up ----------
def glossary_add(term: str, explanation: str, source: str, paper_id: str, page: int = 0, gid: str | None = None, created_at: float | None = None) -> dict:
    """One row for each term and paper. The same term again gives the saved row. source: "paper" or "ai"."""
    with conn() as c:
        r = c.execute("SELECT * FROM glossary WHERE lower(term)=lower(?) AND paper_id=?", (term, paper_id)).fetchone()
        if r:
            return dict(r)
        gid = gid or new_id()
        c.execute("INSERT INTO glossary(id,term,explanation,source,paper_id,page,created_at) VALUES(?,?,?,?,?,?,?)",
                  (gid, term, explanation, source, paper_id, int(page or 0), created_at or time.time()))
        c.execute("INSERT INTO review_items(id,kind,paper_id,question,answer,quote,page,created_at,ref_id,due) VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (new_id(), "glossary", paper_id, term, explanation, explanation if source == "paper" else "", int(page or 0), created_at or now(), gid, created_at or now()))
        return dict(c.execute("SELECT * FROM glossary WHERE id=?", (gid,)).fetchone())


def glossary_find(term: str, paper_id: str):
    with conn() as c:
        r = c.execute("SELECT * FROM glossary WHERE lower(term)=lower(?) AND paper_id=?", (term, paper_id)).fetchone()
    return dict(r) if r else None


def glossary_list(q: str = "") -> list[dict]:
    like = f"%{q.strip().lower()}%"
    with conn() as c:
        rows = c.execute(
            "SELECT g.*, p.title AS paper_title FROM glossary g LEFT JOIN papers p ON p.id=g.paper_id "
            "WHERE ?='%%' OR lower(g.term) LIKE ? OR lower(g.explanation) LIKE ? ORDER BY lower(g.term)", (like, like, like)).fetchall()
    return [dict(r) for r in rows]


def glossary_delete(gid: str) -> bool:
    with conn() as c:
        c.execute("DELETE FROM review_items WHERE kind='glossary' AND ref_id=?", (gid,))
        return c.execute("DELETE FROM glossary WHERE id=?", (gid,)).rowcount > 0


# ---------- AI use log: one row for each AI answer that did not come from the saved answers ----------
def ai_log_add(feature: str, paper_id: str, provider: str, model: str, when: float | None = None) -> None:
    with conn() as c:
        c.execute("INSERT INTO ai_log(time,feature,paper_id,provider,model) VALUES(?,?,?,?,?)", (when or time.time(), feature, paper_id, provider, model))


def ai_log_list(limit: int = 100) -> dict:
    with conn() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM ai_log ORDER BY id DESC LIMIT ?", (limit,))]
        by = {r["feature"]: r["n"] for r in c.execute("SELECT feature, COUNT(*) AS n FROM ai_log GROUP BY feature ORDER BY n DESC")}
    return {"total": sum(by.values()), "by_feature": by, "rows": rows}


def ai_log_has(row: dict) -> bool:
    with conn() as c:
        return c.execute("SELECT 1 FROM ai_log WHERE time=? AND feature=? AND paper_id=? AND provider=? AND model=?",
                         (row["time"], row["feature"], row["paper_id"], row["provider"], row["model"])).fetchone() is not None


# ---------- feature switches ----------
def get_feature(name: str):
    """True or False when the student chose. None when there is no choice yet (the feature uses its default)."""
    with conn() as c:
        r = c.execute("SELECT enabled FROM features WHERE name=?", (name,)).fetchone()
    return None if r is None else bool(r["enabled"])


def set_feature(name: str, enabled: bool) -> None:
    with conn() as c:
        c.execute("INSERT INTO features(name,enabled) VALUES(?,?) ON CONFLICT(name) DO UPDATE SET enabled=excluded.enabled", (name, int(enabled)))


def _ensure_settings_table() -> None:
    """The table is in the schema. This function stays, so the callers do not change."""


def get_setting(key: str, default: str = "") -> str:
    _ensure_settings_table()
    with conn() as c:
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def set_setting(key: str, value: str) -> None:
    _ensure_settings_table()
    with conn() as c:
        c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


# ---------- Duck Island (Sprint 14): rounds of the mini-games and the items that the student bought ----------
def play_round_add(game: str, questions: list[dict], date: str, rid: str | None = None) -> str:
    rid = rid or new_id()
    with conn() as c:
        c.execute("INSERT INTO play_rounds(id,game,questions_json,created_at,date) VALUES(?,?,?,?,?)", (rid, game, json.dumps(questions, ensure_ascii=False), now(), date))
    return rid


def play_round_get(rid: str):
    with conn() as c:
        r = c.execute("SELECT * FROM play_rounds WHERE id=?", (rid,)).fetchone()
    return {**dict(r), "questions": json.loads(r["questions_json"])} if r else None


def play_round_finish(rid: str, score: int, coins: int) -> bool:
    """False if the round is finished already. The table update is the lock: a round pays one time only."""
    with conn() as c:
        return c.execute("UPDATE play_rounds SET finished=1, score=?, coins=? WHERE id=? AND finished=0", (score, coins, rid)).rowcount > 0


def play_rounds_all() -> list[dict]:
    with conn() as c:
        return [{**dict(r), "questions": json.loads(r["questions_json"])} for r in c.execute("SELECT * FROM play_rounds ORDER BY created_at")]


def play_coins_on(date: str) -> int:
    with conn() as c:
        return c.execute("SELECT COALESCE(SUM(coins),0) AS n FROM play_rounds WHERE finished=1 AND date=?", (date,)).fetchone()["n"]


def play_coins_total() -> int:
    with conn() as c:
        return c.execute("SELECT COALESCE(SUM(coins),0) AS n FROM play_rounds WHERE finished=1").fetchone()["n"]


def play_items_list() -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM play_items ORDER BY bought_at")]


def play_item_buy(code: str, when: float | None = None, x: int = -1, y: int = -1) -> bool:
    with conn() as c:
        return c.execute("INSERT OR IGNORE INTO play_items(code,bought_at,x,y) VALUES(?,?,?,?)", (code, when or now(), x, y)).rowcount > 0


def play_item_place(code: str, x: int, y: int) -> None:
    with conn() as c:
        c.execute("UPDATE play_items SET x=?, y=? WHERE code=?", (x, y, code))


def play_review_material() -> list[dict]:
    """Quiz questions and glossary words from the papers: the rows that have a quote."""
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM review_items WHERE quote != '' AND kind IN ('quiz','glossary') ORDER BY created_at, id")]
