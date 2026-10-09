"""SQLite storage: papers, page texts and cards."""
import json, sqlite3, threading, time, uuid
from contextlib import contextmanager

from . import config

_lock = threading.Lock()


@contextmanager
def conn():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(config.DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    try:
        with _lock:
            yield c
            c.commit()
    finally:
        c.close()


def init() -> None:
    with conn() as c:
        c.executescript(
            """
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
            """
        )
        # The thesis has one row. An older database keeps its research question: it moves from the settings into the project one time.
        if not c.execute("SELECT 1 FROM project WHERE id=1").fetchone():
            has_settings = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='settings'").fetchone()
            old = c.execute("SELECT value FROM settings WHERE key='thesis_question'").fetchone() if has_settings else None
            c.execute("INSERT INTO project(id,title,question,stage,updated_at) VALUES(1,'',?,'',?)", ((old["value"] if old else "") or "", time.time()))
        c.execute("UPDATE extra_cards SET status='error', error='Processing stopped (server restart). Click Retry.' WHERE status IN ('processing','queued')")
        # Older databases have no focus column. Add it one time.
        if "focus" not in {r["name"] for r in c.execute("PRAGMA table_info(papers)")}:
            c.execute("ALTER TABLE papers ADD COLUMN focus TEXT DEFAULT ''")
        # A restart can stop a job in the middle. Mark such papers, so you can retry them.
        c.execute("UPDATE papers SET status='error', error='Processing stopped (server restart). Click Retry.' WHERE status IN ('processing','queued')")


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
        c.execute("DELETE FROM paper_tags WHERE paper_id=? AND card_id=?", (pid, cid))


# ---------- saved AI answers ----------
CACHE_MAX = 1000  # the oldest answers go first


def _ensure_cache_table() -> None:
    with conn() as c:
        c.execute("CREATE TABLE IF NOT EXISTS llm_cache(key TEXT PRIMARY KEY, tag TEXT, provider TEXT, model TEXT, response TEXT, created_at REAL)")


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
    with conn() as c:
        c.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")


def get_setting(key: str, default: str = "") -> str:
    _ensure_settings_table()
    with conn() as c:
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def set_setting(key: str, value: str) -> None:
    _ensure_settings_table()
    with conn() as c:
        c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
