"""The Today page (Sprint 04): the goal, the tasks of today, one next best action, the focus time and the wins.
No AI call here. The page must be fast and free. The tone is kind: no guilt, no "you missed" text."""
import datetime as dt

from . import cards, db

GOAL_KINDS = ("papers", "words", "focus", "free")
MAX_GOALS_PER_DAY = 10
MAX_GOAL_TEXT = 200
MAX_WIN_TEXT = 300
MAX_TASK_TEXT = 200
MIN_PLANNED, MAX_PLANNED = 1, 180
MAX_SESSION_MINUTES = 600
PAST_WINS = 5


class TodayError(Exception):
    """Wrong input. The message is for the user."""


def clean_date(value) -> str:
    """A date as YYYY-MM-DD. The page sends the date of the student, because the server can be in another time zone."""
    if not value:
        return dt.date.fromtimestamp(db.now()).isoformat()
    try:
        return dt.date.fromisoformat(str(value)).isoformat()
    except ValueError:
        raise TodayError("The date must look like 2026-10-09.")


def clean_text(value, limit: int, what: str) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise TodayError(f"Write the {what}.")
    if len(text) > limit:
        raise TodayError(f"The {what} is longer than {limit} characters.")
    return text


def add_goal(date: str, text, kind: str = "free", target: int = 0) -> dict:
    if kind not in GOAL_KINDS:
        raise TodayError("Unknown kind of goal.")
    text = clean_text(text, MAX_GOAL_TEXT, "goal")
    if len(db.goals_list(date)) >= MAX_GOALS_PER_DAY:
        raise TodayError(f"A day can have {MAX_GOALS_PER_DAY} goals at most. Small goals are good. Many goals are too much.")
    return db.goal_add(date, text, kind, max(0, min(int(target or 0), 100000)))


def start_focus(task_text, paper_id: str, planned, goal_id: str, date: str) -> dict:
    if db.focus_active():
        raise TodayError("A focus session is running. Stop it first.")
    planned = 25 if planned is None else int(planned)
    if not MIN_PLANNED <= planned <= MAX_PLANNED:
        raise TodayError(f"The time must be between {MIN_PLANNED} and {MAX_PLANNED} minutes.")
    task = " ".join(str(task_text or "").split())[:MAX_TASK_TEXT]
    if paper_id and not db.get_paper(paper_id):
        raise TodayError("This paper does not exist.")
    return db.focus_start(task, paper_id or "", planned, goal_id or "", date)


def stop_focus() -> dict:
    """The server counts the minutes from its own clock. The page cannot write them."""
    s = db.focus_stop()
    if not s:
        raise TodayError("No focus session is running.")
    return s


def next_action(date: str) -> dict:
    """One next best action. Rules, in this order. No AI.
    1. A card has a field that was not found.  2. A sub-question has 0 or 1 paper.  3. A paper has no explanation.  4. The win of the day."""
    papers = [p for p in db.list_papers() if p["status"] == "ready"]
    for p in papers:
        found = [("", db.get_card(p["id"]))] + [(x["id"], x["card"]) for x in db.list_extra(p["id"]) if x["card"]]
        for card_id, card in found:
            if card and cards.missing_fields(card):
                return {"kind": "fill", "text": f"The AI did not find a field of \"{p['title']}\". Search the paper again.",
                        "button": "Open the card", "paper_id": p["id"], "card_id": card_id}
    for s in db.coverage()["sub_questions"]:
        if s["papers"] <= 1:
            n = s["position"] + 1
            return {"kind": "find_paper", "text": f"Find a paper for SQ{n}: {s['text'][:80]}. It has {s['papers']} {'paper' if s['papers'] == 1 else 'papers'}.",
                    "button": "Open the thesis page", "sub_question_id": s["id"]}
    for p in papers:
        if not db.explanation_list(p["id"]):
            return {"kind": "explain", "text": f"Explain \"{p['title']}\" in your own words.", "button": "Explain it", "paper_id": p["id"]}
    if not papers:
        return {"kind": "add_paper", "text": "Add your first paper. Click Add paper in the library.", "button": "Add a paper"}
    if not db.wins_list(date=date):
        return {"kind": "win", "text": "Write your win of the day. One small line is enough.", "button": "Write my win"}
    return {"kind": "rest", "text": "You did enough today. Rest is part of the work.", "button": ""}


def today(date: str) -> dict:
    goals = db.goals_list(date)
    wins_today = db.wins_list(date=date)
    past = db.win_random(before=date)
    return {
        "date": date,
        "project": {k: v for k, v in db.get_project().items() if k in ("title", "question", "stage")},
        "goals": goals,
        "goals_done": sum(1 for g in goals if g["done"]),
        "goals_total": len(goals),
        "next": next_action(date),
        "focus_minutes": db.focus_minutes(date),
        "active_session": db.focus_active(),
        "win_today": wins_today[0] if wins_today else None,
        "past_win": past,
    }
