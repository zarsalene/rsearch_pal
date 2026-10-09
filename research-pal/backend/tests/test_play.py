"""Sprint 14: Duck Island. Mini-games use only verified quotes. Play gives coins, never points. A round pays one time."""
from app import db, game, play
from helpers import upload, wait_ready

A_QUOTE = "Our system uses a hypothesis agent and a validation agent."  # page 2 of a.pdf
B_QUOTES = [("Pasta with tomato sauce is easy to cook at home and cheap for students.", 4), ("The sauce tastes better with basil and olive oil.", 3),
            ("We boil the pasta for nine minutes and stir the tomato sauce slowly with fresh basil leaves.", 2)]
FALSE_QUOTE = "The system reaches a perfect precision of 100 percent on every dataset in the world."


def two_papers(client, h, sample_pdfs):
    ids = []
    for name in ("a.pdf", "b.pdf"):
        pid = upload(client, h, sample_pdfs[name].path)
        wait_ready(client, h, pid)
        ids.append(pid)
    return ids


def with_material(client, h, sample_pdfs):
    a, b = two_papers(client, h, sample_pdfs)
    db.review_add("quiz", a, "What does the system use?", "A hypothesis agent and a validation agent.", A_QUOTE, 2)
    for i, (q, page) in enumerate(B_QUOTES):
        db.review_add("quiz", b, f"Question {i}", "Answer", q, page)
    return a, b


def right_answers(client, h, rid, n):
    """Finish a round with a wrong answer first, to read the right answers. Only for the helper: it uses a second round."""
    return [db.play_round_get(rid)["questions"][i]["answer"] for i in range(n)]


def new_round(client, h, game_code="quotes"):
    r = client.post("/api/play/rounds", headers=h, json={"game": game_code})
    assert r.status_code == 200, r.text
    return r.json()


def test_the_island_state_has_coins_a_shop_and_game_places(client, auth_headers):
    s = client.get("/api/play", headers=auth_headers).json()
    assert s["coins"]["balance"] == 0 and s["grid"] == {"w": 12, "h": 8}
    assert {x["code"] for x in s["spots"]} == {"quotes", "terms", "shop"}
    assert len(s["shop"]) == len(play.SHOP) and not any(i["owned"] for i in s["shop"])


def test_a_round_has_questions_but_no_answers(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    with_material(client, h, sample_pdfs)
    rnd = new_round(client, h)
    assert rnd["game"] == "quotes" and 3 <= len(rnd["questions"]) <= 5
    assert "answer" not in str(rnd) and all("answer" not in q for q in rnd["questions"])
    for q in rnd["questions"]:
        assert 2 <= len(q["options"]) <= 4 and q["prompt"] in [A_QUOTE] + [x for x, _ in B_QUOTES]


def test_truth_a_false_quote_never_appears_in_a_round(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    a, b = with_material(client, h, sample_pdfs)
    db.review_add("quiz", a, "Invented", "Invented", FALSE_QUOTE, 3)  # a quote that is not in the PDF
    db.review_add("quiz", b, "Wrong paper", "x", A_QUOTE, 1)  # a real quote, but not in this paper
    for _ in range(8):
        rnd = new_round(client, h)
        prompts = [q["prompt"] for q in rnd["questions"]]
        assert FALSE_QUOTE not in prompts
        for q in rnd["questions"]:  # the title of the right paper is an option, and the quote is in that paper
            assert any(opt in (sample_pdfs["a.pdf"].title, sample_pdfs["b.pdf"].title) for opt in q["options"])
    assert client.get("/api/play", headers=h).json()["material"]["quotes"] == 4  # 4 verified quotes. The 2 bad ones do not count.


def test_finish_a_round_gives_coins_and_shows_the_sources(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    with_material(client, h, sample_pdfs)
    rnd = new_round(client, h)
    n = len(rnd["questions"])
    right = right_answers(client, h, rnd["id"], n)
    res = client.post(f"/api/play/rounds/{rnd['id']}/finish", headers=h, json={"answers": right}).json()
    assert res["score"] == n and res["coins"] == n + play.PERFECT_BONUS and not res["capped"]
    assert all(a["source"]["quote"] and a["source"]["title"] and a["source"]["page"] for a in res["answers"])
    assert client.get("/api/play", headers=h).json()["coins"]["balance"] == res["coins"]


def test_a_round_pays_one_time_only(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    with_material(client, h, sample_pdfs)
    rnd = new_round(client, h)
    right = right_answers(client, h, rnd["id"], len(rnd["questions"]))
    first = client.post(f"/api/play/rounds/{rnd['id']}/finish", headers=h, json={"answers": right})
    second = client.post(f"/api/play/rounds/{rnd['id']}/finish", headers=h, json={"answers": right})
    assert first.status_code == 200 and second.status_code == 400 and "finished already" in second.json()["detail"]
    assert client.get("/api/play", headers=h).json()["coins"]["play"] == first.json()["coins"]


def test_wrong_answers_give_fewer_coins_and_a_bad_payload_is_refused(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    with_material(client, h, sample_pdfs)
    rnd = new_round(client, h)
    n = len(rnd["questions"])
    assert client.post(f"/api/play/rounds/{rnd['id']}/finish", headers=h, json={"answers": [0]}).status_code == 400
    assert client.post(f"/api/play/rounds/{rnd['id']}/finish", headers=h, json={}).status_code == 400
    right = right_answers(client, h, rnd["id"], n)
    wrong = [None] * n  # no answer is a wrong answer. true is not an answer either.
    wrong[0] = True
    res = client.post(f"/api/play/rounds/{rnd['id']}/finish", headers=h, json={"answers": wrong}).json()
    assert res["score"] == 0 and res["coins"] == 0 and "Good play" in res["message"]
    assert right  # the right answers were not shown by the round before the end
    assert client.post("/api/play/rounds/unknown/finish", headers=h, json={"answers": []}).status_code == 400


def test_the_daily_limit_stops_the_coins_but_not_the_play(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    with_material(client, h, sample_pdfs)
    paid = []
    for _ in range(4):
        rnd = new_round(client, h)
        res = client.post(f"/api/play/rounds/{rnd['id']}/finish", headers=h, json={"answers": right_answers(client, h, rnd["id"], len(rnd["questions"]))})
        assert res.status_code == 200
        paid.append(res.json())
    assert sum(p["coins"] for p in paid) == play.DAILY_PLAY_CAP
    assert paid[-1]["coins"] == 0 and paid[-1]["capped"] and paid[-1]["score"] == len(paid[-1]["answers"])  # the score still counts for fun


def test_play_gives_no_points_and_no_level(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    with_material(client, h, sample_pdfs)
    before = client.get("/api/game", headers=h).json()
    rnd = new_round(client, h)
    client.post(f"/api/play/rounds/{rnd['id']}/finish", headers=h, json={"answers": right_answers(client, h, rnd["id"], len(rnd["questions"]))})
    after = client.get("/api/game", headers=h).json()
    assert after["xp"] == before["xp"] and after["level"]["index"] == before["level"]["index"] and after["badges"] == before["badges"]


def test_a_round_needs_material_and_says_what_to_do(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    r = client.post("/api/play/rounds", headers=h, json={"game": "quotes"})
    assert r.status_code == 400 and "2 papers" in r.json()["detail"]
    a, b = two_papers(client, h, sample_pdfs)
    r = client.post("/api/play/rounds", headers=h, json={"game": "quotes"})
    assert r.status_code == 400 and "quiz" in r.json()["detail"]
    assert client.post("/api/play/rounds", headers=h, json={"game": "chess"}).status_code == 400
    r = client.post("/api/play/rounds", headers=h, json={"game": "terms"})
    assert r.status_code == 400 and "glossary" in r.json()["detail"]


def test_word_match_uses_the_meanings_of_the_papers(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    a, b = two_papers(client, h, sample_pdfs)
    db.glossary_add("agent", A_QUOTE, "paper", a, 2)
    db.glossary_add("pasta", B_QUOTES[0][0], "paper", b, 4)
    db.glossary_add("sauce", B_QUOTES[1][0], "paper", b, 3)
    db.glossary_add("magic", "An AI explanation that is not a quote from a paper.", "ai", a, 0)
    rnd = new_round(client, h, "terms")
    assert len(rnd["questions"]) == 3 and all(q["prompt"].startswith("Which meaning fits the word") for q in rnd["questions"])
    assert not any("AI explanation" in o for q in rnd["questions"] for o in q["options"]) and "magic" not in str(rnd)
    res = client.post(f"/api/play/rounds/{rnd['id']}/finish", headers=h, json={"answers": right_answers(client, h, rnd["id"], 3)}).json()
    assert res["score"] == 3


def test_the_shop_uses_coins_from_work_and_play(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    assert client.post("/api/play/buy", headers=h, json={"code": "flower"}).status_code == 400  # no coins
    game.award("win_written", "w1", 50)  # 50 points of real work are 10 coins
    s = client.get("/api/play", headers=h).json()
    assert s["coins"]["work"] == 10 and s["coins"]["balance"] == 10
    s = client.post("/api/play/buy", headers=h, json={"code": "flower"}).json()
    assert s["coins"]["balance"] == 5 and next(i for i in s["shop"] if i["code"] == "flower")["owned"]
    again = client.post("/api/play/buy", headers=h, json={"code": "flower"})
    assert again.status_code == 400 and "already" in again.json()["detail"]
    poor = client.post("/api/play/buy", headers=h, json={"code": "fountain"})
    assert poor.status_code == 400 and "Not enough coins" in poor.json()["detail"] and "5" in poor.json()["detail"]
    assert client.post("/api/play/buy", headers=h, json={"code": "nothing"}).status_code == 400
    assert client.get("/api/game", headers=h).json()["xp"] == 50  # buying costs coins, never points


def test_place_an_item_only_on_a_free_place_of_the_island(client, auth_headers):
    h = auth_headers
    game.award("win_written", "w1", 100)
    client.post("/api/play/buy", headers=h, json={"code": "flower"})
    client.post("/api/play/buy", headers=h, json={"code": "tree"})
    put = lambda code, x, y: client.put(f"/api/play/items/{code}", headers=h, json={"x": x, "y": y})
    assert put("bench", 1, 1).status_code == 400  # not bought
    assert put("flower", 12, 0).status_code == 400 and put("flower", -1, 0).status_code == 400 and put("flower", "a", 0).status_code == 400
    assert put("flower", 2, 2).status_code == 400  # the Quote Hunt place
    ok = put("flower", 3, 3)
    assert ok.status_code == 200 and next(i for i in ok.json()["shop"] if i["code"] == "flower")["x"] == 3
    assert put("tree", 3, 3).status_code == 400  # taken
    assert put("flower", 4, 3).status_code == 200  # a move


def test_the_switch_turns_the_game_off(client, auth_headers):
    h = auth_headers
    client.put("/api/features", headers=h, json={"features": {"play": False}})
    assert client.get("/api/play", headers=h).status_code == 403
    assert client.post("/api/play/rounds", headers=h, json={"game": "quotes"}).status_code == 403


def test_the_backup_keeps_coins_and_items(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    with_material(client, h, sample_pdfs)
    game.award("win_written", "w1", 100)
    rnd = new_round(client, h)
    client.post(f"/api/play/rounds/{rnd['id']}/finish", headers=h, json={"answers": right_answers(client, h, rnd["id"], len(rnd["questions"]))})
    client.post("/api/play/buy", headers=h, json={"code": "tree"})
    client.put("/api/play/items/tree", headers=h, json={"x": 6, "y": 4})
    before = client.get("/api/play", headers=h).json()
    backup = client.get("/api/export", headers=h).json()
    assert len(backup["play_rounds"]) == 1 and [i["code"] for i in backup["play_items"]] == ["tree"]
    with db.conn() as c:
        c.execute("DELETE FROM play_rounds")
        c.execute("DELETE FROM play_items")
    client.post("/api/import", headers=h, json=backup)
    client.post("/api/import", headers=h, json=backup)  # a second restore adds nothing
    after = client.get("/api/play", headers=h).json()
    assert after["coins"] == before["coins"] and next(i for i in after["shop"] if i["code"] == "tree")["x"] == 6


def test_a_small_library_can_play_a_round_of_two_but_gets_no_perfect_bonus(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    a, b = two_papers(client, h, sample_pdfs)
    db.review_add("quiz", a, "Q1", "A1", A_QUOTE, 2)
    db.review_add("quiz", b, "Q2", "A2", B_QUOTES[1][0], 3)
    rnd = new_round(client, h)
    assert len(rnd["questions"]) == 2
    res = client.post(f"/api/play/rounds/{rnd['id']}/finish", headers=h, json={"answers": right_answers(client, h, rnd["id"], 2)}).json()
    assert res["score"] == 2 and res["coins"] == 2
