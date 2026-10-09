"""The game (Sprint 05). All rules of the game are in this one file, so they are easy to change.

The golden rule: points come only from real research work that the server can verify.
- Only the server writes XP. No endpoint takes XP from the page. The server gives XP after it verified the action.
- One action (action + ref_id) gives XP one time only. The database refuses a second row.
- No guilt: a lost streak gives a kind message. Rest days are normal. There is no ranking, only your own past."""
import datetime as dt

from . import cards, db

# action -> XP. "focus_session" gives 1 XP for each 5 minutes, for a session of 20 minutes or more.
XP = {"card_ready": 10, "feynman_pass": 25, "quiz_correct": 5, "link_explained": 10, "win_written": 2, "review": 2}
MAX_REVIEW_XP_PER_DAY = 20
FOCUS_MIN_MINUTES, FOCUS_STEP_MINUTES = 20, 5
FEYNMAN_PASS_SCORE = 70
TOKENS_PER_WEEK = 2

ACTION_LABEL = {
    "card_ready": "A card with checked quotes", "feynman_pass": "A Feynman check passed", "quiz_correct": "A quiz answer that is correct",
    "link_explained": "A link explained with quotes", "focus_session": "A focus session", "win_written": "A win written", "review": "A review of an item",
    "quest": "A quest done", "boss": "A boss defeated",
}

# (name, XP needed, the conditions of the skill). A condition is (key, text, number needed).
# The features of a key that is None are not built yet: the level stays locked and says so.
LEVELS = [
    ("Explorer", 0, []),
    ("Reader", 100, [("cards", "cards with checked quotes", 5), ("feynman", "Feynman checks passed", 3)]),
    ("Critic", 250, [("critical", "critical reading checks", 10)]),
    ("Connector", 450, [("links", "links explained with quotes", 10), ("gaps", "gaps found", 1)]),
    ("Author", 700, [("sections", "literature review sections written", 1)]),
    ("Doctor", 1000, [("outline", "thesis outline complete and defense practice done", 1)]),
]

BADGES = {  # code: (name, how)
    "first_card": ("First card", "Your first card with checked quotes."),
    "first_feynman_pass": ("First Feynman pass", "You explained a paper and the check said: well done."),
    "streak_7": ("7-day streak", "7 days of real work in a row. Rest days do not break it."),
    "streak_30": ("30-day streak", "30 days of real work in a row."),
    "cards_100": ("100 cards", "100 cards with checked quotes."),
    "year_1": ("1 year", "One year since your first point."),
}


# ------------------------------------------------------------------ writing XP (only the server calls these)
def _tz_minutes() -> int:
    try:
        return int(db.get_setting("tz_minutes") or 0)
    except ValueError:
        return 0


def local_date(t: float) -> str:
    """The date of a moment in the time zone of the student. The page tells the server the offset (set_timezone)."""
    return (dt.datetime.fromtimestamp(t, dt.timezone.utc) + dt.timedelta(minutes=_tz_minutes())).date().isoformat()


def set_timezone(minutes) -> None:
    try:
        m = int(minutes)
    except (TypeError, ValueError):
        return
    if -14 * 60 <= m <= 14 * 60 and str(m) != db.get_setting("tz_minutes"):
        db.set_setting("tz_minutes", str(m))


def award(action: str, ref_id: str, xp: int | None = None) -> bool:
    """Give XP for a verified action. True if this is new. The same (action, ref_id) never gives XP twice."""
    if action not in ACTION_LABEL:
        raise ValueError("unknown action")
    points = XP.get(action, 0) if xp is None else xp
    if points <= 0 or not ref_id:
        return False
    now = db.now()
    new = db.xp_add(action, str(ref_id), points, now, local_date(now))
    if new:
        refresh()
    return new


def card_is_ready(card: dict | None) -> bool:
    """A card is ready when each main field has a quote that the server found in the PDF. A hidden claim gives no points."""
    fields = (card or {}).get("fields") or {}
    return all(
        (fields.get(n) or {}).get("status") in ("verified", "check") and any(e.get("verified") for e in (fields.get(n) or {}).get("evidence", []))
        for n in cards.PAPER_FIELDS
    )


def check_card(pid: str, card_id: str = "") -> bool:
    card = db.get_card(pid) if not card_id else (db.get_extra(pid, card_id) or {}).get("card")
    return card_is_ready(card) and award("card_ready", f"{pid}:{card_id}")


def check_feynman(pid: str, score: int) -> bool:
    """One pass for each paper. Many attempts on the same paper give XP one time."""
    return score >= FEYNMAN_PASS_SCORE and award("feynman_pass", pid)


def check_link(a: str, b: str, evidence: list[dict]) -> bool:
    """The link has a verified quote in both PDFs."""
    ok = {e.get("paper_id") for e in evidence if e.get("verified")}
    return {a, b} <= ok and award("link_explained", ":".join(sorted([a, b])))


def check_focus(session: dict) -> bool:
    if session["minutes"] < FOCUS_MIN_MINUTES:
        return False
    return award("focus_session", session["id"], session["minutes"] // FOCUS_STEP_MINUTES)


def check_review(item_id: str, reps: int) -> bool:
    """2 points for each review, at most 20 points each day. The same answer number of the same item gives points one time."""
    today = local_date(db.now())
    if db.xp_by_day("review").get(today, 0) + XP["review"] > MAX_REVIEW_XP_PER_DAY:
        return False
    return award("review", f"{item_id}:{reps}")


def check_win(date: str) -> bool:
    return award("win_written", date)


# ------------------------------------------------------------------ the numbers of the student
def counts() -> dict:
    """What the student has done. None means: the feature does not exist yet."""
    c = db.xp_counts()
    return {"cards": c.get("card_ready", 0), "feynman": c.get("feynman_pass", 0), "links": c.get("link_explained", 0),
            "critical": None, "gaps": None, "sections": db.sections_written(300), "outline": None}


def level_info(xp: int, have: dict) -> dict:
    reached = 0
    for i, (_, need_xp, conds) in enumerate(LEVELS):
        if xp >= need_xp and all(have.get(k) is not None and have[k] >= n for k, _, n in conds):
            reached = i
        else:
            break
    nxt = None
    if reached + 1 < len(LEVELS):
        name, need_xp, conds = LEVELS[reached + 1]
        nxt = {"name": name, "xp_needed": max(0, need_xp - xp), "xp_total": need_xp,
               "conditions": [{"text": text, "have": have.get(k) or 0, "need": n, "available": have.get(k) is not None} for k, text, n in conds]}
    return {"index": reached, "name": LEVELS[reached][0], "floor": LEVELS[reached][1], "next": nxt, "names": [name for name, _, _ in LEVELS]}


# ------------------------------------------------------------------ the kind streak
def streak(days_with_xp: set[str], today: str, weekend_off: bool = True) -> dict:
    """A day counts if it has at least one XP event. A day without XP uses a rest token (2 each week). With no token, the streak ends.
    With weekend_off, Saturday and Sunday need no XP and use no token. Today is not judged before it ends."""
    if not days_with_xp:
        return {"current": 0, "best": 0, "tokens_left": TOKENS_PER_WEEK, "today_done": False, "rest_days": []}
    d, end = dt.date.fromisoformat(min(days_with_xp)), dt.date.fromisoformat(today)
    cur = best = 0
    used: dict[tuple, int] = {}
    rest_days = []
    while d <= end:
        iso = d.isoformat()
        week = d.isocalendar()[:2]
        if iso in days_with_xp:
            cur += 1
        elif d == end:
            pass  # today is not over: the streak holds
        elif weekend_off and d.weekday() >= 5:
            pass
        elif cur > 0 and used.get(week, 0) < TOKENS_PER_WEEK:
            used[week] = used.get(week, 0) + 1
            cur += 1
            rest_days.append(iso)
        else:
            cur = 0
        best = max(best, cur)
        d += dt.timedelta(days=1)
    wk = end.isocalendar()[:2]
    return {"current": cur, "best": best, "tokens_left": TOKENS_PER_WEEK - used.get(wk, 0), "today_done": today in days_with_xp, "rest_days": rest_days[-14:]}


def streak_message(s: dict, had_before: bool) -> str:
    if s["current"] == 0 and had_before:
        return "Welcome back. Your knowledge is still here."
    if s["current"] == 0:
        return "Your first point starts your streak."
    if s["today_done"]:
        return "Good work today. Rest is part of the work."
    return f"{s['current']} {'day' if s['current'] == 1 else 'days'} in a row. A rest day is fine: you have {s['tokens_left']} rest {'token' if s['tokens_left'] == 1 else 'tokens'} this week."


# ------------------------------------------------------------------ badges, records, own rewards
def refresh() -> None:
    """Give new badges and mark earned rewards. The server calls this after each XP event."""
    c = db.xp_counts()
    xp = db.xp_total()
    have = counts()
    today = local_date(db.now())
    days = db.xp_days()
    s = streak(days, today, weekend_off=weekend_off())
    first = dt.date.fromisoformat(min(days)) if days else None
    earned = {
        "first_card": c.get("card_ready", 0) >= 1, "first_feynman_pass": c.get("feynman_pass", 0) >= 1,
        "streak_7": s["best"] >= 7, "streak_30": s["best"] >= 30, "cards_100": c.get("card_ready", 0) >= 100,
        "year_1": bool(first and (dt.date.fromisoformat(today) - first).days >= 365),
    }
    for code, ok in earned.items():
        if ok:
            db.badge_add(code, db.now())
    lvl = level_info(xp, have)["index"]
    for r in db.rewards_list():
        if not r["earned_at"] and condition_met(r["condition"], lvl, xp, s["best"], have["cards"]):
            db.reward_earn(r["id"], db.now())
    try:  # quests and bosses check their conditions after each point event
        from . import quests
        quests.check_bosses()
        quests.check_all()
    except Exception:
        import logging
        logging.getLogger("research_pal").exception("Quest check failed")


def badge_info(code: str):
    """(name, how) of a badge. A boss badge has the title of the paper in its name."""
    if code in BADGES:
        return BADGES[code]
    if code.startswith("boss:"):
        p = db.get_paper(code[5:])
        return (f"Boss defeated: {p['title'] if p else 'a paper'}", "You answered the quiz and passed the Feynman check, both with 80% or more.")
    return None


def parse_condition(text: str):
    """"level:3", "xp:500", "streak:7" or "cards:20". Returns (kind, number) or None."""
    kind, _, num = str(text or "").strip().lower().partition(":")
    if kind in ("level", "xp", "streak", "cards") and num.isdigit() and 0 < int(num) <= 100000:
        return kind, int(num)
    return None


def condition_met(text: str, level: int, xp: int, best_streak: int, cards_n: int) -> bool:
    p = parse_condition(text)
    if not p:
        return False
    kind, n = p
    return {"level": level + 1, "xp": xp, "streak": best_streak, "cards": cards_n}[kind] >= n  # "level:3" means Critic: the third level


def weekend_off() -> bool:
    return db.get_setting("weekend_off", "1") != "0"


def _sum_between(rows: dict[str, int], start: dt.date, end: dt.date) -> int:
    return sum(v for k, v in rows.items() if start <= dt.date.fromisoformat(k) <= end)


def records(today: str) -> dict:
    """This week against last week, this month against last month. The student is compared with his or her own past only."""
    t = dt.date.fromisoformat(today)
    wk = t - dt.timedelta(days=t.weekday())
    m1 = t.replace(day=1)
    m0 = (m1 - dt.timedelta(days=1)).replace(day=1)
    series = {"xp": db.xp_by_day(), "cards": db.xp_by_day("card_ready", count=True), "focus_minutes": db.focus_minutes_by_day()}
    out = {}
    for name, rows in series.items():
        out[name] = {
            "this_week": _sum_between(rows, wk, t), "last_week": _sum_between(rows, wk - dt.timedelta(days=7), wk - dt.timedelta(days=1)),
            "this_month": _sum_between(rows, m1, t), "last_month": _sum_between(rows, m0, m1 - dt.timedelta(days=1)),
        }
    return out


def summary(today: str) -> dict:
    xp = db.xp_total()
    have = counts()
    days = db.xp_days()
    s = streak(days, today, weekend_off=weekend_off())
    info = level_info(xp, have)
    return {
        "date": today, "xp": xp, "level": info, "have": have,
        "streak": {**s, "weekend_off": weekend_off(), "message": streak_message(s, bool(days))},
        "badges": [{**b, "name": badge_info(b["code"])[0], "how": badge_info(b["code"])[1]} for b in db.badges_list() if badge_info(b["code"])],
        "badges_missing": [{"code": c, "name": n, "how": h} for c, (n, h) in BADGES.items() if c not in {b["code"] for b in db.badges_list()}],
        "records": records(today),
        "rewards": db.rewards_list(),
        "recent": [{**e, "label": ACTION_LABEL.get(e["action"], e["action"])} for e in db.xp_recent(10)],
    }
