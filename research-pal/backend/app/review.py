"""Spaced review (Sprint 06). The Knowledge Garden.
Each review item (a quiz question, a glossary word or the main idea of a card) has a date for the next review.
The open FSRS algorithm (the algorithm of Anki) sets the date after each answer of the student.
No AI call here. A plant (a paper) can be dry. It never dies."""
import datetime as dt

from fsrs import Card, Rating, Scheduler

from . import cards, db, game

RATINGS = {"again": Rating.Again, "hard": Rating.Hard, "good": Rating.Good, "easy": Rating.Easy}
KIND_LABEL = {"quiz": "Quiz question", "glossary": "Word", "idea": "Main idea"}
DRY_AFTER_DAYS = 3  # a plant looks dry when an item is 3 days or more over its date
MAX_DUE = 50

# Intervals in whole days: a student reviews one time each day. A wrong answer ("Again") comes back the next day.
scheduler = Scheduler(learning_steps=(), relearning_steps=(), enable_fuzzing=False)


class ReviewError(Exception):
    """Wrong request. The message is for the user."""


def _dt(ts: float) -> dt.datetime:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc)


def rate(item: dict, rating: str, now: float) -> dict:
    """The new state of an item after an answer. FSRS decides the next date. A rating that is not known gives an error."""
    if rating not in RATINGS:
        raise ReviewError("The rating must be again, hard, good or easy.")
    card = Card.from_json(item["fsrs_json"]) if item.get("fsrs_json") else Card(due=_dt(item["created_at"]))
    was_review = card.state.value == 2
    new, _ = scheduler.review_card(card, RATINGS[rating], review_datetime=_dt(now))
    return {
        "due": new.due.timestamp(), "stability": new.stability, "difficulty": new.difficulty, "last_review": now,
        "reps": (item.get("reps") or 0) + 1, "lapses": (item.get("lapses") or 0) + (1 if rating == "again" and was_review else 0),
        "fsrs_json": new.to_json(),
    }


def due_date(item: dict) -> str:
    return game.local_date(item["due"] if item.get("due") else item["created_at"])


def plant_state(due_dates: list[str], today: str) -> str:
    """fresh: nothing is due. ok: something is due, but not for long. dry: something is 3 days or more over its date.
    A plant never dies. A paper with no review item is fresh."""
    t = dt.date.fromisoformat(today)
    late = [(t - dt.date.fromisoformat(d)).days for d in due_dates if d <= today]
    if not late:
        return "fresh"
    return "dry" if max(late) >= DRY_AFTER_DAYS else "ok"


# ------------------------------------------------------------------ the items
def idea_item(pid: str, title: str, card: dict | None) -> dict | None:
    """The main idea of a card: its checked problem and method. The quote is the first quote that the server verified.
    A card without a verified quote gives no item."""
    fields = (card or {}).get("fields") or {}
    parts, quote, page = [], "", 0
    for name in ("problem", "method", "result"):
        f = fields.get(name) or {}
        if f.get("status") not in ("verified", "check") or not f.get("answer"):
            continue
        ev = next((e for e in f.get("evidence", []) if e.get("verified")), None)
        if ev:
            if not quote:
                quote, page = ev["quote"], ev["page"]
            if name != "result":
                parts.append(f["answer"])
    if not quote or not parts:
        return None
    return {"question": f"What is the main idea of \"{title}\"? What problem does it solve, and how?", "answer": " ".join(parts), "quote": quote, "page": page}


def sync_cards() -> int:
    """Make the item "main idea" for each card that has none. It runs when the student opens the review. No AI call."""
    made = 0
    have = {r["ref_id"] for r in db.review_list(kind="idea")}
    for p in db.list_papers():
        if p["status"] != "ready":
            continue
        entries = [("", db.get_card(p["id"]), p["title"])] + [(x["id"], x["card"], p["title"] + (f" ({x['focus']})" if x["focus"] else "")) for x in db.list_extra(p["id"]) if x["card"]]
        for card_id, card, title in entries:
            ref = f"{p['id']}:{card_id}"
            item = idea_item(p["id"], title, card) if ref not in have else None
            if item:
                db.review_add("idea", p["id"], item["question"], item["answer"], item["quote"], item["page"], card_id, ref)
                made += 1
    return made


def public(item: dict, titles: dict[str, str]) -> dict:
    kind = item["kind"]
    question = f"What does \"{item['question']}\" mean?" if kind == "glossary" else item["question"]
    label = KIND_LABEL[kind] if kind != "glossary" else ("From the paper" if item["quote"] else "AI explanation")
    return {"id": item["id"], "kind": kind, "kind_label": KIND_LABEL[kind], "label": label, "paper_id": item["paper_id"], "title": titles.get(item["paper_id"], ""),
            "question": question, "answer": item["answer"], "quote": item["quote"], "page": item["page"], "due": item["due"], "reps": item["reps"] or 0}


def titles() -> dict[str, str]:
    return {p["id"]: p["title"] for p in db.list_papers()}


def due_items(today: str, paper_id: str | None = None, limit: int = MAX_DUE) -> tuple[list[dict], int]:
    """Items with a date of today or earlier. The oldest first. Also the total number."""
    sync_cards()
    rows = [r for r in db.review_list() if due_date(r) <= today and (paper_id is None or r["paper_id"] == paper_id)]
    rows.sort(key=lambda r: (r["due"] or r["created_at"], r["id"]))
    t = titles()
    return [public(r, t) for r in rows[:limit]], len(rows)


def garden(today: str) -> dict:
    sync_cards()
    items = db.review_list()
    plants = []
    for p in db.list_papers():
        mine = [r for r in items if r["paper_id"] == p["id"]]
        dates = [due_date(r) for r in mine]
        plants.append({"paper_id": p["id"], "title": p["title"] or p["filename"], "items": len(mine), "due": sum(1 for d in dates if d <= today),
                       "state": plant_state(dates, today), "status": p["status"]})
    plants.sort(key=lambda x: x["title"].lower())
    return {"date": today, "due_total": sum(1 for r in items if due_date(r) <= today), "plants": plants}


def answer(item_id: str, rating: str, today: str, now: float) -> dict:
    """The student rates an item. FSRS sets the next date. The server gives points in main.py (see game.check_review)."""
    item = db.review_get(item_id)
    if not item:
        raise ReviewError("This item does not exist.")
    if due_date(item) > today:
        raise ReviewError("This item is not due yet. Come back on its day.")
    state = rate(item, rating, now)
    db.review_apply(item_id, state)
    days = (dt.date.fromisoformat(game.local_date(state["due"])) - dt.date.fromisoformat(today)).days
    return {"id": item_id, "rating": rating, "due": state["due"], "interval_days": max(0, days), "reps": state["reps"], "remaining": due_items(today)[1]}
