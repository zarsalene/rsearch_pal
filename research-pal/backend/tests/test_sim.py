"""The Semester Simulator. The rules, the link to the real work, the balance (thousands of played semesters) and the server."""
import json

import pytest

from app import db, game, sim
import sim_policies as P
from helpers import upload, wait_ready


@pytest.fixture(autouse=True)
def no_quests(monkeypatch):
    monkeypatch.setattr(game, "QUESTS_PER_WEEK", 0)  # a quest bonus would change the XP numbers of these tests


def fresh(seed=1, real=None):
    s = sim.new_state(seed, real)
    s["coming"] = None  # no event, so a test is not about the luck of the draw
    return s


# ---------- the rules ----------
def test_the_same_seed_and_the_same_choices_give_the_same_semester():
    a, b, c = P.play(P.balanced, 7), P.play(P.balanced, 7), P.play(P.balanced, 8)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert json.dumps(a, sort_keys=True) != json.dumps(c, sort_keys=True)


def test_the_state_is_plain_data():
    s = sim.new_state(3, P.REAL)
    assert json.loads(json.dumps(s)) == s


def test_an_action_costs_action_points_and_energy():
    s = fresh()
    sim.act(s, "read")
    assert s["ap"] == 4 and s["energy"] == 62 and s["chapters"]["review"] > 0
    sim.act(s, "experiment")
    assert s["ap"] == 2
    with pytest.raises(sim.SimError, match="Not enough action points"):
        s["ap"] = 1
        sim.act(s, "write")


def test_rest_gives_energy_and_morale():
    s = fresh()
    s["energy"], s["morale"] = 30, 50
    sim.act(s, "rest")
    assert s["energy"] == 52 and s["morale"] == 54


def test_a_tired_student_does_less():
    rested, tired = fresh(), fresh()
    tired["energy"] = 12
    sim.act(rested, "read")
    sim.act(tired, "read")
    assert tired["chapters"]["review"] < rested["chapters"]["review"]


def test_you_cannot_write_more_than_you_know():
    s = fresh()
    for _ in range(2):
        s["ap"] = 5
        s["energy"] = 90
        sim.act(s, "write")
    assert s["chapters"]["writing"] == 20  # with no reading, the limit is 20
    s["ap"] = 5
    text = sim.act(s, "write")
    assert s["chapters"]["writing"] == 20 and "cannot write more than you know" in text


def test_an_event_must_be_answered_before_the_next_action():
    s = sim.new_state(1)
    s["coming"] = {"id": "praise"}
    sim.end_week(s)
    assert s["event"]["id"] == "praise" and sim.can(s, "read") == "Answer the event first."
    with pytest.raises(sim.SimError):
        sim.act(s, "read")
    with pytest.raises(sim.SimError):
        sim.end_week(s)
    sim.choose(s, "thanks")
    assert s["event"] is None and s["week"] == 2


def test_a_wrong_choice_is_refused_and_the_event_stays():
    s = sim.new_state(1)
    s["coming"] = {"id": "praise"}
    sim.end_week(s)
    with pytest.raises(sim.SimError):
        sim.choose(s, "nonsense")
    assert s["event"] is not None


def test_the_week_ends_and_the_next_week_starts():
    s = fresh()
    sim.act(s, "read")
    sim.end_week(s)
    assert s["week"] == 2 and s["ap"] == 5 and s["energy"] == 62 + 3 * 4 + 8  # the unused action points are quiet time


def test_a_milestone_with_enough_work_pleases_the_supervisor():
    s = fresh()
    s["week"], s["chapters"]["review"] = 4, 40
    trust = s["trust"]
    sim.end_week(s)
    assert s["milestones"]["4"] is True and s["trust"] == trust + 6


def test_a_missed_milestone_worries_the_supervisor_but_the_game_goes_on():
    s = fresh()
    s["week"] = 4
    trust = s["trust"]
    sim.end_week(s)
    assert s["milestones"]["4"] is False and s["trust"] == trust - 6 and s["status"] == "active" and s["week"] == 5


def test_burnout_ends_the_semester_kindly():
    s = fresh()
    s["morale"], s["chapters"]["writing"], s["chapters"]["review"] = 1, 100, 100
    sim.end_week(s)
    r = s["report"]
    assert s["status"] == "burnout" and r["burnout"] is True and r["grade"] == "C"  # the grade is not better than C
    assert "Your progress is safe" in r["text"] and "Rest" in r["text"]


def test_an_exhausted_week_has_fewer_action_points_but_no_lost_progress():
    s = fresh()
    s["energy"], s["ap"], s["chapters"]["review"] = 0, 0, 50
    sim.end_week(s)
    assert s["ap"] == sim.AP_TIRED and s["energy"] == 35 and s["chapters"]["review"] == 50


def test_the_semester_has_12_weeks_and_a_report():
    s = P.play(P.rest_only, 5)
    assert s["status"] == "done" and s["week"] == 12 and s["report"]["weeks_done"] == 12
    assert sim.grade_for(s["report"]["progress"]) == s["report"]["grade"] == "D"
    with pytest.raises(sim.SimError):
        sim.act(s, "read")


def test_the_grades():
    assert [sim.grade_for(p) for p in (0, 39, 40, 55, 70, 85, 100)] == ["D", "D", "C", "B", "A", "S", "S"]
    assert sim.grade_for(95, burnout=True) == "C" and sim.grade_for(20, burnout=True) == "D"


def test_a_second_chance_rolls_again_one_time():
    s = fresh()
    s["armed"] = True
    assert sim._roll(s, 0.0, "x") is False and s["armed"] is False  # the chance was used, the roll failed again
    assert "Second chance" in s["log"][-1]["text"]
    s["armed"] = True
    assert sim._roll(s, 1.0, "y") is True and s["armed"] is True  # no fail: the chance stays


def test_coffee_and_second_chance_need_the_inventory(client):
    s = fresh()
    with pytest.raises(sim.SimError, match="do not have"):
        sim.use_boost(s, "coffee")
    db.purchase_add("coffee", 20)
    s["energy"] = 40
    sim.use_boost(s, "coffee")
    assert s["energy"] == 65 and game.inventory()["boosts"].get("coffee", 0) == 0
    with pytest.raises(sim.SimError):
        sim.use_boost(s, "coffee")  # one coffee for each week
    with pytest.raises(sim.SimError):
        sim.use_boost(s, "tea")


# ---------- the real student ----------
REAL = P.REAL


def test_the_real_work_gives_the_starting_knowledge():
    assert sim.new_state(1, None)["knowledge"] == 10
    assert sim.new_state(1, REAL)["knowledge"] == 23 and sim.new_state(1, REAL)["real"]["mastered"] == 1


def test_the_odds_of_a_reviewer_follow_the_real_rank():
    s = sim.new_state(1, REAL)
    odds = [sim._odds(s, p) for p in s["papers"]]
    assert odds[0] > odds[1] > odds[2]  # mastered > read > seen
    sim.act(s, "study", "p3")  # a paper that you study in the simulation is a safe answer
    assert sim._odds(s, s["papers"][2]) >= 0.75


def test_study_needs_one_of_your_papers():
    s = sim.new_state(1, None)
    assert sim.can(s, "study") == "Add a paper in the library first."
    s = sim.new_state(1, REAL)
    with pytest.raises(sim.SimError):
        sim.act(s, "study", "not-a-paper")


def test_a_reviewer_who_beats_you_names_a_real_paper_in_the_report(monkeypatch):
    s = sim.new_state(1, REAL)
    s["event"] = {"id": "reviewer", "paper": dict(s["papers"][2])}  # the paper that you only saw
    monkeypatch.setattr(sim, "_roll", lambda s, p, tag: False)
    text = sim.choose(s, "answer")
    assert "Paper three" in text and s["misses"] == [{"id": "p3", "title": "Paper three", "rank": 0}]
    sim._finish(s)
    assert s["report"]["weak_spots"][0]["title"] == "Paper three"
    assert any("Fight the boss of \"Paper three\"" in step for step in s["report"]["next_steps"])


def test_a_reviewer_is_kind_to_a_mastered_paper(monkeypatch):
    s = sim.new_state(1, REAL)
    s["event"] = {"id": "reviewer", "paper": dict(s["papers"][0])}
    monkeypatch.setattr(sim, "_roll", lambda s, p, tag: True)
    w = s["chapters"]["writing"]
    sim.choose(s, "answer")
    assert s["chapters"]["writing"] == w + 8 and s["misses"] == []


def test_the_reviewer_hint_shows_the_odds():
    s = sim.new_state(1, REAL)
    s["event"] = {"id": "reviewer", "paper": dict(s["papers"][0])}
    v = sim._event_view(s)
    assert v["choices"][0]["hint"] == "Good odds" and "mastered" in v["text"]
    s["event"]["paper"] = dict(s["papers"][2])
    assert sim._event_view(s)["choices"][0]["hint"] == "Poor odds"


def test_meeting_your_supervisor_shows_the_coming_event():
    s = sim.new_state(1, None)
    s["coming"] = {"id": "illness"}
    assert sim.public("x", s, "active")["coming"] is None
    sim.act(s, "meet")
    assert sim.public("x", s, "active")["coming"]["title"] == "You feel sick"


def test_the_seed_is_never_shown():
    assert "seed" not in sim.public("x", sim.new_state(99), "active")


# ---------- the balance: thousands of semesters ----------
def test_balance_a_careful_student_does_well_and_a_reckless_one_does_not():
    careful, careful_real = P.stats(lambda i: P.balanced, 120), P.stats(lambda i: P.balanced, 120, REAL)
    random_s, rest, grind = P.stats(P.random_player, 120), P.stats(lambda i: P.rest_only, 60), P.stats(lambda i: P.grind, 120)
    assert 62 <= careful["mean"] <= 82 and careful["burnout"] < 0.05
    assert careful["grades"]["S"] / 120 < 0.05  # S is rare for a new student
    assert careful_real["mean"] >= careful["mean"] + 5  # real work is worth something
    assert random_s["mean"] <= careful["mean"] - 20  # planning is worth something
    assert rest["mean"] < 5  # no work, no thesis
    assert grind["burnout"] >= 0.5 and grind["mean"] < careful["mean"] - 30  # never to rest is the way to burnout


def test_balance_every_policy_always_finishes():
    for policy in (P.balanced, P.rest_only, P.grind):
        for seed in range(15):
            assert P.play(policy, seed, REAL)["status"] in ("done", "burnout")


# ---------- the server ----------
def start(client, h):
    r = client.post("/api/sim", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def finish(client, h, sid):
    for _ in range(80):
        run = client.get(f"/api/sim/{sid}", headers=h).json()
        if run["status"] != "active":
            return run
        if run["event"]:
            assert client.post(f"/api/sim/{sid}/choose", headers=h, json={"choice": run["event"]["choices"][0]["id"]}).status_code == 200
        else:
            assert client.post(f"/api/sim/{sid}/end-week", headers=h).status_code == 200
    raise AssertionError("the semester did not end")


def test_the_simulation_needs_a_login_and_the_switch(client, auth_headers):
    assert client.get("/api/sim").status_code == 401 and client.post("/api/sim").status_code == 401
    client.put("/api/features", headers=auth_headers, json={"features": {"game": False}})
    assert client.get("/api/sim", headers=auth_headers).status_code == 403
    client.put("/api/features", headers=auth_headers, json={"features": {"game": True}})
    assert client.get("/api/sim", headers=auth_headers).status_code == 200


def test_a_semester_on_the_server(client, auth_headers):
    assert client.get("/api/sim", headers=auth_headers).json() == {"run": None, "records": {"runs": 0, "best": 0, "best_grade": "", "last": None}}
    run = start(client, auth_headers)
    assert run["status"] == "active" and run["week"] == 1 and run["ap"] == 5 and "seed" not in json.dumps(run)
    assert [a["id"] for a in run["actions"]][:3] == ["read", "study", "experiment"]
    r = client.post(f"/api/sim/{run['id']}/act", headers=auth_headers, json={"action": "read"}).json()
    assert r["run"]["ap"] == 4 and r["run"]["chapters"]["review"] > 0 and r["say"].startswith("You read papers")
    assert client.get("/api/sim", headers=auth_headers).json()["run"]["ap"] == 4  # the state lives on the server


def test_the_server_refuses_bad_moves(client, auth_headers):
    sid = start(client, auth_headers)["id"]
    act = lambda body: client.post(f"/api/sim/{sid}/act", headers=auth_headers, json=body)
    assert act({"action": "fly"}).status_code == 400
    assert act({"action": "study", "arg": "x"}).status_code == 409  # no paper in the library
    assert client.post(f"/api/sim/{sid}/choose", headers=auth_headers, json={"choice": "x"}).status_code == 409  # no event
    assert client.post("/api/sim/nope/end-week", headers=auth_headers).status_code == 404
    for _ in range(2):
        act({"action": "experiment"})
    assert act({"action": "read"}).status_code == 200 and act({"action": "write"}).status_code == 409  # no action points left


def test_a_full_semester_gives_a_report_and_a_record_but_no_xp(client, auth_headers):
    before = client.get("/api/game", headers=auth_headers).json()["xp"]
    sid = start(client, auth_headers)["id"]
    run = finish(client, auth_headers, sid)
    assert run["report"]["grade"] in "SABCD" and run["report"]["weeks_done"] == 12 and run["event"] is None
    cur = client.get("/api/sim", headers=auth_headers).json()
    assert cur["run"] is None and cur["records"]["runs"] == 1 and cur["records"]["last"]["progress"] == run["report"]["progress"]
    assert client.post(f"/api/sim/{sid}/end-week", headers=auth_headers).status_code == 409  # over
    assert client.get("/api/game", headers=auth_headers).json()["xp"] == before  # a game is not work: no XP


def test_a_new_semester_closes_the_old_one_without_a_penalty(client, auth_headers):
    a = start(client, auth_headers)["id"]
    b = start(client, auth_headers)["id"]
    assert a != b and db.sim_get(a)["status"] == "abandoned" and client.get("/api/sim", headers=auth_headers).json()["run"]["id"] == b


def test_the_semester_starts_from_the_real_work(client, auth_headers, fake_ai, sample_pdfs):
    new = start(client, auth_headers)
    assert new["real"]["knowledge"] == 10 and new["papers"] == []
    pid = upload(client, auth_headers, sample_pdfs["a.pdf"].path)
    wait_ready(client, auth_headers, pid)
    run = start(client, auth_headers)
    assert run["real"]["knowledge"] == 12 and run["real"]["read"] == 1  # one paper that you read
    assert run["papers"][0]["title"].startswith("AUTOMA") and run["papers"][0]["rank_name"] == "read"
    act = client.post(f"/api/sim/{run['id']}/act", headers=auth_headers, json={"action": "study", "arg": pid}).json()
    assert act["run"]["papers"][0]["prepared"] is True


def test_the_shop_boosts_work_in_the_simulation(client, auth_headers):
    db.xp_add("eureka", "gift", 100)
    run = start(client, auth_headers)
    assert client.post(f"/api/sim/{run['id']}/boost", headers=auth_headers, json={"item": "coffee"}).status_code == 409  # nothing in the bag
    assert client.post("/api/game/shop/coffee", headers=auth_headers).status_code == 200
    assert client.get("/api/game", headers=auth_headers).json()["inventory"]["boosts"] == {"coffee": 1}
    client.post(f"/api/sim/{run['id']}/act", headers=auth_headers, json={"action": "experiment"})
    r = client.post(f"/api/sim/{run['id']}/boost", headers=auth_headers, json={"item": "coffee"}).json()
    assert r["run"]["coffee_used"] is True and r["run"]["boosts"] == {"coffee": 0}
    assert client.get("/api/game", headers=auth_headers).json()["sparks"] == 80  # 100 - 20
