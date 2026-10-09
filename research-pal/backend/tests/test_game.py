"""Sprint 05: the game. Points only for real work that the server verified."""
import copy
import datetime as dt
import re

from app import db, game, main
from fake_ai import default_answers
from helpers import upload, wait_ready

EXPLAIN_AI = "to check an explanation of a paper"
HIGH = "Analysts spend many hours on manual log review. The system uses a hypothesis agent and a validation agent. It reaches a precision of 91.4 percent and a recall of 84.2 percent."
LOW = "The system uses a hypothesis agent. It reaches a precision of 91.4 percent. The recall is 95.0 percent. It also cooks pasta."
DAY = dt.datetime(2026, 10, 9, 12, 0, tzinfo=dt.timezone.utc).timestamp()  # a Friday


def verified_card(messages):
    """A card where all four main fields have a quote that is in the PDF."""
    raw = copy.deepcopy(default_answers(messages))
    raw["limitation"] = {"answer": "The authors test only one dataset.", "evidence": [{"quote": "We test only on one dataset.", "page": 3}]}
    raw["result"] = {"answer": "Precision is 91.4 percent. Recall is 84.2 percent.", "evidence": [{"quote": "AUTOMA reaches a precision of 91.4 percent and a recall of 84.2 percent.", "page": 3}]}
    return raw


def total(client, h):
    return client.get("/api/game", headers=h).json()["xp"]


def read(client, h, sample_pdfs, name="a.pdf"):
    pid = upload(client, h, sample_pdfs[name].path)
    wait_ready(client, h, pid)
    return pid


# ------------------------------------------------------------------ XP rules
def test_a_card_with_a_hidden_claim_gives_no_xp(client, auth_headers, fake_ai, sample_pdfs):
    """Truth test: the default card has a hidden limitation (the quote is not in the PDF). No points."""
    read(client, auth_headers, sample_pdfs)
    g = client.get("/api/game", headers=auth_headers).json()
    assert g["xp"] == 0 and g["level"]["name"] == "Explorer" and g["recent"] == []


def test_card_ready_gives_10_xp_one_time(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    fake_ai.when("<paper>", verified_card)
    pid = read(client, h, sample_pdfs)
    g = client.get("/api/game", headers=h).json()
    assert g["xp"] == 10 and g["recent"][0]["action"] == "card_ready" and g["have"]["cards"] == 1
    assert [b["code"] for b in g["badges"]] == ["first_card"]
    client.post(f"/api/papers/{pid}/regenerate", headers=h, json={"fresh": True})  # read again: the same card, no new points
    wait_ready(client, h, pid)
    assert total(client, h) == 10
    cid = client.post(f"/api/papers/{pid}/cards", headers=h, json={"focus": "Sysmon logs"}).json()["id"]  # another card of the paper
    for _ in range(100):
        if client.get(f"/api/papers/{pid}/cards/{cid}", headers=h).json()["paper"]["status"] == "ready":
            break
    assert total(client, h) == 20


def test_a_card_that_the_student_fixes_later_gives_xp_then(client, auth_headers, fake_ai, sample_pdfs):
    """The first reading hides the limitation. After "Search again" gives a verified quote, the card is ready."""
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    assert total(client, h) == 0
    fake_ai.when("<paper>", verified_card)
    client.post(f"/api/papers/{pid}/regenerate", headers=h, json={"fresh": True})
    wait_ready(client, h, pid)
    assert total(client, h) == 10


def test_feynman_pass_gives_25_xp_one_time_per_paper(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    low = client.post(f"/api/papers/{pid}/explain", headers=h, json={"text": LOW}).json()
    assert low["score"] < 70 and low["xp_gained"] == 0 and total(client, h) == 0  # a score under 70 gives nothing
    high = client.post(f"/api/papers/{pid}/explain", headers=h, json={"text": HIGH}).json()
    assert high["score"] >= 70 and high["xp_gained"] == 25 and total(client, h) == 25
    again = client.post(f"/api/papers/{pid}/explain", headers=h, json={"text": HIGH}).json()
    assert again["xp_gained"] == 0 and total(client, h) == 25  # no XP for the same paper again
    assert [b["code"] for b in client.get("/api/game", headers=h).json()["badges"]] == ["first_feynman_pass"]


def test_quiz_answer_gives_5_xp_one_time_for_each_question(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    qs = client.post(f"/api/papers/{pid}/quiz", headers=h, json={}).json()["questions"]
    assert client.post(f"/api/quiz/{qs[0]['id']}/answer", headers=h, json={"answer": "I do not know."}).json()["mark"] == "wrong"
    assert total(client, h) == 0  # a wrong answer gives nothing
    assert client.post(f"/api/quiz/{qs[0]['id']}/answer", headers=h, json={"answer": "It reads Sysmon logs."}).json()["mark"] == "correct"
    assert total(client, h) == 5
    client.post(f"/api/quiz/{qs[0]['id']}/answer", headers=h, json={"answer": "Sysmon logs again."})
    assert total(client, h) == 5  # the same question gives XP one time
    client.post(f"/api/quiz/{qs[1]['id']}/answer", headers=h, json={"answer": "The OpTC dataset."})
    assert total(client, h) == 10


def test_link_explained_needs_a_verified_quote_in_both_pdfs(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    a, b = read(client, h, sample_pdfs, "a.pdf"), read(client, h, sample_pdfs, "b.pdf")
    fake_ai.when("You explain how two papers", {"relation": "same_method", "summary": "Both papers talk about methods.", "shared": ["methods"], "differences": "One is about threats.",
                                                "evidence": [{"paper": 1, "quote": "Analysts spend many hours on manual log review and miss attacks.", "page": 1},
                                                             {"paper": 2, "quote": "The pasta must cook for two hours in cold milk.", "page": 2}]})  # the quote of paper 2 is false
    client.post("/api/links/explain", headers=h, json={"a": a, "b": b})
    assert total(client, h) == 0  # truth: one false quote, no points
    fake_ai.reset()
    client.post("/api/links/explain", headers=h, json={"a": a, "b": b, "refresh": True})  # the default answer has a true quote in each PDF
    assert total(client, h) == 10
    client.post("/api/links/explain", headers=h, json={"a": b, "b": a, "refresh": True})
    assert total(client, h) == 10  # the pair gives XP one time, in any order


def test_focus_session_gives_1_xp_for_each_5_minutes_from_20_minutes(client, auth_headers, clock):
    h = auth_headers
    for minutes in (19, 20, 27, 60):
        client.post("/api/focus/start", headers=h, json={"date": "2026-10-09"})
        clock.t += minutes * 60
        client.post("/api/focus/stop", headers=h)
    assert total(client, h) == 0 + 4 + 5 + 12
    assert [e["xp"] for e in client.get("/api/game/events", headers=h).json()][::-1] == [4, 5, 12]


def test_a_win_gives_2_xp_one_time_for_each_day(client, auth_headers, clock):
    h = auth_headers
    client.post("/api/wins", headers=h, json={"text": "I read the method.", "date": "2026-10-09"})
    client.post("/api/wins", headers=h, json={"text": "I read the results.", "date": "2026-10-09"})
    assert total(client, h) == 2
    client.post("/api/wins", headers=h, json={"text": "I wrote the plan.", "date": "2026-10-10"})
    assert total(client, h) == 4


def test_the_same_action_gives_xp_one_time(client):
    db.init()
    assert game.award("win_written", "2026-10-09") is True
    assert game.award("win_written", "2026-10-09") is False
    assert game.award("win_written", "2026-10-10") is True
    assert db.xp_total() == 4
    assert game.award("card_ready", "") is False  # no reference: no points


def test_xp_cannot_come_from_the_client(client, auth_headers):
    """Truth test: no endpoint writes XP. The page can only read the game."""
    h = auth_headers
    xp_routes = [(r.path, sorted(r.methods)) for r in main.app.routes if hasattr(r, "methods") and re.search(r"/xp|xp_events", r.path.lower())]
    assert xp_routes == []
    for r in main.app.routes:  # the only routes under /api/game that write are the settings
        if hasattr(r, "methods") and r.path.startswith("/api/game") and r.methods & {"POST", "PUT", "PATCH", "DELETE"}:
            assert r.path == "/api/game/settings"
    client.post("/api/wins", headers=h, json={"text": "A win.", "date": "2026-10-09", "xp": 9999, "action": "card_ready"})
    client.post("/api/goals", headers=h, json={"text": "A goal.", "date": "2026-10-09", "xp": 9999, "done": True})
    client.put("/api/game/settings", headers=h, json={"weekend_off": True, "xp": 9999})
    assert total(client, h) == 2  # only the win of the day
    assert client.post("/api/game", headers=h, json={"xp": 5}).status_code == 405
    assert client.post("/api/xp", headers=h, json={"xp": 5}).status_code in (404, 405)


# ------------------------------------------------------------------ levels
def add_events(action, n, start=0):
    for i in range(n):
        db.xp_add(action, f"x{start + i}", 10, DAY, "2026-10-09")


def test_a_level_needs_xp_and_the_skill(client):
    db.init()
    assert game.level_info(0, game.counts())["name"] == "Explorer"
    add_events("card_ready", 5)  # 50 XP, 5 cards
    add_events("feynman_pass", 3)  # 30 XP more, 3 passes
    info = game.level_info(db.xp_total(), game.counts())
    assert db.xp_total() == 80 and info["name"] == "Explorer"  # the skill is there, but the XP is not (100 needed)
    assert info["next"]["name"] == "Reader" and info["next"]["xp_needed"] == 20
    add_events("link_explained", 2)
    assert game.level_info(db.xp_total(), game.counts())["name"] == "Reader"
    # a lot of XP without the skill: no level
    db.xp_add("win_written", "big", 5000, DAY, "2026-10-09")
    assert game.level_info(5000, {"cards": 5, "feynman": 2, "links": 0, "critical": None, "gaps": None, "sections": None, "outline": None})["name"] == "Explorer"
    info = game.level_info(5000, game.counts())
    assert info["name"] == "Reader" and info["next"]["name"] == "Critic"
    assert info["next"]["conditions"] == [{"text": "critical reading checks", "have": 0, "need": 10, "available": True}]  # the quality check exists now (Sprint 09)


def test_levels_and_the_game_page(client, auth_headers):
    h = auth_headers
    g = client.get("/api/game", headers=h).json()
    assert g["level"]["names"] == ["Explorer", "Reader", "Critic", "Connector", "Author", "Doctor"] and g["level"]["name"] == "Explorer"
    assert g["level"]["next"]["conditions"][0]["text"] == "cards with checked quotes" and g["level"]["next"]["conditions"][1]["need"] == 3


# ------------------------------------------------------------------ the kind streak
def days(*d):
    return {f"2026-10-{n:02d}" for n in d}


def test_streak_with_a_rest_token():
    """Monday, Tuesday, (Wednesday: rest token), Thursday: the streak is 4."""
    s = game.streak(days(5, 6, 8), "2026-10-08")
    assert s["current"] == 4 and s["rest_days"] == ["2026-10-07"] and s["tokens_left"] == 1 and s["today_done"] is True


def test_streak_ends_without_a_token():
    """Two rest tokens each week. The third missing day in the same week ends the streak."""
    s = game.streak(days(5), "2026-10-09", weekend_off=False)  # Mon xp, Tue Wed (tokens), Thu (no token): the streak ends. Fri is today.
    assert s["current"] == 0 and s["best"] == 3 and s["tokens_left"] == 0


def test_streak_with_the_weekend_off():
    """Friday, then Saturday and Sunday off, then Monday: not broken, no token used."""
    s = game.streak(days(2, 5, 6) | {"2026-10-09", "2026-10-12"}, "2026-10-12", weekend_off=True)
    # Fri Oct 2 xp. Sat and Sun: off. Mon 5 and Tue 6: xp. Wed 7 and Thu 8: two tokens. Fri 9 xp. Sat and Sun: off. Mon 12 xp (the new week has 2 tokens).
    assert s["current"] == 7 and s["tokens_left"] == 2
    s2 = game.streak({"2026-10-09", "2026-10-12"}, "2026-10-12", weekend_off=True)  # Friday and Monday
    assert s2["current"] == 2 and s2["rest_days"] == []
    s3 = game.streak({"2026-10-09", "2026-10-12"}, "2026-10-12", weekend_off=False)  # the weekend uses 2 tokens (the days are in 1 week: Sat Sun)
    assert s3["current"] == 4 and s3["rest_days"] == ["2026-10-10", "2026-10-11"]


def test_today_without_xp_does_not_end_the_streak():
    s = game.streak(days(7, 8), "2026-10-09")
    assert s["current"] == 2 and s["today_done"] is False  # today is not over


def test_tokens_start_again_each_week():
    s = game.streak(days(5, 8, 12), "2026-10-12", weekend_off=False)  # Mon xp, Tue and Wed tokens, Thu xp: 4. Fri: no token left, the streak ends. Mon 12: a new start.
    assert s["best"] == 4 and s["current"] == 1
    w = game.streak({"2026-10-05", "2026-10-12"}, "2026-10-12", weekend_off=False)  # week 1: Tue Wed tokens; Thu Fri: no token left -> ends
    assert w["current"] == 1  # the new week starts a new streak with Monday 12


def test_a_lost_streak_gets_a_kind_message(client, auth_headers, clock):
    h = auth_headers
    db.init()
    db.xp_add("win_written", "a", 2, DAY - 20 * 86400, "2026-09-19")
    clock.t = DAY
    g = client.get("/api/game", headers=h, params={"date": "2026-10-09"}).json()
    assert g["streak"]["current"] == 0 and g["streak"]["best"] >= 1 and g["streak"]["message"] == "Welcome back. Your knowledge is still here."
    fresh = game.streak_message({"current": 0, "best": 0, "tokens_left": 2, "today_done": False}, False)
    assert "first point" in fresh


def test_streak_setting(client, auth_headers):
    h = auth_headers
    assert client.get("/api/game", headers=h).json()["streak"]["weekend_off"] is True
    assert client.put("/api/game/settings", headers=h, json={"weekend_off": False}).json() == {"weekend_off": False}
    assert client.get("/api/game", headers=h).json()["streak"]["weekend_off"] is False


def test_the_day_of_an_event_follows_the_time_zone_of_the_student(client, auth_headers, clock):
    h = auth_headers
    clock.t = dt.datetime(2026, 10, 9, 1, 0, tzinfo=dt.timezone.utc).timestamp()  # 01:00 in UTC
    client.get("/api/game", headers=h, params={"tz": -300})  # the student is at UTC-5: it is still the 8th
    client.post("/api/wins", headers=h, json={"text": "A late win.", "date": "2026-10-08"})
    assert [e["date"] for e in client.get("/api/game/events", headers=h).json()] == ["2026-10-08"]


# ------------------------------------------------------------------ badges, records, own rewards
def test_badges_are_rare_and_given_one_time(client, auth_headers):
    h = auth_headers
    db.init()
    codes = lambda: [b["code"] for b in client.get("/api/game", headers=h).json()["badges"]]
    for i in range(7):  # 7 days in a row
        db.xp_add("win_written", f"d{i}", 2, DAY, f"2026-10-0{i + 1}")
    game.refresh()
    assert codes() == ["streak_7"]
    game.refresh()
    assert codes() == ["streak_7"]  # one time
    add_events("card_ready", 100)
    game.refresh()
    assert set(codes()) == {"streak_7", "first_card", "cards_100"}
    missing = {b["code"] for b in client.get("/api/game", headers=h).json()["badges_missing"]}
    assert missing == {"first_feynman_pass", "streak_30", "year_1"}


def test_the_year_badge(client, auth_headers):
    db.init()
    db.xp_add("win_written", "old", 2, DAY - 400 * 86400, "2025-09-04")
    db.xp_add("win_written", "new", 2, DAY, "2026-10-09")
    game.refresh()
    assert "year_1" in [b["code"] for b in db.badges_list()]


def test_records_compare_the_student_with_his_or_her_own_past(client, auth_headers):
    h = auth_headers
    db.init()
    for date, n in (("2026-10-09", 10), ("2026-10-06", 5), ("2026-10-01", 20), ("2026-09-20", 7)):  # Fri, Tue (this week), Thu (last week), last month
        db.xp_add("card_ready", date, n, DAY, date)
    r = client.get("/api/game", headers=h, params={"date": "2026-10-09"}).json()["records"]
    assert r["xp"] == {"this_week": 15, "last_week": 20, "this_month": 35, "last_month": 7}
    assert r["cards"]["this_week"] == 2 and r["cards"]["last_week"] == 1
    assert set(r) == {"xp", "cards", "focus_minutes"}  # no other student, no ranking


def test_own_rewards(client, auth_headers):
    h = auth_headers
    r = client.post("/api/rewards", headers=h, json={"text": "A dinner out", "condition": "level:2"}).json()
    assert r["earned_at"] is None and r["claimed"] is False
    assert client.post(f"/api/rewards/{r['id']}/claim", headers=h).status_code == 400  # not earned yet
    add_events("card_ready", 5)
    add_events("feynman_pass", 3)
    add_events("link_explained", 2)
    game.refresh()
    got = client.get("/api/game", headers=h).json()
    assert got["level"]["name"] == "Reader" and got["rewards"][0]["earned_at"] is not None
    assert client.post(f"/api/rewards/{r['id']}/claim", headers=h).json()["claimed"] is True
    assert client.post("/api/rewards", headers=h, json={"text": "Coffee", "condition": "xp:1"}).json()["earned_at"] is not None  # earned at once
    for bad in ("level", "level:x", "money:5", "xp:0", ""):
        assert client.post("/api/rewards", headers=h, json={"text": "X", "condition": bad}).status_code == 400
    assert client.post("/api/rewards", headers=h, json={"text": " ", "condition": "xp:5"}).status_code == 400
    assert client.delete(f"/api/rewards/{r['id']}", headers=h).status_code == 200
    assert client.delete(f"/api/rewards/{r['id']}", headers=h).status_code == 404
    assert client.post("/api/rewards/nope/claim", headers=h).status_code == 404


# ------------------------------------------------------------------ switch, backup, kind words
def test_a_switched_off_game_gives_no_xp_and_blocks_its_endpoints(client, auth_headers, clock):
    h = auth_headers
    client.put("/api/features", headers=h, json={"features": {"game": False}})
    client.post("/api/wins", headers=h, json={"text": "A win.", "date": "2026-10-09"})
    assert client.get("/api/game", headers=h).status_code == 403
    assert client.post("/api/rewards", headers=h, json={"text": "X", "condition": "xp:5"}).status_code == 403
    assert client.get("/api/wins", headers=h).status_code == 200  # the rest of the app works
    client.put("/api/features", headers=h, json={"features": {"game": True}})
    assert total(client, h) == 0  # nothing was given while the game was off


def test_backup_keeps_points_badges_and_rewards(client, auth_headers):
    h = auth_headers
    client.post("/api/wins", headers=h, json={"text": "A win.", "date": "2026-10-09"})
    add_events("card_ready", 1)
    game.refresh()
    r = client.post("/api/rewards", headers=h, json={"text": "Coffee", "condition": "xp:1"}).json()
    backup = client.get("/api/export", headers=h).json()
    assert len(backup["xp_events"]) == 2 and [b["code"] for b in backup["badges"]] == ["first_card"] and [x["id"] for x in backup["rewards"]] == [r["id"]]
    with db.conn() as c:
        c.execute("DELETE FROM xp_events")
        c.execute("DELETE FROM badges")
        c.execute("DELETE FROM rewards")
    client.post("/api/import", headers=h, json=backup)
    client.post("/api/import", headers=h, json=backup)  # a second import adds nothing
    g = client.get("/api/game", headers=h).json()
    assert g["xp"] == 12 and [b["code"] for b in g["badges"]] == ["first_card"] and len(g["rewards"]) == 1 and g["rewards"][0]["earned_at"] is not None


def test_the_texts_of_the_game_are_kind():
    """Rule 5: no guilt, no ranking. No text of the game has a word of blame, and the game has no comparison with other people."""
    texts = [game.streak_message({"current": c, "best": 5, "tokens_left": t, "today_done": d}, True) for c in (0, 1, 5) for t in (0, 1, 2) for d in (True, False)]
    texts += [h for _, h in game.BADGES.values()] + [n for n, _ in game.BADGES.values()]
    assert not re.search(r"\b(lost|lose|missed|behind|lazy|failed|late|shame|only|ranking|leaderboard|others)\b", " ".join(texts), re.I)
    source = open(game.__file__, encoding="utf-8").read()
    assert "leaderboard" not in source.lower().replace("no ranking", "") or "no ranking" in source


def test_the_avatar_switch_is_in_the_feature_list_and_can_be_switched_off(client, auth_headers):
    h = auth_headers
    names = {f["name"]: f["enabled"] for f in client.get("/api/features", headers=h).json()}
    assert names["avatar"] is True
    client.put("/api/features", headers=h, json={"features": {"avatar": False}})
    assert {f["name"]: f["enabled"] for f in client.get("/api/features", headers=h).json()}["avatar"] is False
