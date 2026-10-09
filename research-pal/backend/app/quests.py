"""Quests and boss fights (Sprint 07).
Each week the server offers 3 quests that fit the PhD stage and the features that exist. The student chooses 1 or 2.
The server checks the conditions after each point event. A quest that is not done has no penalty: it just goes away.
Boss fights: the student marks a hard paper as a boss. The boss is defeated when the quiz and the Feynman check both reach 80%."""
import datetime as dt
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from . import db, features, game

MAX_CHOSEN = 2
OFFERED = 3
BOSS_PERCENT = 80
BOSS_MIN_ANSWERED = 3  # a boss needs at least 3 answered quiz questions, so that 1 of 1 does not count
BOSS_XP = 50
STAGES = ("year_1", "year_2_3", "final_year")
KINDS = ("reading", "writing", "habit", "thesis", "people")
_checking = False


class QuestError(Exception):
    """Wrong request. The message is for the user."""


@lru_cache(maxsize=1)
def catalog() -> list[dict]:
    quests = json.loads((Path(__file__).with_name("quests.json")).read_text(encoding="utf-8"))
    codes = [q["code"] for q in quests]
    assert len(codes) == len(set(codes)), "A quest code must be unique."
    for q in quests:
        assert q["kind"] in KINDS and q["condition"].get("type") and all(s == "all" or s in STAGES for s in q["stage"]), q["code"]
    return quests


def by_code(code: str) -> dict | None:
    return next((q for q in catalog() if q["code"] == code), None)


# ------------------------------------------------------------------ weeks
def week_bounds(date: str) -> tuple[dt.date, dt.date]:
    d = dt.date.fromisoformat(date)
    monday = d - dt.timedelta(days=d.weekday())
    return monday, monday + dt.timedelta(days=6)


def week_key(date: str) -> str:
    y, w, _ = dt.date.fromisoformat(date).isocalendar()
    return f"{y}-W{w:02d}"


def _in_week(date_str: str, start: dt.date, end: dt.date) -> bool:
    return bool(date_str) and start <= dt.date.fromisoformat(date_str) <= end


# ------------------------------------------------------------------ which quests fit
def available(q: dict) -> bool:
    """A quest is offered only when the feature that it needs exists and is switched on."""
    return q["unlock_feature"] is None or features.is_enabled(q["unlock_feature"])


def fits_stage(q: dict, stage: str) -> bool:
    stage = stage or "year_1"  # a student without a stage gets the quests of the first year
    return "all" in q["stage"] or stage in q["stage"]


def eligible(stage: str) -> list[dict]:
    return [q for q in catalog() if fits_stage(q, stage) and available(q)]


def pick(week: str, stage: str, recent: set[str]) -> list[dict]:
    """3 quests. The same input always gives the same quests. Quests of the last weeks come last. The kinds are mixed when possible."""
    pool = sorted(eligible(stage), key=lambda q: (q["code"] in recent, hashlib.sha256(f"{week}:{q['code']}".encode()).hexdigest()))
    chosen: list[dict] = []
    for q in pool:  # first, one quest of each kind
        if len(chosen) < OFFERED and q["kind"] not in {c["kind"] for c in chosen}:
            chosen.append(q)
    for q in pool:
        if len(chosen) < OFFERED and q not in chosen:
            chosen.append(q)
    return chosen


def offer(date: str) -> list[dict]:
    """The rows of this week. They are made at the first call of the week."""
    week = week_key(date)
    rows = db.quests_week(week)
    if not rows:
        recent = {r["code"] for r in db.quests_recent_offers(week)}
        for q in pick(week, db.get_project()["stage"], recent):
            db.quest_offer(q["code"], week)
        rows = db.quests_week(week)
    return rows


def choose(date: str, code: str) -> dict:
    rows = offer(date)
    row = next((r for r in rows if r["code"] == code), None)
    if not row:
        raise QuestError("This quest is not offered this week.")
    if row["chosen_at"]:
        return row
    if sum(1 for r in rows if r["chosen_at"]) >= MAX_CHOSEN:
        raise QuestError(f"You can choose {MAX_CHOSEN} quests each week. Drop one first. There is no penalty.")
    db.quest_choose(row["id"], db.now())
    check_all(date)
    return next(r for r in db.quests_week(week_key(date)) if r["id"] == row["id"])


def drop(date: str, code: str) -> None:
    row = next((r for r in offer(date) if r["code"] == code), None)
    if not row or not row["chosen_at"]:
        raise QuestError("This quest is not chosen.")
    if row["done_at"]:
        raise QuestError("This quest is done. It stays in your log.")
    db.quest_unchoose(row["id"])


# ------------------------------------------------------------------ conditions
def _count_table(table: str) -> int:
    with db.conn() as c:
        if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
            return 0
        return c.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]


def links_compare(start: dt.date, end: dt.date) -> int:
    """Explained links of the type "compares_with" with a verified quote in both PDFs, made this week. One link for each pair."""
    n = 0
    for key, value in db.settings_like("link:%"):
        try:
            link = json.loads(value)
        except ValueError:
            continue
        day = game.local_date(link.get("generated_at") or 0)
        both = {e.get("paper_id") for e in link.get("evidence", []) if e.get("verified")}
        if link.get("relation") == "compares_with" and {link.get("a"), link.get("b")} <= both and start <= dt.date.fromisoformat(day) <= end:
            n += 1
    return n


def progress(q: dict, start: dt.date, end: dt.date) -> tuple[int, int]:
    """(done so far, needed). The numbers come from events that the server verified."""
    cond = q["condition"]
    need = int(cond.get("count", 1))
    t = cond["type"]

    def events(action: str) -> list[dict]:
        return [e for e in db.xp_events_of(action) if _in_week(e["date"], start, end)]

    if t in ("cards_ready", "feynman_pass", "quiz_correct"):
        return len(events({"cards_ready": "card_ready"}.get(t, t))), need
    if t == "review_days":
        return len({e["date"] for e in events("review")}), need
    if t == "review_items":
        return len(events("review")), need
    if t == "wins":
        return len(events("win_written")), need
    if t == "focus_minutes":
        return sum(m for d, m in db.focus_minutes_by_day().items() if _in_week(d, start, end)), need
    if t == "words_saved":
        return sum(1 for g in db.glossary_list() if _in_week(game.local_date(g["created_at"]), start, end)), need
    if t == "links_compare":
        return links_compare(start, end), need
    if t == "eli12_boss":
        bosses = {p["id"] for p in db.list_papers() if p.get("is_boss")}
        viewed = any(a["ref_id"] in bosses and _in_week(a["date"], start, end) for a in db.activity_list("eli12_view"))
        passed = any(e["ref_id"] in bosses for e in events("feynman_pass"))
        return int(viewed) + int(passed), 2
    if t == "boss_defeated":
        return sum(1 for b in db.badges_list() if b["code"].startswith("boss:") and _in_week(game.local_date(b["earned_at"]), start, end)), need
    if t == "sub_questions":
        return len(db.list_sub_questions()), need
    if t == "tagged_all":
        subs, tags = db.list_sub_questions(), db.all_tags()
        tagged = {s for by_card in tags.values() for ids in by_card.values() for s in ids}
        return sum(1 for s in subs if s["id"] in tagged), max(len(subs), 1)
    if t in ("lit_sections", "gap_written", "pack_sent"):  # the features of later sprints. 0 until their tables exist
        if t == "lit_sections":
            return db.sections_written(300), need
        return _count_table({"gap_written": "gap_notes", "pack_sent": "packs_sent"}[t]), need
    return 0, need


def check_all(date: str | None = None) -> list[str]:
    """Mark the chosen quests of this week that are done, and give their points. Returns the codes that are new. It runs after each point event."""
    global _checking
    if _checking or not features.is_enabled("game") or not features.is_enabled("quests"):
        return []
    _checking = True
    try:
        date = date or game.local_date(db.now())
        start, end = week_bounds(date)
        week = week_key(date)
        newly = []
        for r in db.quests_week(week):
            q = by_code(r["code"])
            if not q or not r["chosen_at"] or r["done_at"]:
                continue
            have, need = progress(q, start, end)
            if have >= need:
                db.quest_done(r["id"], db.now())
                game.award("quest", f"{week}:{q['code']}", q["xp"])
                newly.append(q["code"])
        return newly
    finally:
        _checking = False


def summary(date: str) -> dict:
    start, end = week_bounds(date)
    rows = offer(date)
    check_all(date)
    rows = db.quests_week(week_key(date))
    items = []
    for r in rows:
        q = by_code(r["code"])
        if not q:
            continue
        have, need = progress(q, start, end)
        items.append({"code": q["code"], "title": q["title"], "text": q["text"], "kind": q["kind"], "xp": q["xp"], "chosen": bool(r["chosen_at"]), "done": bool(r["done_at"]),
                      "have": min(have, need), "need": need})
    log = []
    for r in db.quests_done():
        q = by_code(r["code"])
        if q:
            log.append({"code": q["code"], "title": q["title"], "week": r["week"], "xp": q["xp"], "done_at": r["done_at"]})
    return {"week": week_key(date), "week_start": start.isoformat(), "week_end": end.isoformat(), "stage": db.get_project()["stage"], "max_chosen": MAX_CHOSEN,
            "chosen": sum(1 for i in items if i["chosen"]), "quests": items, "log": log}


# ------------------------------------------------------------------ bosses
def set_boss(pid: str, flag: bool) -> None:
    if not db.get_paper(pid):
        raise QuestError("Paper not found.")
    db.paper_set_boss(pid, flag)


def boss_status(pid: str) -> dict:
    quiz = [r for r in db.review_list(pid, "quiz") if (r["tries"] or 0) > 0]
    correct = sum(1 for r in quiz if r["last_mark"] == "correct")
    quiz_pct = round(100 * correct / len(quiz)) if quiz else 0
    best = max((e["score"] for e in db.explanation_list(pid)), default=0)
    p = db.get_paper(pid) or {}
    return {"paper_id": pid, "title": p.get("title", ""), "is_boss": bool(p.get("is_boss")), "quiz_percent": quiz_pct, "quiz_answered": len(quiz), "quiz_needed": BOSS_MIN_ANSWERED,
            "feynman_best": best, "need_percent": BOSS_PERCENT, "defeated": bool(p.get("boss_defeated_at")),
            "ready": len(quiz) >= BOSS_MIN_ANSWERED and quiz_pct >= BOSS_PERCENT and best >= BOSS_PERCENT}


def check_bosses() -> list[str]:
    """Defeat each boss paper that reached 80% in the quiz and 80% in the Feynman check. One badge and 50 points for each boss."""
    won = []
    if not features.is_enabled("game") or not features.is_enabled("quests"):
        return won
    for p in db.list_papers():
        if not p.get("is_boss") or p.get("boss_defeated_at"):
            continue
        if boss_status(p["id"])["ready"]:
            db.paper_boss_defeated(p["id"], db.now())
            db.badge_add(f"boss:{p['id']}", db.now())
            game.award("boss", p["id"], BOSS_XP)
            won.append(p["id"])
    return won


def bosses() -> list[dict]:
    return [boss_status(p["id"]) for p in db.list_papers() if p.get("is_boss") or p.get("boss_defeated_at")]
