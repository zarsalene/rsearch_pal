"""Duck Island (Sprint 14). A small game world on top of the Journey page.
The rules:
- Play never gives XP, levels or badges. Those come only from real work (game.py). Play gives "coins" for fun things: items for the island.
- Coins come from two sources: your real work (1 coin for each 5 points) and the mini-games (a limit for each day).
- A mini-game uses ONLY material that the server verified: a quote that is in the PDF of its paper. The server checks it again when it makes the round.
- The server makes the question and keeps the answer. The page never sees the answer before the round is finished. A round pays one time only.
- No guilt: nothing is lost, no timer, no ranking. A full daily limit only means: play for fun, no more coins today."""
import random

from . import chat, db, game

GAMES = {
    "quotes": {"name": "Quote Hunt", "text": "A quote from your papers. Which paper has it?"},
    "terms": {"name": "Word Match", "text": "A word from your glossary. Which meaning is right?"},
}
ROUND_SIZE = 5
MIN_ROUND = 2
PERFECT_MIN = 3  # a perfect round of 2 questions gets no bonus
DAILY_PLAY_CAP = 15  # coins from mini-games for each day
PERFECT_BONUS = 2
POINTS_PER_COIN = 5
MAX_QUOTE_CHARS = 240
W, H = 12, 8  # the island grid
SPOTS = {"quotes": (2, 2), "terms": (9, 2), "shop": (5, 6)}  # places that stay free
SHOP = [  # code, name, cost
    ("flower", "Flower", 5), ("tree", "Tree", 10), ("bench", "Bench", 15), ("lamp", "Lamp", 20), ("flag", "Flag", 25),
    ("tent", "Tent", 30), ("boat", "Boat", 40), ("telescope", "Telescope", 50), ("fountain", "Fountain", 60),
]
PRICE = {c: p for c, _, p in SHOP}


class PlayError(Exception):
    """Wrong request. The message is for the user."""


def today() -> str:
    return game.local_date(db.now())


# ------------------------------------------------------------------ coins
def coins() -> dict:
    work = db.xp_total() // POINTS_PER_COIN
    played = db.play_coins_total()
    spent = sum(PRICE.get(i["code"], 0) for i in db.play_items_list())
    return {"work": work, "play": played, "spent": spent, "balance": work + played - spent,
            "play_today": db.play_coins_on(today()), "play_cap": DAILY_PLAY_CAP}


# ------------------------------------------------------------------ material (verified quotes only)
def _verified_material() -> list[dict]:
    """Quiz questions and saved words that have a quote. The server checks each quote in the PDF text again."""
    rows = db.play_review_material()
    pages = {pid: db.get_pages(pid) for pid in {r["paper_id"] for r in rows}}
    checked = chat.verify_evidence([{"paper_id": r["paper_id"], "quote": r["quote"], "page": r["page"]} for r in rows], pages)
    by_key = {(e["paper_id"], e["quote"]): e for e in checked}  # a row of a paper without text is skipped by verify_evidence
    out = []
    for r in rows:
        e = by_key.get((r["paper_id"], r["quote"].strip()[:400]))
        paper = db.get_paper(r["paper_id"])
        if e and e["verified"] and paper and paper["status"] == "ready" and len(r["quote"]) <= MAX_QUOTE_CHARS:
            out.append({**r, "page": e["page"], "title": paper["title"]})
    return out


def material_counts() -> dict:
    mat = _verified_material()
    ready = [p for p in db.list_papers() if p["status"] == "ready"]
    return {"quotes": len(mat) if len(ready) >= 2 else 0, "terms": len([m for m in mat if m["kind"] == "glossary"]), "papers": len({m["paper_id"] for m in mat})}


def _quotes_round(mat: list[dict], rng: random.Random) -> list[dict]:
    ready = [p for p in db.list_papers() if p["status"] == "ready"]
    if len(ready) < 2:
        raise PlayError("Quote Hunt needs 2 papers that are ready. Read one more paper first.")
    if len(mat) < MIN_ROUND:
        raise PlayError(f"Quote Hunt needs at least {MIN_ROUND} checked quotes (quiz questions or saved words). Do a quiz on a paper first.")
    mat = mat[:]
    rng.shuffle(mat)
    seen, qs = set(), []
    for m in mat:
        if m["quote"] in seen:
            continue
        seen.add(m["quote"])
        others = [p["title"] for p in ready if p["id"] != m["paper_id"] and p["title"] != m["title"]]
        rng.shuffle(others)
        options = [m["title"]] + others[:3]
        if len(options) < 2:
            continue
        rng.shuffle(options)
        qs.append({"prompt": m["quote"], "options": options, "answer": options.index(m["title"]), "source": {"title": m["title"], "page": m["page"], "quote": m["quote"]}})
        if len(qs) == ROUND_SIZE:
            break
    return qs


def _terms_round(mat: list[dict], rng: random.Random) -> list[dict]:
    words = [m for m in mat if m["kind"] == "glossary"]
    if len(words) < MIN_ROUND:
        raise PlayError(f"Word Match needs at least {MIN_ROUND} words in your glossary, with a meaning from a paper. Select a word in a paper and save it.")
    words = words[:]
    rng.shuffle(words)
    qs = []
    for m in words[:ROUND_SIZE]:
        others = [w["answer"] for w in words if w["id"] != m["id"] and w["answer"] != m["answer"]]
        rng.shuffle(others)
        options = [m["answer"]] + others[:3]
        if len(options) < 2:
            continue
        rng.shuffle(options)
        qs.append({"prompt": f"Which meaning fits the word \"{m['question']}\"?", "options": options, "answer": options.index(m["answer"]),
                   "source": {"title": m["title"], "page": m["page"], "quote": m["quote"]}})
    return qs


def make_round(game_code: str, seed=None) -> dict:
    if game_code not in GAMES:
        raise PlayError("This game does not exist.")
    rng = random.Random(seed)
    mat = _verified_material()
    qs = _quotes_round(mat, rng) if game_code == "quotes" else _terms_round(mat, rng)
    if len(qs) < MIN_ROUND:
        raise PlayError("There is not enough material for a round yet. Read, quiz and save words first.")
    return round_view(db.play_round_add(game_code, qs, today()))


def round_view(rid: str) -> dict:
    r = db.play_round_get(rid)
    return {"id": rid, "game": r["game"], "name": GAMES[r["game"]]["name"], "finished": bool(r["finished"]),
            "questions": [{"prompt": q["prompt"], "options": q["options"]} for q in r["questions"]]}  # no answer here


def finish_round(rid: str, answers) -> dict:
    r = db.play_round_get(rid)
    if not r:
        raise PlayError("Round not found.")
    qs = r["questions"]
    if not isinstance(answers, list) or len(answers) != len(qs):
        raise PlayError("Send one answer for each question.")
    score = sum(1 for q, a in zip(qs, answers) if isinstance(a, int) and not isinstance(a, bool) and a == q["answer"])
    want = score + (PERFECT_BONUS if score == len(qs) and len(qs) >= PERFECT_MIN else 0)
    room = max(0, DAILY_PLAY_CAP - db.play_coins_on(r["date"]))
    paid = min(want, room)
    if not db.play_round_finish(rid, score, paid):
        raise PlayError("This round is finished already.")
    return {"score": score, "total": len(qs), "coins": paid, "capped": paid < want,
            "message": "Perfect round." if score == len(qs) else "Good play. Every round helps you remember.",
            "answers": [{"correct": q["answer"], "chosen": a if isinstance(a, int) else None, "source": q["source"]} for q, a in zip(qs, answers)],
            "coins_state": coins()}


# ------------------------------------------------------------------ shop and island
def view() -> dict:
    owned = {i["code"]: i for i in db.play_items_list()}
    return {"coins": coins(), "grid": {"w": W, "h": H}, "spots": [{"code": k, "x": x, "y": y} for k, (x, y) in SPOTS.items()],
            "games": [{"code": k, **v} for k, v in GAMES.items()], "material": material_counts(),
            "shop": [{"code": c, "name": n, "cost": p, "owned": c in owned, "x": owned[c]["x"] if c in owned else -1, "y": owned[c]["y"] if c in owned else -1} for c, n, p in SHOP]}


def buy(code: str) -> dict:
    if code not in PRICE:
        raise PlayError("This item does not exist.")
    if any(i["code"] == code for i in db.play_items_list()):
        raise PlayError("You have this item already.")
    c = coins()
    if c["balance"] < PRICE[code]:
        raise PlayError(f"Not enough coins. You have {c['balance']}. The price is {PRICE[code]}. Your work and the mini-games give coins.")
    db.play_item_buy(code)
    return view()


def place(code: str, x, y) -> dict:
    if not any(i["code"] == code for i in db.play_items_list()):
        raise PlayError("You do not have this item.")
    if not (isinstance(x, int) and isinstance(y, int) and not isinstance(x, bool) and not isinstance(y, bool)) or not (0 <= x < W and 0 <= y < H):
        raise PlayError("This place is not on the island.")
    if (x, y) in SPOTS.values():
        raise PlayError("This place must stay free: it is a game place.")
    if any(i["code"] != code and (i["x"], i["y"]) == (x, y) for i in db.play_items_list()):
        raise PlayError("Another item is on this place.")
    db.play_item_place(code, x, y)
    return view()
