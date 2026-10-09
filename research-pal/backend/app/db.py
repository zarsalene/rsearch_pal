"""Storage: papers, page texts, cards, words, settings.
One-user mode and tests: SQLite. Multi-user mode (DATABASE_URL + SUPABASE_URL): Postgres on Supabase.
Every row has a user_id. Every query filters by the user of the request (auth.current_user()), so users never see each other's data."""
import json, sqlite3, threading, time, uuid
from contextlib import contextmanager

from . import auth, config

_lock = threading.Lock()  # SQLite only: one writer at a time
_ready: set[str] = set()  # SQLite files that have their tables
_pool = None
_pool_lock = threading.Lock()
_last_used: dict[int, float] = {}  # Postgres connection -> time of last use

INTEGRITY_ERRORS: tuple = (sqlite3.IntegrityError,)
if config.USE_PG:
    import psycopg2, psycopg2.extras, psycopg2.pool
    INTEGRITY_ERRORS = (sqlite3.IntegrityError, psycopg2.IntegrityError)

TABLES = ("papers", "pages", "cards", "extra_cards", "features", "glossary", "ai_log", "llm_cache", "settings", "xp_events", "battles")

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS papers(
  id TEXT PRIMARY KEY, filename TEXT, title TEXT, status TEXT, error TEXT,
  purpose TEXT, n_pages INTEGER DEFAULT 0, created_at REAL, updated_at REAL, focus TEXT DEFAULT '', user_id TEXT NOT NULL DEFAULT 'local');
CREATE TABLE IF NOT EXISTS pages(
  paper_id TEXT, page INTEGER, text TEXT, user_id TEXT NOT NULL DEFAULT 'local', PRIMARY KEY(paper_id, page));
CREATE TABLE IF NOT EXISTS cards(
  paper_id TEXT PRIMARY KEY, data TEXT, updated_at REAL, user_id TEXT NOT NULL DEFAULT 'local');
CREATE TABLE IF NOT EXISTS extra_cards(
  id TEXT PRIMARY KEY, paper_id TEXT, focus TEXT, purpose TEXT, status TEXT, error TEXT,
  data TEXT, created_at REAL, updated_at REAL, user_id TEXT NOT NULL DEFAULT 'local');
CREATE TABLE IF NOT EXISTS features(
  name TEXT PRIMARY KEY, enabled INTEGER NOT NULL, user_id TEXT NOT NULL DEFAULT 'local');
CREATE TABLE IF NOT EXISTS glossary(
  id TEXT PRIMARY KEY, term TEXT, explanation TEXT, source TEXT, paper_id TEXT, page INTEGER DEFAULT 0, created_at REAL, user_id TEXT NOT NULL DEFAULT 'local');
CREATE TABLE IF NOT EXISTS ai_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, time REAL, feature TEXT, paper_id TEXT, provider TEXT, model TEXT, user_id TEXT NOT NULL DEFAULT 'local');
CREATE TABLE IF NOT EXISTS llm_cache(
  key TEXT PRIMARY KEY, tag TEXT, provider TEXT, model TEXT, response TEXT, created_at REAL, user_id TEXT NOT NULL DEFAULT 'local');
CREATE TABLE IF NOT EXISTS settings(
  key TEXT PRIMARY KEY, value TEXT, user_id TEXT NOT NULL DEFAULT 'local');
CREATE TABLE IF NOT EXISTS xp_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT, ref_id TEXT, xp INTEGER, time REAL, user_id TEXT NOT NULL DEFAULT 'local', UNIQUE(user_id, action, ref_id));
CREATE TABLE IF NOT EXISTS battles(
  id TEXT PRIMARY KEY, paper_id TEXT, status TEXT, data TEXT, created_at REAL, updated_at REAL, user_id TEXT NOT NULL DEFAULT 'local');
"""


def _uid() -> str:
    return auth.current_user()


def _on(*cols: str) -> str:
    """The conflict target. In Postgres the key of these tables also has the user id."""
    return "(" + ",".join((["user_id"] if config.USE_PG else []) + list(cols)) + ")"


def _j(v):
    """A JSON value. SQLite gives text. Postgres (jsonb) gives an object."""
    if v is None or isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v)
    except ValueError:
        return None


def _sqlite_ready(c: sqlite3.Connection) -> None:
    key = str(config.DB_PATH)
    if key in _ready:
        return
    c.executescript(SQLITE_SCHEMA)
    for t in TABLES:  # an older database has no user_id and no focus column. Add them one time.
        cols = {r["name"] for r in c.execute(f"PRAGMA table_info({t})")}
        if "user_id" not in cols:
            c.execute(f"ALTER TABLE {t} ADD COLUMN user_id TEXT NOT NULL DEFAULT 'local'")
    if "focus" not in {r["name"] for r in c.execute("PRAGMA table_info(papers)")}:
        c.execute("ALTER TABLE papers ADD COLUMN focus TEXT DEFAULT ''")
    _ready.add(key)


class _PgConn:
    """Gives Postgres the same small interface as SQLite: execute(sql, params) with ? marks, and rows that work like dicts."""

    def __init__(self, raw):
        self.raw = raw

    @staticmethod
    def _sql(sql: str) -> str:
        return sql.replace("%", "%%").replace("?", "%s")

    def execute(self, sql: str, params=()):
        cur = self.raw.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(self._sql(sql), tuple(params))
        return cur

    def executemany(self, sql: str, rows) -> None:
        psycopg2.extras.execute_batch(self.raw.cursor(), self._sql(sql), list(rows))


def _get_pool():
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = psycopg2.pool.ThreadedConnectionPool(1, 6, config.DATABASE_URL, connect_timeout=15, keepalives=1, keepalives_idle=30)
    return _pool


@contextmanager
def conn():
    if config.USE_PG:
        pool = _get_pool()
        raw = pool.getconn()
        try:
            if raw.closed or time.time() - _last_used.get(id(raw), 0) > 30:  # a long-idle connection may be closed by the server
                try:
                    raw.cursor().execute("SELECT 1")
                    raw.rollback()
                except Exception:
                    pool.putconn(raw, close=True)
                    raw = pool.getconn()
            try:
                yield _PgConn(raw)
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


def init() -> None:
    with conn() as c:
        # A restart can stop a job in the middle. Mark such papers, so you can retry them.
        msg = "Processing stopped (server restart). Click Retry."
        c.execute("UPDATE extra_cards SET status='error', error=? WHERE status IN ('processing','queued')", (msg,))
        c.execute("UPDATE papers SET status='error', error=? WHERE status IN ('processing','queued')", (msg,))


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def add_paper(pid: str, filename: str, purpose: str, focus: str = "") -> None:
    now = time.time()
    with conn() as c:
        c.execute("INSERT INTO papers(id,user_id,filename,title,status,error,purpose,focus,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (pid, _uid(), filename, filename.rsplit(".", 1)[0], "queued", "", purpose, focus, now, now))


def update_paper(pid: str, **fields) -> None:
    if not fields:
        return
    fields["updated_at"] = time.time()
    cols = ", ".join(f"{k}=?" for k in fields)
    with conn() as c:
        c.execute(f"UPDATE papers SET {cols} WHERE id=? AND user_id=?", (*fields.values(), pid, _uid()))


def get_paper(pid: str):
    with conn() as c:
        r = c.execute("SELECT * FROM papers WHERE id=? AND user_id=?", (pid, _uid())).fetchone()
    return dict(r) if r else None


def list_papers():
    with conn() as c:
        rows = c.execute("SELECT p.*, c.data AS card FROM papers p LEFT JOIN cards c ON c.paper_id=p.id AND c.user_id=p.user_id "
                         "WHERE p.user_id=? ORDER BY p.created_at DESC", (_uid(),)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        card = _j(d.pop("card"))
        d["verdict"] = (card or {}).get("verdict", "")
        d["keywords"] = (card or {}).get("keywords", [])
        out.append(d)
    return out


def save_pages(pid: str, pages: list[str]) -> None:
    with conn() as c:
        c.execute("DELETE FROM pages WHERE paper_id=? AND user_id=?", (pid, _uid()))
        c.executemany("INSERT INTO pages(user_id,paper_id,page,text) VALUES(?,?,?,?)", [(_uid(), pid, i + 1, t) for i, t in enumerate(pages)])


def get_pages(pid: str) -> list[str]:
    with conn() as c:
        rows = c.execute("SELECT text FROM pages WHERE paper_id=? AND user_id=? ORDER BY page", (pid, _uid())).fetchall()
    return [r["text"] for r in rows]


def save_card(pid: str, card: dict) -> None:
    with conn() as c:
        c.execute("INSERT INTO cards(paper_id,user_id,data,updated_at) VALUES(?,?,?,?) ON CONFLICT(paper_id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
                  (pid, _uid(), json.dumps(card, ensure_ascii=False), time.time()))


def get_card(pid: str):
    with conn() as c:
        r = c.execute("SELECT data FROM cards WHERE paper_id=? AND user_id=?", (pid, _uid())).fetchone()
    return _j(r["data"]) if r else None


def delete_paper(pid: str) -> None:
    u = _uid()
    with conn() as c:
        for t in ("pages", "cards", "battles"):  # the XP of the student stays: it is a list of work that was done
            c.execute(f"DELETE FROM {t} WHERE paper_id=? AND user_id=?", (pid, u))
        c.execute("DELETE FROM papers WHERE id=? AND user_id=?", (pid, u))
        c.execute("DELETE FROM settings WHERE key LIKE ? AND user_id=?", (f"link:%{pid}%", u))  # saved link explanations of this paper
        c.execute("DELETE FROM llm_cache WHERE tag=? AND user_id=?", (pid, u))  # saved AI answers of this paper
        c.execute("DELETE FROM extra_cards WHERE paper_id=? AND user_id=?", (pid, u))


# ---------- more cards for one paper ----------
# The first card of a paper is in the table "cards". Each other card has its own focus, status and data.
MAX_EXTRA_CARDS = 12


def add_extra(pid: str, focus: str, purpose: str, cid: str | None = None, card: dict | None = None) -> str:
    """card is given when a backup is restored. Then the card is ready at once."""
    cid, now = cid or new_id(), time.time()
    with conn() as c:
        c.execute("INSERT INTO extra_cards(id,user_id,paper_id,focus,purpose,status,error,data,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (cid, _uid(), pid, focus, purpose, "ready" if card else "queued", "", json.dumps(card, ensure_ascii=False) if card else None, now, now))
    return cid


def _extra_row(r) -> dict:
    d = dict(r)
    d["card"] = _j(d.pop("data"))
    return d


def get_extra(pid: str, cid: str):
    with conn() as c:
        r = c.execute("SELECT * FROM extra_cards WHERE id=? AND paper_id=? AND user_id=?", (cid, pid, _uid())).fetchone()
    return _extra_row(r) if r else None


def list_extra(pid: str) -> list[dict]:
    with conn() as c:
        rows = c.execute("SELECT * FROM extra_cards WHERE paper_id=? AND user_id=? ORDER BY created_at", (pid, _uid())).fetchall()
    return [_extra_row(r) for r in rows]


def update_extra(cid: str, **fields) -> None:
    if "card" in fields:
        fields["data"] = json.dumps(fields.pop("card"), ensure_ascii=False)
    fields["updated_at"] = time.time()
    cols = ", ".join(f"{k}=?" for k in fields)
    with conn() as c:
        c.execute(f"UPDATE extra_cards SET {cols} WHERE id=? AND user_id=?", (*fields.values(), cid, _uid()))


def delete_extra(pid: str, cid: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM extra_cards WHERE id=? AND paper_id=? AND user_id=?", (cid, pid, _uid()))


# ---------- saved AI answers ----------
CACHE_MAX = 1000  # the oldest answers go first (for each user)


def cache_get(key: str):
    with conn() as c:
        r = c.execute("SELECT response FROM llm_cache WHERE key=? AND user_id=?", (key, _uid())).fetchone()
    return _j(r["response"]) if r else None


def cache_put(key: str, tag: str, provider: str, model: str, response: dict) -> None:
    u = _uid()
    with conn() as c:
        c.execute("INSERT INTO llm_cache(key,user_id,tag,provider,model,response,created_at) VALUES(?,?,?,?,?,?,?) "
                  f"ON CONFLICT{_on('key')} DO UPDATE SET tag=excluded.tag, provider=excluded.provider, model=excluded.model, response=excluded.response, created_at=excluded.created_at",
                  (key, u, tag, provider, model, json.dumps(response, ensure_ascii=False), time.time()))
        c.execute("DELETE FROM llm_cache WHERE user_id=? AND key NOT IN (SELECT key FROM llm_cache WHERE user_id=? ORDER BY created_at DESC LIMIT ?)", (u, u, CACHE_MAX))


def cache_count() -> int:
    with conn() as c:
        return c.execute("SELECT COUNT(*) AS n FROM llm_cache WHERE user_id=?", (_uid(),)).fetchone()["n"]


def cache_clear() -> None:
    with conn() as c:
        c.execute("DELETE FROM llm_cache WHERE user_id=?", (_uid(),))


# ---------- glossary: the words that the student looked up ----------
def glossary_add(term: str, explanation: str, source: str, paper_id: str, page: int = 0, gid: str | None = None, created_at: float | None = None) -> dict:
    """One row for each term and paper. The same term again gives the saved row. source: "paper" or "ai"."""
    u = _uid()
    with conn() as c:
        r = c.execute("SELECT * FROM glossary WHERE lower(term)=lower(?) AND paper_id=? AND user_id=?", (term, paper_id, u)).fetchone()
        if r:
            return dict(r)
        gid = gid or new_id()
        c.execute("INSERT INTO glossary(id,user_id,term,explanation,source,paper_id,page,created_at) VALUES(?,?,?,?,?,?,?,?)",
                  (gid, u, term, explanation, source, paper_id, int(page or 0), created_at or time.time()))
        return dict(c.execute("SELECT * FROM glossary WHERE id=? AND user_id=?", (gid, u)).fetchone())


def glossary_find(term: str, paper_id: str):
    with conn() as c:
        r = c.execute("SELECT * FROM glossary WHERE lower(term)=lower(?) AND paper_id=? AND user_id=?", (term, paper_id, _uid())).fetchone()
    return dict(r) if r else None


def glossary_list(q: str = "") -> list[dict]:
    sql = "SELECT g.*, p.title AS paper_title FROM glossary g LEFT JOIN papers p ON p.id=g.paper_id AND p.user_id=g.user_id WHERE g.user_id=?"
    args: list = [_uid()]
    if q.strip():
        like = f"%{q.strip().lower()}%"
        sql += " AND (lower(g.term) LIKE ? OR lower(g.explanation) LIKE ?)"
        args += [like, like]
    with conn() as c:
        rows = c.execute(sql + " ORDER BY lower(g.term)", args).fetchall()
    return [dict(r) for r in rows]


def glossary_delete(gid: str) -> bool:
    with conn() as c:
        return c.execute("DELETE FROM glossary WHERE id=? AND user_id=?", (gid, _uid())).rowcount > 0


# ---------- AI use log: one row for each AI answer that did not come from the saved answers ----------
def ai_log_add(feature: str, paper_id: str, provider: str, model: str, when: float | None = None) -> None:
    with conn() as c:
        c.execute("INSERT INTO ai_log(user_id,time,feature,paper_id,provider,model) VALUES(?,?,?,?,?,?)", (_uid(), when or time.time(), feature, paper_id, provider, model))


def ai_log_list(limit: int = 100) -> dict:
    u = _uid()
    with conn() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM ai_log WHERE user_id=? ORDER BY id DESC LIMIT ?", (u, limit))]
        by = {r["feature"]: r["n"] for r in c.execute("SELECT feature, COUNT(*) AS n FROM ai_log WHERE user_id=? GROUP BY feature ORDER BY n DESC", (u,))}
    for r in rows:
        r.pop("user_id", None)
    return {"total": sum(by.values()), "by_feature": by, "rows": rows}


def ai_log_has(row: dict) -> bool:
    with conn() as c:
        return c.execute("SELECT 1 FROM ai_log WHERE time=? AND feature=? AND paper_id=? AND provider=? AND model=? AND user_id=?",
                         (row["time"], row["feature"], row["paper_id"], row["provider"], row["model"], _uid())).fetchone() is not None


# ---------- feature switches ----------
def get_feature(name: str):
    """True or False when the student chose. None when there is no choice yet (the feature uses its default)."""
    with conn() as c:
        r = c.execute("SELECT enabled FROM features WHERE name=? AND user_id=?", (name, _uid())).fetchone()
    return None if r is None else bool(r["enabled"])


def set_feature(name: str, enabled: bool) -> None:
    with conn() as c:
        c.execute(f"INSERT INTO features(name,user_id,enabled) VALUES(?,?,?) ON CONFLICT{_on('name')} DO UPDATE SET enabled=excluded.enabled", (name, _uid(), bool(enabled)))


# ---------- game: the list of XP and the boss battles ----------
def xp_add(action: str, ref_id: str, xp: int, when: float | None = None) -> bool:
    """One row for each (action, ref_id). The same pair again gives False and adds no XP: a piece of work gives points one time only."""
    with conn() as c:
        cur = c.execute("INSERT INTO xp_events(user_id,action,ref_id,xp,time) VALUES(?,?,?,?,?) ON CONFLICT DO NOTHING",
                        (_uid(), action, ref_id, int(xp), when or time.time()))
        return cur.rowcount > 0


def xp_list() -> list[dict]:
    with conn() as c:
        rows = c.execute("SELECT action, ref_id, xp, time FROM xp_events WHERE user_id=? ORDER BY time, id", (_uid(),)).fetchall()
    return [dict(r) for r in rows]


def _battle_row(r) -> dict:
    d = dict(r)
    d["data"] = _j(d["data"]) or {}
    d.pop("user_id", None)
    return d


def battle_add(bid: str, pid: str, data: dict, status: str = "active", when: float | None = None) -> None:
    now = when or time.time()
    with conn() as c:
        c.execute("INSERT INTO battles(id,user_id,paper_id,status,data,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                  (bid, _uid(), pid, status, json.dumps(data, ensure_ascii=False), now, now))


def battle_get(bid: str):
    with conn() as c:
        r = c.execute("SELECT * FROM battles WHERE id=? AND user_id=?", (bid, _uid())).fetchone()
    return _battle_row(r) if r else None


def battle_update(bid: str, status: str, data: dict) -> None:
    with conn() as c:
        c.execute("UPDATE battles SET status=?, data=?, updated_at=? WHERE id=? AND user_id=?", (status, json.dumps(data, ensure_ascii=False), time.time(), bid, _uid()))


def battle_list(pid: str | None = None, status: str | None = None) -> list[dict]:
    sql, args = "SELECT * FROM battles WHERE user_id=?", [_uid()]
    if pid:
        sql, args = sql + " AND paper_id=?", args + [pid]
    if status:
        sql, args = sql + " AND status=?", args + [status]
    with conn() as c:
        rows = c.execute(sql + " ORDER BY created_at", args).fetchall()
    return [_battle_row(r) for r in rows]


# ---------- settings ----------
def settings_with_prefix(prefix: str) -> list[tuple[str, str]]:
    """The saved values whose key starts with prefix (the saved link explanations, for example)."""
    with conn() as c:
        rows = c.execute("SELECT key, value FROM settings WHERE key LIKE ? AND user_id=?", (prefix.replace("%", "") + "%", _uid())).fetchall()
    return [(r["key"], r["value"]) for r in rows]


def get_setting(key: str, default: str = "") -> str:
    with conn() as c:
        r = c.execute("SELECT value FROM settings WHERE key=? AND user_id=?", (key, _uid())).fetchone()
    return r["value"] if r else default


def set_setting(key: str, value: str) -> None:
    with conn() as c:
        c.execute(f"INSERT INTO settings(key,user_id,value) VALUES(?,?,?) ON CONFLICT{_on('key')} DO UPDATE SET value=excluded.value", (key, _uid(), value))
