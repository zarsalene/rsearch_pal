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
              id TEXT PRIMARY KEY, start REAL, end REAL, minutes INTEGER DEFAULT 0, task_text TEXT, paper_id TEXT DEFAULT '',
              date TEXT, planned INTEGER DEFAULT 0, goal_id TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS xp_events(
              id TEXT PRIMARY KEY, time REAL, date TEXT, action TEXT, ref_id TEXT, xp INTEGER, UNIQUE(action, ref_id));
            CREATE TABLE IF NOT EXISTS badges(
              id TEXT PRIMARY KEY, code TEXT UNIQUE, earned_at REAL);
            CREATE TABLE IF NOT EXISTS rewards(
              id TEXT PRIMARY KEY, text TEXT, condition TEXT, earned_at REAL, claimed INTEGER DEFAULT 0, created_at REAL);
            CREATE TABLE IF NOT EXISTS ai_log(
              id INTEGER PRIMARY KEY AUTOINCREMENT, time REAL, feature TEXT, paper_id TEXT, provider TEXT, model TEXT);
            """
        )
        # The thesis has one row. An older database keeps its research question: it moves from the settings into the project one time.
        if not c.execute("SELECT 1 FROM project WHERE id=1").fetchone():
            has_settings = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='settings'").fetchone()
            old = c.execute("SELECT value FROM settings WHERE key='thesis_question'").fetchone() if has_settings else None
            c.execute("INSERT INTO project(id,title,question,stage,updated_at) VALUES(1,'',?,'',?)", ((old["value"] if old else "") or "", time.time()))
        c.execute("UPDATE extra_cards SET status='error', error='Processing stopped (server restart). Click Retry.' WHERE status IN ('processing','queued')")
        # Spaced review (Sprint 06): the columns of the FSRS state. Older rows get their date now (they are due).
        cols = {r["name"] for r in c.execute("PRAGMA table_info(review_items)")}
        for name, typ in (("due", "REAL"), ("stability", "REAL"), ("difficulty", "REAL"), ("reps", "INTEGER DEFAULT 0"), ("lapses", "INTEGER DEFAULT 0"),
                          ("last_review", "REAL"), ("fsrs_json", "TEXT")):
            if name not in cols:
                c.execute(f"ALTER TABLE review_items ADD COLUMN {name} {typ}")
        c.execute("UPDATE review_items SET due=created_at WHERE due IS NULL")
        # A word in the glossary is also a review item (kind "glossary"). Words saved before Sprint 02 get their item now.
        c.execute("INSERT INTO review_items(id,kind,paper_id,question,answer,quote,page,created_at,ref_id,due) "
                  "SELECT id,'glossary',paper_id,term,explanation,CASE WHEN source='paper' THEN explanation ELSE '' END,page,created_at,id,created_at FROM glossary "
                  "WHERE id NOT IN (SELECT ref_id FROM review_items WHERE kind='glossary')")
        # Older databases have no focus column. Add it one time.
        if "focus" not in {r["name"] for r in c.execute("PRAGMA table_info(papers)")}:
            c.execute("ALTER TABLE papers ADD COLUMN focus TEXT DEFAULT ''")
        # A restart can stop a job in the middle. Mark such papers, so you can retry them.
        c.execute("UPDATE papers SET status='error', error='Processing stopped (server restart). Click Retry.' WHERE status IN ('processing','queued')")


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
        return {r["date"]: r["n"] for r in c.execute("SELECT date, SUM(minutes) AS n FROM focus_sessions WHERE end IS NOT NULL GROUP BY date")}


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
    with conn() as c:
        rows = c.execute("SELECT * FROM goals WHERE date=? ORDER BY created_at, rowid", (date,)).fetchall()
    return [{**dict(r), "done": bool(r["done"])} for r in rows]


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
        r = c.execute("SELECT * FROM focus_sessions WHERE end IS NULL ORDER BY start DESC LIMIT 1").fetchone()
    return dict(r) if r else None


def focus_start(task_text: str, paper_id: str, planned: int, goal_id: str, date: str) -> dict:
    sid = new_id()
    with conn() as c:
        c.execute("INSERT INTO focus_sessions(id,start,end,minutes,task_text,paper_id,date,planned,goal_id) VALUES(?,?,NULL,0,?,?,?,?,?)",
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
        c.execute("UPDATE focus_sessions SET end=?, minutes=? WHERE id=?", (end, minutes, s["id"]))
        return dict(c.execute("SELECT * FROM focus_sessions WHERE id=?", (s["id"],)).fetchone())


def focus_list(date: str | None = None) -> list[dict]:
    with conn() as c:
        if date:
            rows = c.execute("SELECT * FROM focus_sessions WHERE date=? AND end IS NOT NULL ORDER BY start", (date,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM focus_sessions WHERE end IS NOT NULL ORDER BY start").fetchall()
    return [dict(r) for r in rows]


def focus_minutes(date: str) -> int:
    return sum(s["minutes"] for s in focus_list(date))


def focus_restore(row: dict) -> None:
    with conn() as c:
        c.execute("INSERT OR IGNORE INTO focus_sessions(id,start,end,minutes,task_text,paper_id,date,planned,goal_id) VALUES(?,?,?,?,?,?,?,?,?)",
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
