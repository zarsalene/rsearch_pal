"""The Semester Simulator. A turn-based simulation of 12 weeks of research.

Each week the student has 5 action points. The student chooses how to spend them: read, test, write, meet the supervisor, rest.
Energy, morale and trust change. Random events arrive at the end of a week, and each one asks for a choice with a risk.
The simulation runs on the server. The page sends only the choices. The random numbers come from a seed that the page never sees,
so a bad result cannot be rolled again, and a good result cannot be forged.

It is a real simulation of the real student:
- The knowledge at the start comes from the real work: the papers that the student mastered, explained or read, and the links that the student found.
- A reviewer asks about a real paper from the library of the student. The odds depend on the real rank of the paper.
- The report at the end names the real papers that the student did not know, and it says what to do next in the real app.
The simulation gives no XP. XP is only for real work. The simulation shows what the real work is worth.

The rules are in this file, and the balance is tested: tests/test_sim.py plays thousands of semesters with simple policies."""
import random
import threading
from collections import Counter

from . import db, game

WEEKS = 12
AP_WEEK = 5
AP_TIRED = 2           # the action points of a week after an exhausted week
MILESTONES = {4: "Literature review draft", 8: "Method and tests check", 12: "Final report"}
WEIGHTS = {"review": 0.25, "method": 0.15, "experiments": 0.25, "writing": 0.35}  # what each chapter is worth in the final progress
CHAPTER_NAMES = {"review": "Literature review", "method": "Method", "experiments": "Tests", "writing": "Writing"}
GRADES = [("S", 85), ("A", 70), ("B", 55), ("C", 40), ("D", 0)]
EVENT_CHANCE = 0.7
ODDS = {0: 0.2, 1: 0.4, 2: 0.65, 3: 0.9}  # a reviewer asks about a paper: the chance to answer well, for each real rank
RANK_NAMES = ["seen", "read", "explained", "mastered"]

ACTIONS = {
    "read":       {"label": "Read papers", "ap": 1, "energy": -8, "text": "Literature review grows. You learn."},
    "study":      {"label": "Study one paper", "ap": 1, "energy": -6, "text": "Prepare for one real paper. A reviewer may ask about it."},
    "experiment": {"label": "Run a test", "ap": 2, "energy": -15, "text": "Tests and method grow. It can fail."},
    "write":      {"label": "Write", "ap": 2, "energy": -12, "text": "Writing grows. You cannot write more than you know."},
    "meet":       {"label": "Meet your supervisor", "ap": 1, "energy": -3, "text": "Trust and morale grow. You learn what comes this week."},
    "network":    {"label": "Talk to researchers", "ap": 1, "energy": -6, "text": "A chance for a good tip."},
    "rest":       {"label": "Rest", "ap": 1, "energy": 22, "text": "Energy and morale come back."},
}
_lock = threading.Lock()


class SimError(Exception):
    """A request that the simulation cannot do. The message is for the user."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _clamp(v, lo=0, hi=100):
    return max(lo, min(hi, v))


def _eff(energy: int) -> float:
    """A tired student does less in each action. This makes rest worth an action point."""
    return 1.0 if energy >= 30 else 0.6 if energy >= 10 else 0.3


def _rng(s: dict, tag: str) -> random.Random:
    """One random number stream for each step. The same seed and the same choices always give the same semester."""
    s["step"] += 1
    return random.Random(f"{s['seed']}:{s['week']}:{s['step']}:{tag}")


# ---------- the real student ----------
def real_snapshot() -> dict:
    """What the student really did in the app. The simulation starts from it."""
    coll = game.collection()
    found = sum(1 for d in game.explained_links().values() if d.get("status") == "verified")
    n = Counter(c["rank"] for c in coll)
    knowledge = min(60, 10 + 8 * n[3] + 4 * n[2] + 2 * n[1] + 3 * found)
    papers = [{"id": c["id"], "title": c["title"][:120], "rank": c["rank"]} for c in coll][:12]
    return {"papers": papers, "links": found, "knowledge": knowledge, "mastered": n[3], "explained": n[2], "read": n[1]}


def new_state(seed: int, real: dict | None = None) -> dict:
    real = real or {"papers": [], "links": 0, "knowledge": 10, "mastered": 0, "explained": 0, "read": 0}
    s = {
        "seed": seed, "step": 0, "week": 1, "ap": AP_WEEK, "energy": 70, "morale": 70, "trust": 50, "knowledge": real["knowledge"],
        "chapters": {c: 0 for c in WEIGHTS}, "papers": [dict(p, prepared=False) for p in real["papers"]], "links": real["links"],
        "real": {k: real[k] for k in ("knowledge", "mastered", "explained", "read", "links")},
        "armed": False, "coffee_week": 0, "scouted": False, "ap_penalty": 0, "exhausted": False,
        "event": None, "coming": None, "misses": [], "milestones": {}, "log": [], "report": None, "status": "active",
    }
    s["coming"] = _draw(s)
    return s


def progress(s: dict) -> int:
    return round(sum(s["chapters"][c] * w for c, w in WEIGHTS.items()))


def grade_for(p: int, burnout: bool = False) -> str:
    g = next(name for name, floor in GRADES if p >= floor)
    return "C" if burnout and g in ("S", "A", "B") else g  # a burnout ends the semester early: the grade is not better than C


def _say(s: dict, text: str, kind: str = "action") -> None:
    s["log"].append({"week": s["week"], "kind": kind, "text": text})
    del s["log"][:-40]


# ---------- the events ----------
def _pick_paper(s: dict, rng: random.Random) -> dict:
    if s["papers"]:
        return dict(rng.choice(s["papers"]))
    return {"id": "", "title": "a key paper of your field", "rank": 1, "prepared": False}


def _draw(s: dict) -> dict | None:
    """The event that comes at the end of this week. The student can learn it early (Meet your supervisor)."""
    rng = random.Random(f"{s['seed']}:{s['week']}:draw")
    if rng.random() > EVENT_CHANCE:
        return None
    c = s["chapters"]
    weights = {
        "reviewer": 3 if (c["writing"] >= 15 or c["review"] >= 30) else 0,
        "crash": 3 if c["experiments"] >= 8 else 0,
        "praise": 2 if s["trust"] >= 40 else 0,
        "overlap": 2,
        "illness": 1 + (3 if s["energy"] < 30 else 0),  # a tired student gets ill more often: a push to rest
        "helpme": 2,
        "admin": 2,
        "idea": 2 if s["knowledge"] >= 20 else 0,
    }
    kinds = [k for k, w in weights.items() if w > 0]
    if not kinds:
        return None
    pick = rng.choices(kinds, [weights[k] for k in kinds])[0]
    ev = {"id": pick}
    if pick == "reviewer":
        ev["paper"] = _pick_paper(s, rng)
    return ev


def _odds(s: dict, paper: dict) -> float:
    """The chance to answer a reviewer about a real paper. It depends on the real rank of the paper, and on what the student did in the simulation."""
    p = ODDS[paper["rank"]] + s["knowledge"] * 0.002
    prepared = next((x["prepared"] for x in s["papers"] if x["id"] == paper["id"] and paper["id"]), False)
    if prepared:
        p = max(p, 0.75)
    return round(min(0.95, p), 2)


def _odds_word(p: float) -> str:
    return "Good odds" if p >= 0.7 else "Fair odds" if p >= 0.45 else "Poor odds"


def _roll(s: dict, p: float, tag: str) -> bool:
    """A roll with a chance p. A Second chance rolls again one time after a fail."""
    ok = _rng(s, tag).random() < p
    if not ok and s["armed"]:
        s["armed"] = False
        _say(s, "Your Second chance lets you try again.", "boost")
        ok = _rng(s, tag + "2").random() < p
    return ok


def _event_view(s: dict) -> dict | None:
    ev = s["event"]
    if not ev:
        return None
    k = ev["id"]
    if k == "reviewer":
        paper = ev["paper"]
        odds = _odds(s, paper)
        real = paper["id"] != ""
        return {"id": k, "title": "Reviewer 2 writes to you",
                "text": f"The reviewer asks about \"{paper['title']}\". " + (f"In the app, this paper is {RANK_NAMES[paper['rank']]}." if real else ""),
                "paper": paper,
                "choices": [{"id": "answer", "label": "Answer from your notes", "risk": "risky", "hint": _odds_word(odds)},
                            {"id": "ask", "label": "Ask your supervisor for help", "risk": "safe", "hint": "Trust -3. A small gain."},
                            {"id": "delay", "label": "Ask for more time", "risk": "safe", "hint": "Morale -2. One action point less next week."}]}
    views = {
        "crash": ("Your test crashed", "The server stopped in the middle of a run.",
                  [("debug", "Debug all night", "risky", "Energy -15. Tests +6."), ("restart", "Start again next week", "safe", "One action point less next week."), ("mate", "Ask a lab-mate", "risky", "Trust -2. It may work.")]),
        "praise": ("Your supervisor likes your work", "A short, kind email arrives.",
                   [("thanks", "Say thank you", "safe", "Morale +6."), ("freedom", "Ask for more freedom", "risky", "Trust may grow, or fall.")]),
        "overlap": ("A paper looks like your work", "A new paper has a similar idea.",
                    [("read", "Read it now", "safe", "Energy -6. You learn."), ("ignore", "Ignore it", "risky", "It may hurt your morale.")]),
        "illness": ("You feel sick", "Your body asks for a break.",
                    [("rest", "Rest fully", "safe", "Energy +10. One action point less next week."), ("push", "Push through", "risky", "Energy -15. Morale -4.")]),
        "helpme": ("A lab-mate needs help", "A friend is stuck with a problem.",
                   [("help", "Help your friend", "safe", "One action point less next week. Trust and knowledge grow."), ("no", "Say no", "safe", "Morale +2. Trust -2.")]),
        "admin": ("Forms and meetings", "The department wants a form today.",
                  [("now", "Do it now", "safe", "Energy -5."), ("later", "Do it later", "risky", "You may forget it.")]),
        "idea": ("A new idea", "You find an idea in the shower.",
                 [("note", "Write it down", "safe", "Method +8."), ("test", "Test it at once", "risky", "Tests +8. Energy -10. It may fail.")]),
    }
    title, text, choices = views[k]
    return {"id": k, "title": title, "text": text, "paper": None, "choices": [{"id": c, "label": label, "risk": risk, "hint": hint} for c, label, risk, hint in choices]}


def _resolve(s: dict, choice: str) -> str:
    """Apply the choice of the student to the event that waits. Returns the text for the log."""
    ev, k, c = s["event"], s["event"]["id"], s["chapters"]
    valid = {x["id"] for x in _event_view(s)["choices"]}
    if choice not in valid:
        raise SimError("Choose one of the answers.", 400)
    if k == "reviewer":
        paper = ev["paper"]
        if choice == "answer":
            if _roll(s, _odds(s, paper), "reviewer"):
                c["writing"] = _clamp(c["writing"] + 8)
                s["trust"] = _clamp(s["trust"] + 4)
                s["morale"] = _clamp(s["morale"] + 4)
                return f"You answer well about \"{paper['title']}\". The reviewer is happy. Writing +8."
            c["writing"] = _clamp(c["writing"] - 4)
            s["morale"] = _clamp(s["morale"] - 8)
            s["trust"] = _clamp(s["trust"] - 2)
            if paper["id"] and all(m["id"] != paper["id"] for m in s["misses"]):
                s["misses"].append({"id": paper["id"], "title": paper["title"], "rank": paper["rank"]})
            return f"You cannot answer about \"{paper['title']}\". Writing -4. Morale -8."
        if choice == "ask":
            s["trust"] = _clamp(s["trust"] - 3)
            s["energy"] = _clamp(s["energy"] - 2)
            c["writing"] = _clamp(c["writing"] + 3)
            if paper["id"] and paper["rank"] < 2 and all(m["id"] != paper["id"] for m in s["misses"]):
                s["misses"].append({"id": paper["id"], "title": paper["title"], "rank": paper["rank"]})
            return "Your supervisor helps you. Writing +3. Trust -3."
        s["morale"] = _clamp(s["morale"] - 2)
        s["ap_penalty"] += 1
        return "The reviewer waits. Morale -2."
    if k == "crash":
        if choice == "debug":
            s["energy"] = _clamp(s["energy"] - 15)
            c["experiments"] = _clamp(c["experiments"] + 6)
            s["morale"] = _clamp(s["morale"] - 3)
            return "You fix it at night. Tests +6. Energy -15."
        if choice == "restart":
            s["ap_penalty"] += 1
            return "You start again next week. One action point less."
        s["trust"] = _clamp(s["trust"] - 2)
        if _roll(s, 0.6, "mate"):
            c["experiments"] = _clamp(c["experiments"] + 4)
            return "Your lab-mate finds the bug. Tests +4."
        return "Your lab-mate cannot find the bug. Trust -2."
    if k == "praise":
        if choice == "thanks":
            s["morale"] = _clamp(s["morale"] + 6)
            return "You feel good. Morale +6."
        if _roll(s, 0.5, "freedom"):
            s["trust"] = _clamp(s["trust"] + 10)
            return "Your supervisor agrees. Trust +10."
        s["trust"] = _clamp(s["trust"] - 3)
        return "Your supervisor says no. Trust -3."
    if k == "overlap":
        if choice == "read":
            s["energy"] = _clamp(s["energy"] - 6)
            s["knowledge"] += 5
            extra = 4 if s["links"] > 0 else 0  # a student who found links in the real app sees the link at once
            c["review"] = _clamp(c["review"] + extra)
            return "You read the paper. Knowledge +5." + (f" You see how it links to your papers. Review +{extra}." if extra else "")
        if _roll(s, 0.6, "ignore"):
            return "The paper is not a problem. Nothing happens."
        s["morale"] = _clamp(s["morale"] - 6)
        return "You worry about the paper. Morale -6."
    if k == "illness":
        if choice == "rest":
            s["energy"] = _clamp(s["energy"] + 10)
            s["ap_penalty"] += 1
            return "You rest. Energy +10. One action point less next week."
        s["energy"] = _clamp(s["energy"] - 15)
        s["morale"] = _clamp(s["morale"] - 4)
        return "You push through. Energy -15. Morale -4."
    if k == "helpme":
        if choice == "help":
            s["ap_penalty"] += 1
            s["trust"] = _clamp(s["trust"] + 5)
            s["knowledge"] += 3
            return "You help your friend. Trust +5. Knowledge +3."
        s["morale"] = _clamp(s["morale"] + 2)
        s["trust"] = _clamp(s["trust"] - 2)
        return "You say no. Morale +2. Trust -2."
    if k == "admin":
        if choice == "now":
            s["energy"] = _clamp(s["energy"] - 5)
            return "You finish the form. Energy -5."
        if _roll(s, 0.5, "admin"):
            return "You do it later, and it is fine."
        s["trust"] = _clamp(s["trust"] - 4)
        return "You forget the form. Trust -4."
    if k == "idea":
        if choice == "note":
            c["method"] = _clamp(c["method"] + 8)
            return "You write the idea down. Method +8."
        s["energy"] = _clamp(s["energy"] - 10)
        if _roll(s, 0.7, "idea"):
            c["experiments"] = _clamp(c["experiments"] + 8)
            return "The idea works. Tests +8. Energy -10."
        s["morale"] = _clamp(s["morale"] - 4)
        return "The idea does not work. Energy -10. Morale -4."
    raise SimError("Unknown event.", 400)


# ---------- one action ----------
def can(s: dict, action: str) -> str:
    """"" when the action is possible. Else the reason, for the student."""
    if s["status"] != "active":
        return "The semester is over."
    if s["event"]:
        return "Answer the event first."
    if action == "study" and not s["papers"]:
        return "Add a paper in the library first."
    if s["ap"] < ACTIONS[action]["ap"]:
        return "Not enough action points."
    return ""


def act(s: dict, action: str, arg: str = "") -> str:
    if action not in ACTIONS:
        raise SimError("Unknown action.", 400)
    why = can(s, action)
    if why:
        raise SimError(why, 409)
    a, c = ACTIONS[action], s["chapters"]
    eff = _eff(s["energy"])
    if action == "study":
        paper = next((p for p in s["papers"] if p["id"] == arg), None)
        if not paper:
            raise SimError("Choose one of your papers.", 400)
        paper["prepared"] = True
        s["knowledge"] += 2
        c["review"] = _clamp(c["review"] + round(3 * eff))
        text = f"You study \"{paper['title']}\". A reviewer cannot surprise you with it."
    elif action == "read":
        gain = round((3 + s["knowledge"] / 7) * eff)
        c["review"] = _clamp(c["review"] + gain)
        s["knowledge"] += 2
        text = f"You read papers. Literature review +{gain}. Knowledge +2."
    elif action == "experiment":
        p = _clamp(0.30 + s["knowledge"] * 0.006 + (s["morale"] - 50) * 0.002 + (0.08 if s["trust"] >= 70 else 0), 0.15, 0.9)
        if _roll(s, p, "experiment"):
            e, m = round(11 * eff), round(4 * eff)
            c["experiments"] = _clamp(c["experiments"] + e)
            c["method"] = _clamp(c["method"] + m)
            s["morale"] = _clamp(s["morale"] + 3)
            text = f"The test works. Tests +{e}. Method +{m}."
        else:
            c["experiments"] = _clamp(c["experiments"] + 3)
            s["morale"] = _clamp(s["morale"] - 5)
            s["knowledge"] += 1
            text = "The test fails. You learn from it. Morale -5."
    elif action == "write":
        cap = min(100, 20 + 0.6 * c["review"] + 0.2 * c["method"] + 0.2 * c["experiments"])  # you cannot write what you did not read or test
        want = round(8 * eff) + (2 if s["morale"] >= 70 else 0)
        new = min(c["writing"] + want, round(cap))
        got = max(0, new - c["writing"])
        c["writing"] = max(c["writing"], new)
        text = f"You write. Writing +{got}." + (" You cannot write more than you know. Read or test first." if got < want * 0.6 else "")
    elif action == "meet":
        s["trust"] = _clamp(s["trust"] + 8)
        s["morale"] = _clamp(s["morale"] + 5)
        s["scouted"] = True
        text = "Your supervisor listens. Trust +8. Morale +5. You know what comes this week."
    elif action == "network":
        if _rng(s, "network").random() < 0.35:
            s["knowledge"] += 5
            s["trust"] = _clamp(s["trust"] + 3)
            text = "A researcher shares a good tip. Knowledge +5. Trust +3."
        else:
            s["morale"] = _clamp(s["morale"] + 2)
            text = "You have a nice talk. Morale +2."
    else:  # rest
        s["morale"] = _clamp(s["morale"] + 4)
        text = "You rest. Energy +22. Morale +4."
    s["energy"] = _clamp(s["energy"] + a["energy"])
    s["ap"] -= a["ap"]
    _say(s, text)
    return text


def _take(item: str) -> None:
    try:
        game.use_boost(item)  # the server takes the boost from the inventory
    except game.GameError as e:
        raise SimError(str(e), e.status)


def use_boost(s: dict, item: str) -> str:
    """Coffee gives energy one time in a week. A Second chance waits for the next failed roll. The server takes the boost from the inventory."""
    if s["status"] != "active" or s["event"]:
        raise SimError("You cannot use a boost now.", 409)
    if item == "coffee":
        if s["coffee_week"] == s["week"]:
            raise SimError("One coffee for each week is enough.", 409)
        _take("coffee")
        s["coffee_week"] = s["week"]
        s["energy"] = _clamp(s["energy"] + 25)
        text = "You drink a coffee. Energy +25."
    elif item == "second_chance":
        if s["armed"]:
            raise SimError("A Second chance is ready already.", 409)
        _take("second_chance")
        s["armed"] = True
        text = "Your Second chance is ready. It works for the next failed roll."
    else:
        raise SimError("Unknown boost.", 400)
    _say(s, text, "boost")
    return text


# ---------- the end of a week ----------
def end_week(s: dict) -> None:
    """Close the week. An event may arrive. The student answers it, and then the next week starts."""
    if s["status"] != "active":
        raise SimError("The semester is over.", 409)
    if s["event"]:
        raise SimError("Answer the event first.", 409)
    if s["coming"]:
        s["event"], s["coming"] = s["coming"], None
        _say(s, _event_view(s)["title"] + ".", "event")
        return
    _advance(s)


def choose(s: dict, choice: str) -> str:
    if s["status"] != "active" or not s["event"]:
        raise SimError("There is no event now.", 409)
    text = _resolve(s, choice)
    _say(s, text, "event")
    s["event"] = None
    _advance(s)
    return text


def _milestone(s: dict) -> None:
    w, c = s["week"], s["chapters"]
    if w not in MILESTONES:
        return
    ok = {4: c["review"] >= 35, 8: c["experiments"] >= 40 and c["method"] >= 25, 12: True}[w]
    s["milestones"][str(w)] = ok
    if w == 12:
        return
    if ok:
        s["trust"], s["morale"] = _clamp(s["trust"] + 6), _clamp(s["morale"] + 6)
        _say(s, f"{MILESTONES[w]}: your supervisor is happy. Trust +6. Morale +6.", "week")
    else:
        s["trust"], s["morale"] = _clamp(s["trust"] - 6), _clamp(s["morale"] - 4)
        _say(s, f"{MILESTONES[w]}: your supervisor is worried. Trust -6. Morale -4.", "week")


def _advance(s: dict) -> None:
    """The weekly step: sleep, the mood, the milestone, the next week."""
    s["energy"] = _clamp(s["energy"] + 3 * s["ap"])  # the action points that you did not use are quiet time
    s["exhausted"] = s["energy"] <= 0
    if s["energy"] < 20:
        s["morale"] = _clamp(s["morale"] - 4)
    s["morale"] = _clamp(s["morale"] - 2)
    _milestone(s)
    if s["morale"] <= 0:
        _finish(s, burnout=True)
        return
    if s["week"] >= WEEKS:
        _finish(s)
        return
    if s["exhausted"]:
        s["energy"], s["morale"] = 35, _clamp(s["morale"] - 6)
        _say(s, "You are exhausted. You have fewer action points this week. Rest more.", "week")
    else:
        s["energy"] = _clamp(s["energy"] + 8)
    s["ap"] = max(AP_TIRED, AP_WEEK - s["ap_penalty"]) if not s["exhausted"] else AP_TIRED
    s["ap_penalty"], s["scouted"], s["week"] = 0, False, s["week"] + 1
    s["coming"] = _draw(s)


def _finish(s: dict, burnout: bool = False) -> None:
    s["status"] = "burnout" if burnout else "done"
    p = progress(s)
    c = s["chapters"]
    weakest = min(c, key=lambda k: c[k])
    tips = {
        "review": "Read more in the first weeks. Reading makes all other work easier.",
        "method": "Run tests and think about the method before you write.",
        "experiments": "Plan more weeks for tests. Read first, then test.",
        "writing": "Start to write earlier. You can write only what you read and tested.",
    }
    weak = sorted(s["misses"], key=lambda m: m["rank"])[:3]
    next_steps = [f"Fight the boss of \"{m['title']}\" in the real app. A reviewer asked about it." for m in weak]
    if s["real"]["mastered"] == 0 and s["papers"]:
        next_steps.append("Master your first paper in the real app. A strong start gives knowledge in each semester.")
    s["report"] = {
        "progress": p, "grade": grade_for(p, burnout), "burnout": burnout, "weeks_done": s["week"] if burnout else WEEKS,
        "chapters": dict(c), "tip": tips[weakest], "weakest": weakest,
        "weak_spots": weak, "next_steps": next_steps,
        "real": s["real"],
        "text": ("Burnout ended the semester early. Your progress is safe. Rest, then try again." if burnout else
                 {"S": "A perfect semester. Your thesis is far ahead.", "A": "A strong semester. Your supervisor is proud.", "B": "A good semester. You are on the way.",
                  "C": "A hard semester. Plan more rest and more reading next time.", "D": "A slow semester. Plan your weeks, then try again."}[grade_for(p)]),
    }


# ---------- what the page sees ----------
def public(sid: str, s: dict, status: str, boosts: dict | None = None) -> dict:
    ev = _event_view(s)
    coming = None
    if s["scouted"] and s["coming"] and s["status"] == "active":  # the supervisor told the student
        t = _event_view({**s, "event": s["coming"]})
        coming = {"title": t["title"], "text": t["text"], "paper": t["paper"]}
    actions = []
    for k, a in ACTIONS.items():
        why = can(s, k)
        actions.append({"id": k, "label": a["label"], "ap": a["ap"], "energy": a["energy"], "text": a["text"], "enabled": not why, "why": why})
    return {
        "id": sid, "status": status, "week": s["week"], "weeks": WEEKS, "ap": s["ap"], "ap_max": AP_WEEK,
        "energy": s["energy"], "morale": s["morale"], "trust": s["trust"], "knowledge": s["knowledge"],
        "chapters": s["chapters"], "chapter_names": CHAPTER_NAMES, "progress": progress(s),
        "milestones": [{"week": w, "label": label, "done": str(w) in s["milestones"], "ok": s["milestones"].get(str(w))} for w, label in MILESTONES.items()],
        "event": ev, "coming": coming, "actions": actions,
        "papers": [{"id": p["id"], "title": p["title"], "rank": p["rank"], "rank_name": RANK_NAMES[p["rank"]], "prepared": p["prepared"]} for p in s["papers"]],
        "boosts": boosts or {}, "armed": s["armed"], "coffee_used": s["coffee_week"] == s["week"],
        "real": s["real"], "log": s["log"][-8:], "report": s["report"],
    }


# ---------- saved runs ----------
def _boosts() -> dict:
    return game.inventory()["boosts"]


def _view(sid: str) -> dict:
    row = db.sim_get(sid)
    if not row:
        raise SimError("Simulation not found.", 404)
    return public(sid, row["data"], row["status"], _boosts())


def _records() -> dict:
    done = [r for r in db.sim_list() if r["status"] in ("done", "burnout") and r["data"].get("report")]
    best = max((r["data"]["report"]["progress"] for r in done), default=0)
    last = done[-1]["data"]["report"] if done else None
    return {"runs": len(done), "best": best, "best_grade": grade_for(best) if done else "", "last": {"progress": last["progress"], "grade": last["grade"]} if last else None}


def current() -> dict:
    """The open semester (or None) and the records of the student. The records compare the student only with the past of the same student."""
    active = [r for r in db.sim_list("active")]
    return {"run": _view(active[-1]["id"]) if active else None, "records": _records()}


def _new_seed() -> int:
    return random.SystemRandom().randrange(1 << 30)  # the seed is secret: the page never sees it


def start(seed: int | None = None) -> dict:
    """A new semester from the real work of the student. An open semester is closed without a penalty."""
    with _lock:
        for r in db.sim_list("active"):
            db.sim_update(r["id"], "abandoned", r["data"])
        sid = db.new_id()
        db.sim_add(sid, new_state(_new_seed() if seed is None else seed, real_snapshot()))
        return _view(sid)


def _run(sid: str, fn) -> dict:
    with _lock:
        row = db.sim_get(sid)
        if not row:
            raise SimError("Simulation not found.", 404)
        if row["status"] != "active":
            raise SimError("The semester is over.", 409)
        s = row["data"]
        out = fn(s)
        db.sim_update(sid, s["status"], s)
        return {"say": out, "run": public(sid, s, s["status"], _boosts()), "records": _records()}


def do(sid: str, action: str, arg: str = "") -> dict:
    return _run(sid, lambda s: act(s, action, arg))


def boost(sid: str, item: str) -> dict:
    return _run(sid, lambda s: use_boost(s, item))


def answer_event(sid: str, choice: str) -> dict:
    return _run(sid, lambda s: choose(s, choice))


def next_week(sid: str) -> dict:
    return _run(sid, lambda s: end_week(s) or "")


def get(sid: str) -> dict:
    return _view(sid)
