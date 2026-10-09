"""The game. Points only for real work that the server checks. The boss battle asks questions from checked quotes."""
import json

import pytest

from app import db, game, links
from helpers import assert_no_false_quote, upload, wait_ready

QUIZ_AI = "You write quiz questions"  # the start of the prompt of the boss battle

THU = 70  # a day number. Day 0 is a Thursday, so 70 is a Thursday too.
MON, TUE, WED, FRI, SAT, SUN, NEXT_MON = THU - 3, THU - 2, THU - 1, THU + 1, THU + 2, THU + 3, THU + 4


# ---------- rules without a server ----------
def test_streak_a_rest_token_keeps_the_streak():
    s = game.streak({MON, TUE, THU}, THU)  # Monday, Tuesday, (Wednesday: rest token), Thursday
    assert s["days"] == 4 and s["rest_days"] == 1 and s["tokens_left"] == 1 and s["today_done"] is True


def test_streak_the_weekend_is_free():
    assert game.streak({FRI, NEXT_MON}, NEXT_MON)["days"] == 2  # Friday, (Saturday and Sunday free), Monday
    s = game.streak({FRI, NEXT_MON}, NEXT_MON, weekend_off=False, tokens=1)  # two days off, one token: the streak ends
    assert s["days"] == 1


def test_streak_two_tokens_a_week_and_no_more():
    assert game.streak({MON}, FRI)["days"] == 0  # Tue, Wed, Thu are missed: three days, two tokens
    assert game.streak({MON, TUE}, WED)["days"] == 2  # Wednesday is today: it is not a missed day yet


def test_streak_today_is_not_over_yet():
    s = game.streak({MON, TUE, WED}, THU)
    assert s["days"] == 3 and s["today_done"] is False


def test_streak_without_work_is_zero_and_rest_days_alone_do_not_count():
    assert game.streak(set(), THU)["days"] == 0
    assert game.streak({THU - 30}, THU)["days"] == 0  # one old day is far away: the tokens do not reach it


def test_level_needs_xp_and_a_skill():
    assert game.level_index(5000, {}) == 0  # a lot of XP is not enough: Reader needs 3 cards
    assert game.level_index(100, {"cards": 3}) == 1
    assert game.level_index(100, {"cards": 2}) == 0
    assert game.level_index(300, {"cards": 3, "bosses": 1}) == 2
    assert game.level_index(9999, {"cards": 3, "bosses": 0, "links": 9}) == 1  # a level does not skip the one before


def test_a_right_answer_comes_from_the_quote():
    quote = "AUTOMA reaches a precision of 91.4 percent and a recall of 84.2 percent."
    assert game._supported("91.4 percent", quote)
    assert game._supported("A precision of 91.4 percent", quote)
    assert not game._supported("95.0 percent", quote)  # a number that is not in the quote
    assert not game._supported("It finds all the attacks quickly", quote)  # the words are not in the quote


QUOTES = [{"field": "result", "quote": "AUTOMA reaches a precision of 91.4 percent and a recall of 84.2 percent.", "page": 3},
          {"field": "method", "quote": "Our system uses a hypothesis agent and a validation agent.", "page": 2}]


def q(quote=1, question="What does the system use?", correct="A hypothesis agent and a validation agent", wrong=("A database", "A camera", "A radio")):
    return {"quote": quote, "question": question, "correct": correct, "wrong": list(wrong)}


def test_unfair_questions_are_dropped():
    good = q(2)
    bad = [
        q(99),                                                                           # a quote that the server did not give
        q(2, question="Which tool does it use today?", correct="A tool with 77 agents"),  # a number that the quote does not have
        q(2, question="Which two agents does it have?", wrong=("A hypothesis agent", "A camera", "A radio")),  # a wrong answer that the quote says
        q(2, question="Why is this?", wrong=("A camera", "A camera", "A radio")),        # two same answers
        q(2, question="Short?"),                                                         # a question that is too short
        q(2, question="A question with two wrong answers only", wrong=("A camera", "A radio")),
    ]
    kept = game._clean({"questions": [*bad, good]}, QUOTES, set())
    assert [k["text"] for k in kept] == [good["question"]]


def test_a_question_that_was_asked_before_is_dropped():
    asked = {game._qid("What does the system use?")}
    assert game._clean({"questions": [q(2)]}, QUOTES, asked) == []
    assert game._clean({"questions": [q(2), q(2)]}, QUOTES, set()) != []
    assert len(game._clean({"questions": [q(2), q(2)]}, QUOTES, set())) == 1  # the same question two times counts one time


def test_one_piece_of_work_pays_one_time(client):
    assert db.xp_add("card_ready", "p1", 10) is True
    assert db.xp_add("card_ready", "p1", 10) is False
    assert sum(e["xp"] for e in db.xp_list()) == 10


# ---------- the server ----------
def read(client, h, name="a.pdf", sample_pdfs=None):
    pid = upload(client, h, sample_pdfs[name].path)
    wait_ready(client, h, pid)
    return pid


def xp_total(client, h):
    return client.get("/api/game", headers=h).json()["xp"]


def test_the_game_needs_a_login_and_a_switch(client, auth_headers):
    for path in ("/api/game", "/api/game/collection", "/api/game/map"):
        assert client.get(path).status_code == 401
    assert client.post("/api/papers/x/battle").status_code == 401
    client.put("/api/features", headers=auth_headers, json={"features": {"game": False}})
    assert client.get("/api/game", headers=auth_headers).status_code == 403
    assert client.post("/api/papers/x/battle", headers=auth_headers).status_code == 403
    client.put("/api/features", headers=auth_headers, json={"features": {"game": True}})
    assert client.get("/api/game", headers=auth_headers).status_code == 200


def test_a_new_player_starts_at_explorer(client, auth_headers):
    g = client.get("/api/game", headers=auth_headers).json()
    assert g["xp"] == 0 and g["level"]["name"] == "Explorer" and g["streak"]["days"] == 0 and g["new"] == []
    assert g["next"]["name"] == "Reader" and g["next"]["skills"][0]["need"] == 3


def test_the_page_cannot_send_points(client, auth_headers, fake_ai, sample_pdfs):
    assert client.post("/api/game", headers=auth_headers, json={"xp": 999}).status_code == 405
    assert client.put("/api/game", headers=auth_headers, json={"xp": 999}).status_code == 405
    pid = read(client, auth_headers, sample_pdfs=sample_pdfs)
    bid = client.post(f"/api/papers/{pid}/battle", headers=auth_headers).json()["id"]
    right = db.battle_get(bid)["data"]["questions"][0]["answer"]
    r = client.post(f"/api/battles/{bid}/answer", headers=auth_headers, json={"n": 0, "choice": right, "xp": 9999, "damage": 9999, "hp": 0}).json()
    assert r["xp"] == 5 and r["damage"] == 34 and r["battle"]["hp"] == 66  # the rules of the server, not the numbers of the page


def test_a_ready_card_gives_xp_one_time(client, auth_headers, fake_ai, sample_pdfs):
    read(client, auth_headers, sample_pdfs=sample_pdfs)
    first = client.get("/api/game", headers=auth_headers).json()
    assert [e["action"] for e in first["new"]] == ["card_ready"] and first["xp"] == 10
    again = client.get("/api/game", headers=auth_headers).json()
    assert again["new"] == [] and again["xp"] == 10  # no double XP


def test_truth_a_card_with_too_few_checked_claims_gives_no_xp(client, auth_headers, fake_ai, sample_pdfs):
    """The pasta card has only 2 claims with a checked quote. The others are "not stated"."""
    pid = read(client, auth_headers, "b.pdf", sample_pdfs)
    assert xp_total(client, auth_headers) == 0
    assert client.get("/api/game/collection", headers=auth_headers).json()[0]["rank"] == 0
    assert pid


def test_truth_a_hidden_claim_does_not_count(client, auth_headers, fake_ai, sample_pdfs):
    """The test AI invents a quote for the limitation of the paper AUTOMA. The card hides it, so only 3 claims count."""
    pid = read(client, auth_headers, sample_pdfs=sample_pdfs)
    card = db.get_card(pid)
    assert card["fields"]["limitation"]["status"] == "unverified"
    assert game.checked_claims(card) == 3


def test_a_card_is_a_game_card_with_a_rank(client, auth_headers, fake_ai, sample_pdfs):
    pid = read(client, auth_headers, sample_pdfs=sample_pdfs)
    c = client.get("/api/game/collection", headers=auth_headers).json()[0]
    assert c["id"] == pid and c["rank_name"] == "read" and c["can_fight"] is True and c["boss_won"] is False
    # an own word makes it "explained"
    r = client.post("/api/glossary", headers=auth_headers, json={"term": "hypothesis", "paper_id": pid})
    assert r.status_code == 200, r.text
    assert client.get("/api/game/collection", headers=auth_headers).json()[0]["rank_name"] == "explained"


def test_words_pay_but_the_day_has_a_limit(client, auth_headers, fake_ai, sample_pdfs):
    pid = read(client, auth_headers, sample_pdfs=sample_pdfs)
    for term in ("ontology", "baseline", "corpus", "latency", "entropy", "kernel", "gradient"):
        assert client.post("/api/glossary", headers=auth_headers, json={"term": term, "paper_id": pid}).status_code == 200
    g = client.get("/api/game", headers=auth_headers).json()
    assert [e["action"] for e in g["new"]].count("word_saved") == 5 and g["xp"] == 10 + 5 * 3


def test_an_explained_link_with_a_checked_quote_pays(client, auth_headers, fake_ai, sample_pdfs):
    a, b = read(client, auth_headers, sample_pdfs=sample_pdfs), read(client, auth_headers, "b.pdf", sample_pdfs)
    r = client.post("/api/links/explain", headers=auth_headers, json={"a": a, "b": b})
    assert r.status_code == 200 and r.json()["status"] == "verified"
    ref = ":".join(sorted([a, b]))
    expect = 10 + 10 + (15 if game._lucky(ref) else 0)  # the card of AUTOMA + the link (+ a lucky find)
    assert xp_total(client, auth_headers) == expect


def test_truth_a_link_without_a_checked_quote_pays_nothing(client, auth_headers, fake_ai, sample_pdfs):
    a, b = read(client, auth_headers, sample_pdfs=sample_pdfs), read(client, auth_headers, "b.pdf", sample_pdfs)
    fake_ai.when("You explain how two papers", {"relation": "same_method", "summary": "Both papers talk about methods.", "shared": ["methods"], "differences": "",
                                                "evidence": [{"paper": 1, "quote": "This sentence is not in any of the PDF files at all.", "page": 1}]})
    r = client.post("/api/links/explain", headers=auth_headers, json={"a": a, "b": b}).json()
    assert r["status"] == "unverified"
    assert xp_total(client, auth_headers) == 10  # only the card


def test_a_note_with_a_checked_quote_pays(client, auth_headers, fake_ai, sample_pdfs):
    pid = read(client, auth_headers, sample_pdfs=sample_pdfs)
    ev = [{"paper_id": pid, "quote": "Analysts spend many hours on manual log review and miss attacks.", "page": 1}]
    assert client.post(f"/api/papers/{pid}/notes", headers=auth_headers, json={"question": "Why?", "answer": "Because of manual work.", "evidence": ev}).status_code == 200
    assert xp_total(client, auth_headers) == 13
    bad = [{"paper_id": pid, "quote": "This sentence is not in any of the PDF files at all.", "page": 1}]
    client.post(f"/api/papers/{pid}/notes", headers=auth_headers, json={"question": "Q", "answer": "An answer without proof.", "evidence": bad})
    assert xp_total(client, auth_headers) == 13  # a note without a checked quote pays nothing


def test_the_weekend_setting(client, auth_headers):
    assert client.get("/api/game", headers=auth_headers).json()["settings"]["weekend_off"] is True
    assert client.put("/api/game/settings", headers=auth_headers, json={"weekend_off": False}).status_code == 200
    assert client.get("/api/game", headers=auth_headers).json()["settings"]["weekend_off"] is False


# ---------- the boss battle ----------
def start(client, h, pid):
    r = client.post(f"/api/papers/{pid}/battle", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def answer(client, h, bid, n, choice):
    return client.post(f"/api/battles/{bid}/answer", headers=h, json={"n": n, "choice": choice})


def right_choice(bid, n):
    return db.battle_get(bid)["data"]["questions"][n]["answer"]


def wrong_choice(bid, n):
    return (right_choice(bid, n) + 1) % 4


def test_a_battle_starts_with_checked_questions_and_hides_the_answers(client, auth_headers, fake_ai, sample_pdfs):
    pid = read(client, auth_headers, sample_pdfs=sample_pdfs)
    b = start(client, auth_headers, pid)
    assert b["status"] == "active" and b["total"] == 3 and b["hp"] == 100 and b["hearts"] == 3 and b["history"] == []
    assert len(b["question"]["options"]) == 4 and "answer" not in b["question"] and "proof" not in b["question"]
    assert [c for c in fake_ai.calls if QUIZ_AI in c["system"]]  # the questions come from the AI
    assert start(client, auth_headers, pid)["id"] == b["id"]  # the same open battle: no new AI call
    assert len([c for c in fake_ai.calls if QUIZ_AI in c["system"]]) == 1


def test_a_perfect_fight_defeats_the_boss(client, auth_headers, fake_ai, sample_pdfs):
    pid = read(client, auth_headers, sample_pdfs=sample_pdfs)
    b = start(client, auth_headers, pid)
    r = None
    for n in range(3):
        r = answer(client, auth_headers, b["id"], n, right_choice(b["id"], n))
        assert r.status_code == 200, r.text
        r = r.json()
        assert r["correct"] is True and r["proof"]["verified"] is True
    assert r["crit"] is True  # the third right answer in a row hits harder
    assert r["battle"]["status"] == "won" and r["battle"]["hp"] == 0 and r["battle"]["result"]["flawless"] is True
    assert r["xp"] == 8 + 30 + 15  # the combo answer, the boss, the flawless bonus
    g = client.get("/api/game", headers=auth_headers).json()
    assert g["xp"] == 10 + 5 + 5 + 8 + 30 + 15 and g["stats"]["mastered"] == 1
    assert client.get("/api/game/collection", headers=auth_headers).json()[0]["rank_name"] == "mastered"


def test_a_lost_fight_costs_nothing(client, auth_headers, fake_ai, sample_pdfs):
    pid = read(client, auth_headers, sample_pdfs=sample_pdfs)
    b = start(client, auth_headers, pid)
    for n in range(3):
        r = answer(client, auth_headers, b["id"], n, wrong_choice(b["id"], n)).json()
        assert r["correct"] is False
    assert r["battle"]["status"] == "lost" and r["battle"]["hearts"] == 0 and r["battle"]["result"]["won"] is False
    assert "Nothing is lost" in r["battle"]["result"]["text"]
    assert xp_total(client, auth_headers) == 10  # no XP and no loss
    assert answer(client, auth_headers, b["id"], 3, 0).status_code == 409  # the fight is over
    # a new fight asks new questions
    b2 = start(client, auth_headers, pid)
    assert b2["id"] != b["id"] and "Round 2" in b2["question"]["text"]


def test_a_wrong_answer_breaks_the_combo(client, auth_headers, fake_ai, sample_pdfs):
    pid = read(client, auth_headers, sample_pdfs=sample_pdfs)
    b = start(client, auth_headers, pid)
    r1 = answer(client, auth_headers, b["id"], 0, right_choice(b["id"], 0)).json()
    r2 = answer(client, auth_headers, b["id"], 1, wrong_choice(b["id"], 1)).json()
    assert r1["battle"]["combo"] == 1 and r2["battle"]["combo"] == 0 and r2["battle"]["hearts"] == 2 and r2["correct"] is False
    assert r2["answer"] == right_choice(b["id"], 1)  # after the answer, the page sees the right one
    r3 = answer(client, auth_headers, b["id"], 2, right_choice(b["id"], 2)).json()
    assert r3["battle"]["status"] == "lost" and r3["battle"]["hp"] == 32  # the boss still stands: two hits of 34 damage, no flawless bonus


def test_a_question_is_answered_one_time_and_in_order(client, auth_headers, fake_ai, sample_pdfs):
    pid = read(client, auth_headers, sample_pdfs=sample_pdfs)
    b = start(client, auth_headers, pid)
    assert answer(client, auth_headers, b["id"], 1, 0).status_code == 409  # not the open question
    assert answer(client, auth_headers, b["id"], 0, 7).status_code == 400  # not an answer
    assert answer(client, auth_headers, b["id"], 0, right_choice(b["id"], 0)).status_code == 200
    assert answer(client, auth_headers, b["id"], 0, right_choice(b["id"], 0)).status_code == 409  # again: no second XP
    assert xp_total(client, auth_headers) == 10 + 5
    assert client.get("/api/battles/nope", headers=auth_headers).status_code == 404
    assert answer(client, auth_headers, "nope", 0, 0).status_code == 404


def test_truth_the_proof_of_each_answer_is_in_the_pdf(client, auth_headers, fake_ai, sample_pdfs):
    pid = read(client, auth_headers, sample_pdfs=sample_pdfs)
    b = start(client, auth_headers, pid)
    last = None
    for n in range(3):
        last = answer(client, auth_headers, b["id"], n, wrong_choice(b["id"], n) if n == 0 else right_choice(b["id"], n)).json()
        assert_no_false_quote(last, sample_pdfs["a.pdf"].pages)
    assert len(last["battle"]["history"]) == 3
    assert_no_false_quote(client.get(f"/api/battles/{b['id']}", headers=auth_headers).json(), sample_pdfs["a.pdf"].pages)


def test_truth_unfair_questions_never_reach_the_student(client, auth_headers, fake_ai, sample_pdfs):
    pid = read(client, auth_headers, sample_pdfs=sample_pdfs)
    good = [q(1, "What is the problem of the paper?", "Analysts spend many hours on manual log review", ("Analysts have no data", "Logs are too short", "Nobody reads the logs")),
            q(2, "What does the system use?"),
            q(3, "Which precision does it reach?", "A precision of 91.4 percent", ("A precision of 50 percent", "A precision of 12 percent", "A precision of 3 percent"))]
    bad = [q(99), q(2, "Which number does the system reach?", "A recall of 99.9 percent"), q(2, "Which agents are there?", "A hypothesis agent", ("A validation agent", "A camera", "A radio"))]
    fake_ai.when(QUIZ_AI, {"questions": [*bad, *good]})
    b = start(client, auth_headers, pid)
    assert b["total"] == 3
    texts = [db.battle_get(b["id"])["data"]["questions"][i]["text"] for i in range(3)]
    assert sorted(texts) == sorted(x["question"] for x in good)


def test_too_few_fair_questions_make_no_battle(client, auth_headers, fake_ai, sample_pdfs):
    pid = read(client, auth_headers, sample_pdfs=sample_pdfs)
    fake_ai.when(QUIZ_AI, {"questions": [q(99), q(2), q(77)]})
    r = client.post(f"/api/papers/{pid}/battle", headers=auth_headers)
    assert r.status_code == 502 and "fair questions" in r.json()["detail"]
    assert db.battle_list(pid) == []


def test_truth_a_quote_that_is_not_in_the_pdf_is_not_used(client, auth_headers, fake_ai, sample_pdfs):
    """The card says "verified" for a quote that is not in the PDF (a damaged card). The server looks in the PDF again."""
    pid = read(client, auth_headers, sample_pdfs=sample_pdfs)
    card = db.get_card(pid)
    for name in ("problem", "method", "result"):
        card["fields"][name]["evidence"] = [{"quote": "This sentence is not in any of the PDF files at all.", "page": 1, "verified": True}]
    db.save_card(pid, card)
    r = client.post(f"/api/papers/{pid}/battle", headers=auth_headers)
    assert r.status_code == 409 and "too few" in r.json()["detail"]
    assert not [c for c in fake_ai.calls if QUIZ_AI in c["system"]]  # no question without a proof


def test_a_paper_that_is_not_ready_has_no_boss(client, auth_headers, fake_ai, sample_pdfs):
    assert client.post("/api/papers/nope/battle", headers=auth_headers).status_code == 404
    pid = upload(client, auth_headers, sample_pdfs["a.pdf"].path)
    db.update_paper(pid, status="processing")
    assert client.post(f"/api/papers/{pid}/battle", headers=auth_headers).status_code == 409


def test_a_level_up_is_told_in_the_answer(client, auth_headers, fake_ai, sample_pdfs):
    pid = read(client, auth_headers, sample_pdfs=sample_pdfs)
    for i in range(2):  # 3 cards in all, and 95 XP: one right answer makes 100 XP, and the level Reader
        db.xp_add("card_ready", f"old{i}", 10)
    db.xp_add("eureka", "old", 65)
    g = client.get("/api/game", headers=auth_headers).json()
    assert g["xp"] == 95 and g["level"]["name"] == "Explorer" and g["skills"]["cards"] == 3
    b = start(client, auth_headers, pid)
    r = answer(client, auth_headers, b["id"], 0, right_choice(b["id"], 0)).json()
    assert r["level_up"] == "Reader" and r["total_xp"] == 100
    assert client.get("/api/game", headers=auth_headers).json()["level"]["name"] == "Reader"


def test_the_map_shows_fog_until_a_link_is_explained(client, auth_headers, fake_ai, sample_pdfs, monkeypatch):
    a, b = read(client, auth_headers, sample_pdfs=sample_pdfs), read(client, auth_headers, "b.pdf", sample_pdfs)
    nodes = [{"id": a, "title": "AUTOMA", "verdict": "read", "keywords": []}, {"id": b, "title": "Pasta", "verdict": "skip", "keywords": []}]
    monkeypatch.setattr(links, "build_graph", lambda: {"nodes": nodes, "edges": [{"source": a, "target": b, "sim": 0.5, "shared": []}], "threshold": 0.4})
    m = client.get("/api/game/map", headers=auth_headers).json()
    assert m["edges"][0]["state"] == "fog" and m["stats"] == {"found": 0, "fog": 1, "unclear": 0} and m["edges"][0]["summary"] == ""
    assert {n["id"]: n["rank"] for n in m["nodes"]} == {a: 1, b: 0}
    client.post("/api/links/explain", headers=auth_headers, json={"a": b, "b": a})
    m = client.get("/api/game/map", headers=auth_headers).json()
    assert m["edges"][0]["state"] == "found" and m["edges"][0]["summary"] and m["stats"]["found"] == 1


def test_an_unclear_link_stays_in_the_fog_of_doubt(client, auth_headers, fake_ai, sample_pdfs, monkeypatch):
    a, b = read(client, auth_headers, sample_pdfs=sample_pdfs), read(client, auth_headers, "b.pdf", sample_pdfs)
    nodes = [{"id": a, "title": "AUTOMA", "verdict": "read", "keywords": []}, {"id": b, "title": "Pasta", "verdict": "skip", "keywords": []}]
    monkeypatch.setattr(links, "build_graph", lambda: {"nodes": nodes, "edges": [{"source": a, "target": b, "sim": 0.5, "shared": []}], "threshold": 0.4})
    fake_ai.when("You explain how two papers", {"relation": "other", "summary": "Maybe a link.", "shared": [], "differences": "", "evidence": []})
    client.post("/api/links/explain", headers=auth_headers, json={"a": a, "b": b})
    e = client.get("/api/game/map", headers=auth_headers).json()["edges"][0]
    assert e["state"] == "unclear" and e["summary"] == ""  # no checked quote: the map does not show the text


def test_a_deleted_paper_loses_its_battles_but_keeps_the_xp(client, auth_headers, fake_ai, sample_pdfs):
    pid = read(client, auth_headers, sample_pdfs=sample_pdfs)
    b = start(client, auth_headers, pid)
    answer(client, auth_headers, b["id"], 0, right_choice(b["id"], 0))
    assert xp_total(client, auth_headers) == 10 + 5
    client.delete(f"/api/papers/{pid}", headers=auth_headers)
    assert db.battle_list() == []
    assert xp_total(client, auth_headers) == 10 + 5  # the work was done


def test_the_backup_keeps_the_battles_and_cannot_forge_xp(client, auth_headers, fake_ai, sample_pdfs):
    pid = read(client, auth_headers, sample_pdfs=sample_pdfs)
    b = start(client, auth_headers, pid)
    for n in range(3):
        answer(client, auth_headers, b["id"], n, right_choice(b["id"], n))
    backup = client.get("/api/export", headers=auth_headers).json()
    assert backup["game"]["battles"][0]["status"] == "won" and {e["action"] for e in backup["game"]["xp"]} >= {"boss_defeated", "battle_answer"}
    # a forged file: a big XP value and an action that the file may not give
    game.import_data({"xp": [{"action": "boss_defeated", "ref_id": "forged", "xp": 99999, "time": 1}, {"action": "card_ready", "ref_id": "forged2", "xp": 99999, "time": 1}],
                      "battles": [{"id": "x1", "paper_id": pid, "status": "won", "data": {"questions": []}, "created_at": 1}]})
    events = {(e["action"], e["ref_id"]): e["xp"] for e in db.xp_list()}
    assert events[("boss_defeated", "forged")] == 30 and ("card_ready", "forged2") not in events  # the value comes from the rules
    assert db.battle_get("x1") is None  # a battle with a wrong shape is not restored
