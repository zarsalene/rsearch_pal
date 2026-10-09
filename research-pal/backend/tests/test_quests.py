"""Sprint 07: weekly quests, boss fights and the Duck."""
import datetime as dt
import json

import pytest

from app import companion, db, features, game, quests, ste
from helpers import upload, wait_ready

NOON = dt.datetime(2026, 10, 7, 12, 0, tzinfo=dt.timezone.utc).timestamp()  # a Wednesday
DAY = 86400
TODAY = "2026-10-07"
WEEK = "2026-W41"
START, END = dt.date(2026, 10, 5), dt.date(2026, 10, 11)


@pytest.fixture
def now(clock):
    clock.t = NOON
    return clock


def read(client, h, sample_pdfs, name="a.pdf"):
    pid = upload(client, h, sample_pdfs[name].path)
    wait_ready(client, h, pid)
    return pid


def set_stage(client, h, stage):
    client.put("/api/project", headers=h, json={"stage": stage})


def codes(client, h, date=TODAY):
    return [q["code"] for q in client.get("/api/quests", headers=h, params={"date": date}).json()["quests"]]


# ------------------------------------------------------------------ the catalog and the pick
def test_the_catalog_is_valid():
    cat = quests.catalog()
    assert len({q["code"] for q in cat}) == len(cat) >= 12
    assert all(q["xp"] > 0 and q["text"] for q in cat)
    for q in cat:  # the texts are short and simple
        assert not ste.lint(q["text"]), (q["code"], ste.lint(q["text"]))


def test_a_year_1_student_gets_reading_quests_not_writing_quests(client, auth_headers):
    h = auth_headers
    set_stage(client, h, "year_1")
    offered = {quests.by_code(c)["kind"] for c in codes(client, h)}
    assert "writing" not in offered and "reading" in offered
    for q in quests.eligible("year_1"):
        assert q["kind"] != "writing" and "year_1" in q["stage"] + ["year_1"] if "all" not in q["stage"] else True
    assert all("final_year" not in q["stage"] or "year_1" in q["stage"] or "all" in q["stage"] for q in quests.eligible("year_1"))


def test_the_stage_changes_the_quests(client):
    db.init()
    year1 = {q["code"] for q in quests.eligible("year_1")}
    final = {q["code"] for q in quests.eligible("final_year")}
    assert "words_5" in year1 and "words_5" not in final
    assert "review_10" in final and "review_10" not in year1
    assert {q["code"] for q in quests.eligible("")} == year1  # no stage: the first year


def test_a_locked_feature_gives_no_quest(client, monkeypatch):
    db.init()
    assert "supervisor_pack" not in {q["code"] for q in quests.eligible("year_1")}  # the feature of Sprint 12 does not exist yet
    assert "gap_5_lines" in {q["code"] for q in quests.eligible("final_year")}  # the gap finder exists now (Sprint 09)
    assert "lit_section" in {q["code"] for q in quests.eligible("final_year")}  # the literature review builder exists now (Sprint 08)
    monkeypatch.setitem(features.REGISTRY, "supervisor", {"label": "Supervisor", "description": "x", "default": True})
    assert "supervisor_pack" in {q["code"] for q in quests.eligible("year_1")}  # it unlocks with its feature
    db.set_feature("supervisor", False)
    assert "supervisor_pack" not in {q["code"] for q in quests.eligible("year_1")}  # and goes with the switch


def test_the_pick_is_stable_for_a_week_and_changes_the_next_week(client, auth_headers, now):
    h = auth_headers
    first = codes(client, h)
    assert len(first) == 3 and len(set(first)) == 3
    assert codes(client, h, "2026-10-09") == first  # the same week
    assert quests.pick("2026-W41", "year_1", set()) == quests.pick("2026-W41", "year_1", set())
    now.t += 7 * DAY
    nxt = codes(client, h, "2026-10-14")
    assert len(nxt) == 3 and len(set(nxt) & set(first)) < 3  # quests of the last week come last
    assert len({quests.by_code(c)["kind"] for c in first}) >= 2  # the kinds are mixed


# ------------------------------------------------------------------ choose
def test_choose_two_of_three_and_a_third_is_refused(client, auth_headers, now):
    h = auth_headers
    a, b, c = codes(client, h)
    assert client.post(f"/api/quests/{a}/choose", headers=h, params={"date": TODAY}).status_code == 200
    assert client.post(f"/api/quests/{b}/choose", headers=h, params={"date": TODAY}).json()["chosen"] == 2
    r = client.post(f"/api/quests/{c}/choose", headers=h, params={"date": TODAY})
    assert r.status_code == 400 and "no penalty" in r.json()["detail"].lower()
    assert client.post(f"/api/quests/{a}/choose", headers=h, params={"date": TODAY}).status_code == 200  # the same quest again: no change
    assert client.post("/api/quests/nope/choose", headers=h, params={"date": TODAY}).status_code == 400
    assert client.post(f"/api/quests/{a}/drop", headers=h, params={"date": TODAY}).json()["chosen"] == 1  # a drop has no penalty
    assert client.post(f"/api/quests/{c}/choose", headers=h, params={"date": TODAY}).json()["chosen"] == 2
    assert client.post(f"/api/quests/{a}/drop", headers=h, params={"date": TODAY}).status_code == 400  # not chosen now


# ------------------------------------------------------------------ conditions (with test data)
def add(action, n, date="2026-10-06", start=0):
    for i in range(n):
        db.xp_add(action, f"{action}{start + i}", 5, NOON, date)


def prog(code):
    return quests.progress(quests.by_code(code), START, END)


def test_each_condition_counts_the_work_of_this_week(client):
    db.init()
    add("card_ready", 2)
    add("card_ready", 5, date="2026-09-30", start=10)  # last week: not counted
    assert prog("cards_3") == (2, 3)
    add("feynman_pass", 2)
    assert prog("feynman_2") == (2, 2)
    add("quiz_correct", 4)
    assert prog("quiz_5") == (4, 5)
    add("review", 3, date="2026-10-05")
    add("review", 2, date="2026-10-06", start=10)
    assert prog("review_3_days") == (2, 3) and prog("review_10") == (5, 10)
    add("win_written", 1, date="2026-10-05")
    add("win_written", 1, date="2026-10-07", start=5)
    assert prog("wins_3") == (2, 3)
    db.init()
    with db.conn() as c:
        c.execute("INSERT INTO focus_sessions(id,start,\"end\",minutes,task_text,date,planned) VALUES('f1',1,2,70,'x','2026-10-06',25)")
        c.execute("INSERT INTO focus_sessions(id,start,\"end\",minutes,task_text,date,planned) VALUES('f2',1,2,60,'x','2026-10-01',25)")  # last week
    assert prog("focus_120") == (70, 120)
    for i in range(3):
        db.glossary_add(f"term{i}", "An explanation.", "ai", "p1", 0, None, NOON)
    assert prog("words_5") == (3, 5)
    for t in ("a", "b", "c"):
        db.add_sub_question(f"Sub question {t}?")
    assert prog("sub_questions_3") == (3, 3)
    assert prog("lit_section") == (0, 1) and prog("gap_5_lines") == (0, 1) and prog("supervisor_pack") == (0, 1)  # later sprints


def test_tag_all_needs_a_paper_for_each_sub_question():
    db.init()
    s1, s2 = db.add_sub_question("One?")["id"], db.add_sub_question("Two?")["id"]
    assert prog("tag_all") == (0, 2)
    db.set_tags("p1", "", [s1])
    assert prog("tag_all") == (1, 2)
    db.set_tags("p2", "", [s2])
    assert prog("tag_all") == (2, 2)


def link(a, b, relation, verified, day="2026-10-06"):
    ev = [{"paper_id": a, "quote": "A quote of the first paper in the text.", "page": 1, "verified": verified[0]},
          {"paper_id": b, "quote": "A quote of the second paper in the text.", "page": 1, "verified": verified[1]}]
    db.set_setting(f"link:{a}:{b}", json.dumps({"a": a, "b": b, "relation": relation, "evidence": ev, "generated_at": dt.datetime.fromisoformat(day + "T10:00:00+00:00").timestamp()}))


def test_truth_a_quest_that_needs_links_counts_only_links_with_verified_quotes(client):
    db.init()
    link("p1", "p2", "compares_with", (True, True))  # counts
    link("p1", "p3", "compares_with", (True, False))  # one false quote: no
    link("p2", "p3", "same_method", (True, True))  # another relation: no
    link("p1", "p4", "compares_with", (True, True), day="2026-09-20")  # another week: no
    assert prog("disagree_3") == (1, 3)
    link("p2", "p4", "compares_with", (True, True))
    link("p3", "p4", "compares_with", (True, True))
    assert prog("disagree_3") == (3, 3)


# ------------------------------------------------------------------ done: points and date
def test_a_quest_that_is_done_gives_points_one_time_and_a_date(client, auth_headers, now):
    h = auth_headers
    set_stage(client, h, "year_1")
    offered = codes(client, h)
    easy = next((c for c in offered if c in ("wins_3", "review_3_days", "focus_120", "cards_3", "words_5", "sub_questions_3")), None)
    assert easy, offered
    client.post(f"/api/quests/{easy}/choose", headers=h, params={"date": TODAY})
    xp_before = client.get("/api/game", headers=h, params={"date": TODAY}).json()["xp"]
    feeders = {"wins_3": ("win_written", 3), "review_3_days": ("review", 3), "cards_3": ("card_ready", 3), "words_5": None, "focus_120": None, "sub_questions_3": None}
    if feeders[easy]:
        action, n = feeders[easy]
        for i in range(n):  # one event on each of 3 days
            db.xp_add(action, f"{action}{i}", 0 + 1, NOON, f"2026-10-0{5 + i}")
    elif easy == "words_5":
        for i in range(5):
            db.glossary_add(f"t{i}", "An explanation.", "ai", "p1", 0, None, NOON)
    elif easy == "focus_120":
        with db.conn() as c:
            c.execute("INSERT INTO focus_sessions(id,start,\"end\",minutes,task_text,date,planned) VALUES('f1',1,2,130,'x','2026-10-06',25)")
    else:
        for t in "abc":
            db.add_sub_question(f"Sub question {t}?")
    game.refresh()
    s = client.get("/api/quests", headers=h, params={"date": TODAY}).json()
    done = next(q for q in s["quests"] if q["code"] == easy)
    assert done["done"] is True and s["log"][0]["code"] == easy and s["log"][0]["done_at"] > 0
    gained = client.get("/api/game", headers=h, params={"date": TODAY}).json()["xp"] - xp_before
    assert gained >= quests.by_code(easy)["xp"]
    client.get("/api/quests", headers=h, params={"date": TODAY})
    game.refresh()
    assert client.get("/api/game", headers=h, params={"date": TODAY}).json()["xp"] - xp_before == gained  # one time
    assert [e["action"] for e in db.xp_recent(50)].count("quest") == 1


def test_a_quest_that_is_not_chosen_does_not_finish_and_a_missed_quest_has_no_penalty(client, auth_headers, now):
    h = auth_headers
    offered = codes(client, h)
    add("card_ready", 3)
    add("win_written", 3, start=10)
    game.refresh()
    s = client.get("/api/quests", headers=h, params={"date": TODAY}).json()
    assert not any(q["done"] for q in s["quests"]) and s["log"] == []  # nothing chosen: nothing done
    xp = client.get("/api/game", headers=h, params={"date": TODAY}).json()["xp"]
    now.t += 10 * DAY  # the week ends. The offered quests go away with no loss.
    assert client.get("/api/game", headers=h, params={"date": "2026-10-17"}).json()["xp"] == xp
    assert [e["action"] for e in db.xp_recent(50)].count("quest") == 0
    assert len(codes(client, h, "2026-10-17")) == 3 and offered


def test_a_switched_off_game_gives_no_quest_points(client, auth_headers, now):
    h = auth_headers
    set_stage(client, h, "year_1")
    c = next(c for c in codes(client, h) if c == "wins_3" or True)
    client.post(f"/api/quests/{c}/choose", headers=h, params={"date": TODAY})
    client.put("/api/features", headers=h, json={"features": {"game": False}})
    assert quests.check_all(TODAY) == [] and quests.check_bosses() == []
    client.put("/api/features", headers=h, json={"features": {"quests": False}})
    assert client.get("/api/quests", headers=h).status_code == 403
    assert client.get("/api/bosses", headers=h).status_code == 403


# ------------------------------------------------------------------ bosses
def boss_ready(client, h, pid, correct=3, total=3, score=90):
    """Make quiz answers and a Feynman attempt for a paper, with test data."""
    for i in range(total):
        rid = db.review_add("quiz", pid, f"Question {i} about the paper?", "An answer.", "A quote of the paper in the text.", 1)
        with db.conn() as c:
            c.execute("UPDATE review_items SET last_mark=?, tries=1 WHERE id=?", ("correct" if i < correct else "wrong", rid))
    if score is not None:
        db.explanation_add(pid, "", "My explanation of the paper.", {"claims": []}, score)


def test_a_boss_is_defeated_only_when_both_scores_are_80_or_more(client, auth_headers, fake_ai, sample_pdfs, now):
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    st = client.post(f"/api/papers/{pid}/boss", headers=h, json={"boss": True}).json()
    assert st["is_boss"] and not st["defeated"] and st["quiz_needed"] == 3
    assert client.get(f"/api/papers/{pid}", headers=h).json()["paper"]["is_boss"] == 1
    boss_ready(client, h, pid, correct=3, total=4, score=90)  # quiz 75%: not enough
    assert quests.boss_status(pid)["quiz_percent"] == 75 and quests.check_bosses() == []
    db.explanation_add(pid, "", "A second, weaker explanation.", {"claims": []}, 79)
    with db.conn() as c:
        c.execute("DELETE FROM review_items WHERE paper_id=?", (pid,))
    boss_ready(client, h, pid, correct=4, total=4, score=None)  # quiz 100%, Feynman best 90 (from before)
    assert quests.boss_status(pid)["feynman_best"] == 90 and quests.boss_status(pid)["ready"]
    with db.conn() as c:
        c.execute("DELETE FROM explanations")
    db.explanation_add(pid, "", "Only a weak explanation.", {"claims": []}, 79)
    assert not quests.boss_status(pid)["ready"] and quests.check_bosses() == []  # Feynman 79: not enough
    db.explanation_add(pid, "", "A good explanation.", {"claims": []}, 80)
    assert quests.check_bosses() == [pid]
    assert quests.check_bosses() == []  # one time
    g = client.get("/api/game", headers=h, params={"date": TODAY}).json()
    assert any(b["code"] == f"boss:{pid}" and b["name"] == f"Boss defeated: {sample_pdfs['a.pdf'].title}" for b in g["badges"])
    assert [e["action"] for e in db.xp_recent(10)].count("boss") == 1 and client.get("/api/bosses", headers=h).json()[0]["defeated"] is True


def test_a_boss_needs_at_least_3_answered_questions(client, auth_headers, fake_ai, sample_pdfs, now):
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    client.post(f"/api/papers/{pid}/boss", headers=h, json={"boss": True})
    boss_ready(client, h, pid, correct=2, total=2, score=100)  # 2 of 2 is 100%, but too few
    assert quests.boss_status(pid)["quiz_percent"] == 100 and not quests.boss_status(pid)["ready"]


def test_a_paper_that_is_not_a_boss_is_never_defeated(client, auth_headers, fake_ai, sample_pdfs, now):
    pid = read(client, auth_headers, sample_pdfs)
    boss_ready(client, auth_headers, pid, 3, 3, 100)
    assert quests.check_bosses() == [] and not db.get_paper(pid)["boss_defeated_at"]


def test_the_real_quiz_and_explain_defeat_a_boss_and_say_so(client, auth_headers, fake_ai, sample_pdfs, now):
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    client.post(f"/api/papers/{pid}/boss", headers=h, json={"boss": True})
    qs = client.post(f"/api/papers/{pid}/quiz", headers=h, json={}).json()["questions"]
    for q in qs:
        db.review_add("quiz", pid, f"Extra question {q['id']} about the paper?", "Sysmon", "A quote of the paper in the text.", 1)
    for r in db.review_list(pid, "quiz"):
        if r["id"] not in {q["id"] for q in qs}:
            with db.conn() as c:
                c.execute("UPDATE review_items SET last_mark='correct', tries=1 WHERE id=?", (r["id"],))
    text = "Analysts spend many hours on manual log review. The system uses a hypothesis agent and a validation agent. It reaches a precision of 91.4 percent and a recall of 84.2 percent."
    high = client.post(f"/api/papers/{pid}/explain", headers=h, json={"text": text}).json()
    assert high["score"] >= 80 and high["boss_defeated"] == ""  # the quiz is not done yet
    said = [client.post(f"/api/quiz/{q['id']}/answer", headers=h, json={"answer": "It reads the Sysmon logs of the OpTC dataset."}).json()["boss_defeated"] for q in qs]
    assert said.count(sample_pdfs["a.pdf"].title) == 1  # the answer that defeats the boss says so, one time
    assert client.post(f"/api/papers/{pid}/boss", headers=h, json={"boss": False}).json()["defeated"] is True  # the victory stays
    assert client.post("/api/papers/nope/boss", headers=h, json={"boss": True}).status_code == 404


def test_eli12_on_a_boss_and_a_feynman_pass_finish_the_quest(client, auth_headers, fake_ai, sample_pdfs, now):
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    client.post(f"/api/papers/{pid}/boss", headers=h, json={"boss": True})
    assert prog("eli12_hard") == (0, 2)
    client.post(f"/api/papers/{pid}/eli12", headers=h, json={"field": "method"})
    assert prog("eli12_hard") == (1, 2)
    text = "Analysts spend many hours on manual log review. The system uses a hypothesis agent and a validation agent. It reaches a precision of 91.4 percent and a recall of 84.2 percent."
    set_stage(client, h, "year_1")
    client.post(f"/api/papers/{pid}/explain", headers=h, json={"text": text})
    assert prog("eli12_hard") == (2, 2)


# ------------------------------------------------------------------ the Duck
def test_the_messages_of_the_duck_are_simple_and_kind():
    import re
    for event, texts in companion.MESSAGES.items():
        for t in texts:
            assert not ste.lint(t), (event, t, ste.lint(t))
            assert not re.search(r"\b(failed|lazy|stupid|bad|behind|late|missed)\b", t, re.I)
    assert companion.message("feynman_pass", "a") == companion.message("feynman_pass", "a") and companion.message("nope") == ""


def test_the_companion_endpoint_and_its_switch(client, auth_headers):
    h = auth_headers
    got = client.get("/api/companion", headers=h, params={"event": "welcome_back"}).json()
    assert got["message"] in companion.MESSAGES["welcome_back"] and "boss_defeated" in got["events"]
    assert client.get("/api/companion").status_code == 401
    client.put("/api/features", headers=h, json={"features": {"duck": False}})  # hide the Duck
    assert client.get("/api/companion", headers=h).status_code == 403


def test_backup_keeps_quests_and_bosses(client, auth_headers, fake_ai, sample_pdfs, now):
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    client.post(f"/api/papers/{pid}/boss", headers=h, json={"boss": True})
    a = codes(client, h)[0]
    client.post(f"/api/quests/{a}/choose", headers=h, params={"date": TODAY})
    backup = client.get("/api/export", headers=h).json()
    assert len(backup["quests_active"]) == 3 and backup["papers"][0]["is_boss"] == 1
    with db.conn() as c:
        c.execute("DELETE FROM quests_active")
    client.delete(f"/api/papers/{pid}", headers=h)
    client.post("/api/import", headers=h, json=backup)
    client.post("/api/import", headers=h, json=backup)
    assert len(db.quests_week(WEEK)) == 3 and sum(1 for r in db.quests_week(WEEK) if r["chosen_at"]) == 1
    assert wait_ready(client, h, pid)["paper"]["is_boss"] == 1
