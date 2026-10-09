"""The PhD Expedition map (Sprint 06): six regions. Each region fills with color as the work is done.
The numbers come from data that the app already has. A region whose feature is not built yet shows 0% ("Not started").
No AI call. The tone is kind: a region at 0% gives a first step, never a blame."""
from . import db, game


def _count(table: str, where: str = "", args: tuple = ()) -> int:
    """The rows of a table that a later sprint makes. 0 while the table does not exist."""
    with db.conn() as c:
        if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
            return 0
        return c.execute(f"SELECT COUNT(*) AS n FROM {table}" + (f" WHERE {where}" if where else ""), args).fetchone()["n"]


def _pct(x: float) -> int:
    return max(0, min(100, round(100 * x)))


def question_peak() -> dict:
    p, subs = db.get_project(), db.list_sub_questions()
    percent = _pct(0.25 * bool(p["title"]) + 0.25 * bool(p["question"]) + 0.5 * min(len(subs), 3) / 3)
    todo = "Write your thesis title." if not p["title"] else "Write your research question." if not p["question"] else "Cut your question into 3 sub-questions." if len(subs) < 3 else ""
    return {"percent": percent, "target": "project", "first_step": todo or "Your question is clear. Keep it in view.",
            "detail": f"Title {'yes' if p['title'] else 'no'}, question {'yes' if p['question'] else 'no'}, {len(subs)} {'sub-question' if len(subs) == 1 else 'sub-questions'}."}


def literature_forest() -> dict:
    """For each sub-question: half for papers with a ready card (2 papers are enough), half for papers with a Feynman pass (1 is enough).
    With no sub-question: 5 ready cards and 3 Feynman passes fill the forest."""
    ready = {r["ref_id"].split(":")[0] for r in db.xp_events_of("card_ready")}
    passed = set(r["ref_id"] for r in db.xp_events_of("feynman_pass"))
    subs, tags = db.list_sub_questions(), db.all_tags()
    if subs:
        parts = []
        for s in subs:
            mine = {pid for pid, by_card in tags.items() if any(s["id"] in ids for ids in by_card.values())}
            parts.append(0.5 * min(len(mine & ready), 2) / 2 + 0.5 * min(len(mine & passed), 1))
        percent = _pct(sum(parts) / len(parts))
        weakest = min(range(len(subs)), key=lambda i: parts[i])
        step = f"Read a paper for SQ{weakest + 1}, tag it, and explain it in your own words." if percent < 100 else "Your sub-questions have papers. Keep reading."
    else:
        percent = _pct(0.5 * min(len(ready), 5) / 5 + 0.5 * min(len(passed), 3) / 3)
        step = "Add a paper and make a card with checked quotes." if not ready else "Explain a paper in your own words (Understand tab)."
    return {"percent": percent, "target": "cards", "first_step": step, "detail": f"{len(ready)} cards with checked quotes, {len(passed)} Feynman checks passed."}


def method_workshop() -> dict:
    n = _count("journal", "kind != 'experiment'")  # the research journal comes in a later sprint
    return {"percent": _pct(min(n, 10) / 10), "target": "today", "first_step": "The research journal comes in a later sprint. Then you can write your methods here." if n == 0 else "Keep writing your decisions in the journal.",
            "detail": f"{n} journal entries." if n else "Not available yet."}


def data_mines() -> dict:
    n = _count("journal", "kind = 'experiment'")
    return {"percent": _pct(min(n, 10) / 10), "target": "today", "first_step": "The research journal comes in a later sprint. Then you can log your experiments here." if n == 0 else "Log your next experiment.",
            "detail": f"{n} experiments." if n else "Not available yet."}


def writing_coast() -> dict:
    n = _count("lit_sections")  # the literature review builder comes in a later sprint
    return {"percent": _pct(min(n, 5) / 5), "target": "today", "first_step": "The literature review builder comes in a later sprint. Then you can write your first section here." if n == 0 else "Write the next section.",
            "detail": f"{n} sections written." if n else "Not available yet."}


def defense_castle() -> dict:
    return {"percent": 0, "target": "today", "first_step": "This is the end of the road. It opens when your thesis outline is ready. There is no hurry.", "detail": "Not available yet."}


REGIONS = [
    ("peak", "Question Peak", question_peak),
    ("forest", "Literature Forest", literature_forest),
    ("workshop", "Method Workshop", method_workshop),
    ("mines", "Data Mines", data_mines),
    ("coast", "Writing Coast", writing_coast),
    ("castle", "Defense Castle", defense_castle),
]


def build() -> dict:
    out = []
    for code, name, fn in REGIONS:
        r = fn()
        out.append({"code": code, "name": name, **r, "state": "done" if r["percent"] >= 100 else "growing" if r["percent"] > 0 else "not_started"})
    return {"regions": out, "total": round(sum(r["percent"] for r in out) / len(out))}
