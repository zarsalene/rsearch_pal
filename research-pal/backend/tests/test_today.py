"""Sprint 04: the Today page. Goals, wins, focus timer, next best action. No AI call."""
import pytest

from app import cards, db, today
from helpers import upload, wait_ready

DAY = "2026-10-09"


@pytest.fixture
def clock(monkeypatch):
    """A clock that the test controls. clock.t is the time in seconds."""
    class Clock:
        t = 1_000_000.0
    monkeypatch.setattr(db, "now", lambda: Clock.t)
    return Clock


def read(client, h, sample_pdfs, name="a.pdf"):
    pid = upload(client, h, sample_pdfs[name].path)
    wait_ready(client, h, pid)
    return pid


# ------------------------------------------------------------------ next best action
def test_next_action_with_no_paper_asks_for_a_first_paper(client, auth_headers):
    got = client.get("/api/today/next", headers=auth_headers, params={"date": DAY}).json()
    assert got["kind"] == "add_paper" and "first paper" in got["text"]


def test_next_action_rule_1_a_field_that_was_not_found(client, auth_headers, fake_ai, sample_pdfs):
    pid = read(client, auth_headers, sample_pdfs)
    card = db.get_card(pid)
    card["fields"]["result"] = {"answer": cards.NOT_FOUND, "status": "not_found", "kind": "paper", "evidence": [], "draft": "", "unverified_numbers": [], "edited": False}
    db.save_card(pid, card)
    db.add_sub_question("What data exists?")  # rule 2 would also match. Rule 1 comes first.
    got = client.get("/api/today/next", headers=auth_headers, params={"date": DAY}).json()
    assert got["kind"] == "fill" and got["paper_id"] == pid and got["card_id"] == "" and "Search the paper again" in got["text"] and sample_pdfs["a.pdf"].title in got["text"]


def test_next_action_rule_2_a_sub_question_with_0_or_1_paper(client, auth_headers, fake_ai, sample_pdfs):
    a, b = read(client, auth_headers, sample_pdfs, "a.pdf"), read(client, auth_headers, sample_pdfs, "b.pdf")
    s1, s2 = db.add_sub_question("What data exists?")["id"], db.add_sub_question("Which method works best?")["id"]
    db.set_tags(a, "", [s1])
    db.set_tags(b, "", [s1])  # SQ1 has 2 papers. SQ2 has 0.
    got = client.get("/api/today/next", headers=auth_headers, params={"date": DAY}).json()
    assert got["kind"] == "find_paper" and got["sub_question_id"] == s2 and "SQ2" in got["text"] and "0 papers" in got["text"]
    db.set_tags(a, "", [s1, s2])  # SQ2 has 1 paper: this is still a gap
    assert "1 paper." in client.get("/api/today/next", headers=auth_headers, params={"date": DAY}).json()["text"]
    db.set_tags(b, "", [s1, s2])  # both have 2 papers
    assert client.get("/api/today/next", headers=auth_headers, params={"date": DAY}).json()["kind"] == "explain"


def test_next_action_rule_3_and_4(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    got = client.get("/api/today/next", headers=h, params={"date": DAY}).json()
    assert got["kind"] == "explain" and got["paper_id"] == pid and sample_pdfs["a.pdf"].title in got["text"]
    db.explanation_add(pid, "", "My text about the paper.", {"claims": []}, 50)  # the student explained the paper
    got = client.get("/api/today/next", headers=h, params={"date": DAY}).json()
    assert got["kind"] == "win" and "win of the day" in got["text"]
    client.post("/api/wins", headers=h, json={"text": "I read the method.", "date": DAY})
    got = client.get("/api/today/next", headers=h, params={"date": DAY}).json()
    assert got["kind"] == "rest" and "Rest is part of the work" in got["text"] and got["button"] == ""
    assert client.get("/api/today/next", headers=h, params={"date": "2026-10-10"}).json()["kind"] == "win"  # a new day, a new win


# ------------------------------------------------------------------ goals
def test_goals(client, auth_headers):
    h = auth_headers
    ids = [client.post("/api/goals", headers=h, json={"text": t, "kind": k, "target": n, "date": DAY}).json()["id"]
           for t, k, n in (("Read 1 paper", "papers", 1), ("Write 200 words", "words", 200), ("1 focus session", "focus", 1))]
    client.put(f"/api/goals/{ids[0]}", headers=h, json={"done": True})
    t = client.get("/api/today", headers=h, params={"date": DAY}).json()
    assert (t["goals_done"], t["goals_total"]) == (1, 3) and [g["done"] for g in t["goals"]] == [True, False, False]
    assert [g["kind"] for g in t["goals"]] == ["papers", "words", "focus"]
    assert client.get("/api/goals", headers=h, params={"date": "2026-10-10"}).json() == []  # the goals of another day
    g = client.put(f"/api/goals/{ids[1]}", headers=h, json={"text": "  Write   300 words ", "target": 300}).json()
    assert g["text"] == "Write 300 words" and g["target"] == 300 and g["done"] is False
    client.put(f"/api/goals/{ids[0]}", headers=h, json={"done": False})  # a student can take the check away
    assert client.get("/api/today", headers=h, params={"date": DAY}).json()["goals_done"] == 0
    assert client.delete(f"/api/goals/{ids[2]}", headers=h).status_code == 200
    assert client.delete(f"/api/goals/{ids[2]}", headers=h).status_code == 404
    assert client.put("/api/goals/nope", headers=h, json={"done": True}).status_code == 404


def test_goal_input_is_checked(client, auth_headers):
    h = auth_headers
    post = lambda **b: client.post("/api/goals", headers=h, json={"date": DAY, **b}).status_code
    assert post(text="  ") == 400 and post(text="x" * 201) == 400 and post(text="Read", kind="nope") == 400
    assert client.post("/api/goals", headers=h, json={"text": "Read", "date": "9 Oct"}).status_code == 400
    assert client.put("/api/goals/x", headers=h, json={"text": " "}).status_code in (400, 404)
    for i in range(today.MAX_GOALS_PER_DAY):
        assert post(text=f"Goal {i}") == 200
    r = client.post("/api/goals", headers=h, json={"text": "One more", "date": DAY})
    assert r.status_code == 400 and "Small goals are good" in r.json()["detail"]
    assert client.get("/api/today", headers=h).status_code == 200  # no date: the date of the server


# ------------------------------------------------------------------ wins
def test_wins_and_the_past_win(client, auth_headers):
    h = auth_headers
    assert client.get("/api/today", headers=h, params={"date": DAY}).json()["past_win"] is None
    old = client.post("/api/wins", headers=h, json={"text": "I fixed my method chapter.", "date": "2026-10-01"}).json()
    client.post("/api/wins", headers=h, json={"text": "I read two papers.", "date": "2026-10-05"})
    mine = client.post("/api/wins", headers=h, json={"text": "I wrote the plan.", "date": DAY}).json()
    t = client.get("/api/today", headers=h, params={"date": DAY}).json()
    assert t["win_today"]["id"] == mine["id"] and t["past_win"]["date"] in ("2026-10-01", "2026-10-05")  # a past win, never the win of today
    assert [w["text"] for w in client.get("/api/wins", headers=h, params={"limit": 5, "before": DAY}).json()] == ["I read two papers.", "I fixed my method chapter."]  # newest first
    assert len(client.get("/api/wins", headers=h, params={"limit": 1}).json()) == 1
    assert client.post("/api/wins", headers=h, json={"text": " ", "date": DAY}).status_code == 400
    assert client.post("/api/wins", headers=h, json={"text": "x" * 301, "date": DAY}).status_code == 400
    assert client.delete(f"/api/wins/{old['id']}", headers=h).status_code == 200
    assert client.delete(f"/api/wins/{old['id']}", headers=h).status_code == 404


# ------------------------------------------------------------------ focus timer
def test_focus_start_and_stop_count_the_minutes_with_the_clock_of_the_server(client, auth_headers, clock):
    h = auth_headers
    s = client.post("/api/focus/start", headers=h, json={"task_text": "Read the method", "planned_minutes": 25, "date": DAY, "minutes": 999}).json()  # "minutes" is ignored
    assert s["end"] is None and s["planned"] == 25 and s["task_text"] == "Read the method" and s["minutes"] == 0
    assert client.get("/api/focus/active", headers=h).json()["session"]["id"] == s["id"]
    assert client.get("/api/today", headers=h, params={"date": DAY}).json()["active_session"]["id"] == s["id"]
    clock.t += 25 * 60 + 20
    done = client.post("/api/focus/stop", headers=h).json()
    assert done["minutes"] == 25 and done["end"] is not None
    assert client.get("/api/focus/active", headers=h).json()["session"] is None
    clock.t += 60
    client.post("/api/focus/start", headers=h, json={"date": DAY})
    clock.t += 10 * 60
    client.post("/api/focus/stop", headers=h)
    day = client.get("/api/focus", headers=h, params={"date": DAY}).json()
    assert day["minutes"] == 35 and len(day["sessions"]) == 2
    assert client.get("/api/today", headers=h, params={"date": DAY}).json()["focus_minutes"] == 35
    assert client.get("/api/today", headers=h, params={"date": "2026-10-10"}).json()["focus_minutes"] == 0


def test_focus_errors(client, auth_headers, clock, fake_ai, sample_pdfs):
    h = auth_headers
    r = client.post("/api/focus/stop", headers=h)
    assert r.status_code == 400 and r.json()["detail"] == "No focus session is running."  # stop without start
    pid = read(client, h, sample_pdfs)
    client.post("/api/focus/start", headers=h, json={"paper_id": pid, "date": DAY})
    r = client.post("/api/focus/start", headers=h, json={"date": DAY})
    assert r.status_code == 400 and "running" in r.json()["detail"]
    clock.t += 5
    assert client.post("/api/focus/stop", headers=h).json()["minutes"] == 0  # a very short session
    assert client.post("/api/focus/start", headers=h, json={"planned_minutes": 0}).status_code == 400
    assert client.post("/api/focus/start", headers=h, json={"planned_minutes": 181}).status_code == 400
    assert client.post("/api/focus/start", headers=h, json={"paper_id": "nope"}).status_code == 400
    client.post("/api/focus/start", headers=h, json={"date": DAY})
    clock.t += 3 * 24 * 3600  # the student forgot to stop it: the minutes have a limit
    assert client.post("/api/focus/stop", headers=h).json()["minutes"] == today.MAX_SESSION_MINUTES


def test_the_today_page_gives_the_thesis(client, auth_headers):
    h = auth_headers
    client.put("/api/project", headers=h, json={"title": "Validation agents", "question": "Do validation agents reduce false hypotheses?"})
    t = client.get("/api/today", headers=h, params={"date": DAY}).json()
    assert t["project"]["title"] == "Validation agents" and "false hypotheses" in t["project"]["question"]
    assert set(t) >= {"date", "project", "goals", "goals_done", "goals_total", "next", "focus_minutes", "active_session", "win_today", "past_win"}


def test_login_and_switch(client, auth_headers):
    h = auth_headers
    for path in ("/api/today", "/api/goals", "/api/wins", "/api/focus/active"):
        assert client.get(path).status_code == 401
    client.put("/api/features", headers=h, json={"features": {"today": False}})
    for path in ("/api/today", "/api/goals", "/api/wins", "/api/focus/active", "/api/today/next"):
        assert client.get(path, headers=h).status_code == 403
    assert client.post("/api/focus/start", headers=h, json={}).status_code == 403


def test_backup_keeps_goals_wins_and_sessions(client, auth_headers, clock):
    h = auth_headers
    g = client.post("/api/goals", headers=h, json={"text": "Read 1 paper", "kind": "papers", "target": 1, "date": DAY}).json()
    client.put(f"/api/goals/{g['id']}", headers=h, json={"done": True})
    w = client.post("/api/wins", headers=h, json={"text": "I wrote the plan.", "date": DAY}).json()
    client.post("/api/focus/start", headers=h, json={"date": DAY})
    clock.t += 600
    s = client.post("/api/focus/stop", headers=h).json()
    backup = client.get("/api/export", headers=h).json()
    assert [x["id"] for x in backup["goals"]] == [g["id"]] and [x["id"] for x in backup["wins"]] == [w["id"]] and [x["id"] for x in backup["focus_sessions"]] == [s["id"]]
    client.delete(f"/api/goals/{g['id']}", headers=h)
    client.delete(f"/api/wins/{w['id']}", headers=h)
    with db.conn() as c:
        c.execute("DELETE FROM focus_sessions")
    client.post("/api/import", headers=h, json=backup)
    client.post("/api/import", headers=h, json=backup)  # a second import adds nothing
    t = client.get("/api/today", headers=h, params={"date": DAY}).json()
    assert t["goals_done"] == 1 and t["goals_total"] == 1 and t["win_today"]["text"] == "I wrote the plan." and t["focus_minutes"] == 10


def test_the_texts_of_the_page_are_kind():
    """Rule 5: no guilt. The texts of the next best action have no word of blame."""
    import re
    source = open(today.__file__, encoding="utf-8").read()
    texts = " ".join(re.findall(r'"text": f?"([^"]+)"', source))
    assert texts and not re.search(r"\b(missed|behind|lazy|failed|late|should have|only)\b", texts, re.I)
