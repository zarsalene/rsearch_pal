"""Simple players for the Semester Simulator. The balance tests and the tuning script use them.
A policy gets the state and returns one move: ("act", action, arg), ("end",) or ("choose", choice)."""
import random
import statistics

from app import sim

REAL = {"papers": [{"id": "p1", "title": "Paper one", "rank": 3}, {"id": "p2", "title": "Paper two", "rank": 1}, {"id": "p3", "title": "Paper three", "rank": 0}],
        "links": 1, "knowledge": 23, "mastered": 1, "explained": 0, "read": 1}
EMPTY = None  # a new student: no real work yet


def safe_choice(s):
    """The careful way to answer an event. A reviewer: answer only with good odds."""
    ev = s["event"]
    if ev["id"] == "reviewer":
        return "answer" if sim._odds(s, ev["paper"]) >= 0.55 else "ask"
    return next(c["id"] for c in sim._event_view(s)["choices"] if c["risk"] == "safe")


def balanced(s):
    """A careful student: rest when tired, read first, then test, then write."""
    if s["event"]:
        return ("choose", safe_choice(s))
    c, ap, e = s["chapters"], s["ap"], s["energy"]
    if e < 38 and ap >= 1:
        return ("act", "rest", "")
    if s["week"] % 4 == 1 and not s["scouted"] and ap >= 1 and s["trust"] < 75:
        return ("act", "meet", "")
    if c["review"] < 45 and ap >= 1:
        return ("act", "read", "")
    if c["experiments"] < 85 and ap >= 2 and e >= 45:
        return ("act", "experiment", "")
    if c["writing"] < c["review"] * 0.6 + 20 + c["method"] * 0.2 + c["experiments"] * 0.2 - 6 and ap >= 2:
        return ("act", "write", "")
    if c["review"] < 100 and ap >= 1:
        return ("act", "read", "")
    return ("end",)


def rest_only(s):
    if s["event"]:
        return ("choose", safe_choice(s))
    return ("act", "rest", "") if s["ap"] >= 1 else ("end",)


def grind(s):
    """A student who never rests: tests and writing all the time."""
    if s["event"]:
        return ("choose", safe_choice(s))
    for name in ("experiment", "write", "read"):
        if sim.can(s, name) == "":
            return ("act", name, "")
    return ("end",)


def random_player(seed):
    rng = random.Random(seed)

    def policy(s):
        if s["event"]:
            return ("choose", rng.choice([c["id"] for c in sim._event_view(s)["choices"]]))
        options = [a for a in sim.ACTIONS if sim.can(s, a) == ""]
        if not options or rng.random() < 0.12:
            return ("end",)
        pick = rng.choice(options)
        return ("act", pick, rng.choice(s["papers"])["id"] if pick == "study" else "")

    return policy


def play(policy, seed, real=EMPTY):
    """One whole semester. Returns the final state."""
    s = sim.new_state(seed, real)
    for _ in range(2000):
        if s["status"] != "active":
            return s
        move = policy(s)
        if move[0] == "act":
            sim.act(s, move[1], move[2])
        elif move[0] == "choose":
            sim.choose(s, move[1])
        else:
            sim.end_week(s)
    raise AssertionError("the semester did not end")


def stats(policy_for, n=300, real=EMPTY):
    runs = [play(policy_for(i), i, real) for i in range(n)]
    p = [sim.progress(r) for r in runs]
    return {"mean": statistics.mean(p), "min": min(p), "max": max(p), "burnout": sum(r["status"] == "burnout" for r in runs) / n,
            "grades": {g: sum(r["report"]["grade"] == g for r in runs) for g, _ in sim.GRADES}}
