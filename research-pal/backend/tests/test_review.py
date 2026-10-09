"""Sprint 06: the Knowledge Garden (spaced review with FSRS) and the Expedition map."""
import copy
import datetime as dt
import sqlite3

import pytest

from app import config, db, game, journey, review
from fake_ai import default_answers
from helpers import assert_no_false_quote, upload, wait_ready
from pdfs import INVENTED_QUOTE

NOON = dt.datetime(2026, 10, 9, 12, 0, tzinfo=dt.timezone.utc).timestamp()
DAY = 86400
TODAY = "2026-10-09"


@pytest.fixture
def now(clock):
    clock.t = NOON
    return clock


def read(client, h, sample_pdfs, name="a.pdf"):
    pid = upload(client, h, sample_pdfs[name].path)
    wait_ready(client, h, pid)
    return pid


def item(**kw):
    base = {"created_at": NOON, "fsrs_json": None, "reps": 0, "lapses": 0}
    return {**base, **kw}


# ------------------------------------------------------------------ FSRS
def test_a_better_rating_gives_a_later_date():
    due = {r: review.rate(item(), r, NOON)["due"] for r in ("again", "hard", "good", "easy")}
    assert due["hard"] < due["good"] < due["easy"]  # "Good" is later than "Hard"
    assert due["again"] <= due["hard"] and due["again"] >= NOON + DAY - 1  # a whole day: the student reviews one time each day
    assert (due["good"] - NOON) / DAY >= 2 - 1e-6


def test_the_next_interval_grows_with_each_good_answer():
    state, t = item(), NOON
    gaps = []
    for _ in range(4):
        state = {**state, **review.rate(state, "good", t)}
        gaps.append(state["due"] - t)
        t = state["due"]
    assert gaps == sorted(gaps) and gaps[-1] > gaps[0] * 2
    assert state["reps"] == 4 and state["lapses"] == 0


def test_a_lapse_is_counted():
    s = {**item(), **review.rate(item(), "good", NOON)}
    s = {**s, **review.rate(s, "again", s["due"])}
    assert s["lapses"] == 1 and s["reps"] == 2
    with pytest.raises(review.ReviewError):
        review.rate(item(), "great", NOON)


# ------------------------------------------------------------------ plants
def test_plant_state_from_the_dates():
    assert review.plant_state([], TODAY) == "fresh"  # a paper with no item
    assert review.plant_state(["2026-10-10", "2026-11-01"], TODAY) == "fresh"  # nothing is due
    assert review.plant_state(["2026-10-09"], TODAY) == "ok"  # due today
    assert review.plant_state(["2026-10-07"], TODAY) == "ok"  # 2 days over
    assert review.plant_state(["2026-10-06", "2026-10-20"], TODAY) == "dry"  # 3 days over
    assert review.plant_state(["2025-01-01"], TODAY) == "dry"  # a long time: dry, never dead


# ------------------------------------------------------------------ the items
def test_each_card_gives_a_main_idea_item_with_a_verified_quote(client, auth_headers, fake_ai, sample_pdfs, now):
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    due = client.get("/api/review/due", headers=h, params={"date": TODAY}).json()
    idea = [i for i in due["items"] if i["kind"] == "idea"]
    assert len(idea) == 1 and idea[0]["paper_id"] == pid and "main idea" in idea[0]["question"] and idea[0]["label"] == "Main idea"
    assert idea[0]["quote"] and idea[0]["page"] >= 1
    assert "hypothesis agent" in idea[0]["answer"] and "Analysts spend many hours" in idea[0]["answer"]  # the checked problem and method
    rows = db.review_list(pid, "idea")
    assert_no_false_quote({"evidence": [{"quote": r["quote"], "verified": True, "paper_id": pid} for r in rows]}, pages={pid: db.get_pages(pid)}, invented=[INVENTED_QUOTE])
    client.get("/api/review/due", headers=h, params={"date": TODAY})  # a second call makes no second item
    assert len(db.review_list(pid, "idea")) == 1


def test_truth_a_card_without_a_verified_quote_gives_no_item(client, auth_headers, fake_ai, sample_pdfs, now):
    def all_invented(messages):
        raw = copy.deepcopy(default_answers(messages))
        for name in ("problem", "method", "result", "limitation"):
            raw[name]["evidence"] = [{"quote": INVENTED_QUOTE, "page": 1}]
        return raw

    fake_ai.when("<paper>", all_invented)
    pid = read(client, auth_headers, sample_pdfs)
    assert client.get("/api/review/due", headers=auth_headers, params={"date": TODAY}).json()["total"] == 0
    assert db.review_list(pid) == []


def test_quiz_questions_and_words_are_items_with_their_labels(client, auth_headers, fake_ai, sample_pdfs, now):
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    client.post(f"/api/papers/{pid}/quiz", headers=h, json={})
    client.post("/api/glossary", headers=h, json={"term": "hypothesis", "paper_id": pid})  # a definition of the paper
    fake_ai.when("You explain a word or a short term", {"explanation": "An ontology is a map of ideas."})
    client.post("/api/glossary", headers=h, json={"term": "ontology", "paper_id": pid})  # an explanation of the AI
    items = client.get("/api/review/due", headers=h, params={"date": TODAY}).json()["items"]
    by = {(i["kind"], i["question"]): i for i in items}
    assert {i["kind"] for i in items} == {"idea", "quiz", "glossary"} and len(items) == 5
    assert by[("glossary", 'What does "hypothesis" mean?')]["label"] == "From the paper" if ("glossary", 'What does "hypothesis" mean?') in by else True
    labels = {i["question"]: i["label"] for i in items if i["kind"] == "glossary"}
    assert labels == {'What does "hypothesis" mean?': "From the paper", 'What does "ontology" mean?': "AI explanation"}


# ------------------------------------------------------------------ due, answer, points
def test_due_returns_only_items_with_a_date_of_today_or_earlier(client, auth_headers, fake_ai, sample_pdfs, now):
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    client.post(f"/api/papers/{pid}/quiz", headers=h, json={})
    first = client.get("/api/review/due", headers=h, params={"date": TODAY}).json()
    assert first["total"] == 3 and len(first["items"]) == 3
    r = client.post(f"/api/review/{first['items'][0]['id']}", headers=h, json={"rating": "good", "date": TODAY})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["interval_days"] >= 2 and out["remaining"] == 2 and out["xp_gained"] == 2
    assert client.get("/api/review/due", headers=h, params={"date": TODAY}).json()["total"] == 2  # the rated item is not due
    now.t += 3 * DAY  # three days later, it is due again
    assert client.get("/api/review/due", headers=h, params={"date": "2026-10-12"}).json()["total"] == 3
    assert client.get("/api/review/due", headers=h, params={"date": TODAY, "paper_id": "nope"}).json()["total"] == 0
    assert len(client.get("/api/review/due", headers=h, params={"date": TODAY, "limit": 1}).json()["items"]) == 1


def test_rate_an_item_saves_the_new_date_and_gives_2_points_at_most_20_each_day(client, auth_headers, now):
    h = auth_headers
    db.init()
    for i in range(12):
        db.review_add("quiz", "p1", f"Question number {i} about a paper?", "An answer.", "A quote of the paper in the text.", 1)
    items = client.get("/api/review/due", headers=h, params={"date": TODAY}).json()["items"]
    assert len(items) == 12
    gained = [client.post(f"/api/review/{i['id']}", headers=h, json={"rating": "hard", "date": TODAY}).json()["xp_gained"] for i in items]
    assert gained == [2] * 10 + [0, 0]  # 20 points at most for one day
    assert client.get("/api/game", headers=h, params={"date": TODAY}).json()["xp"] == 20
    saved = db.review_get(items[0]["id"])
    assert saved["reps"] == 1 and saved["due"] > NOON and saved["fsrs_json"] and saved["last_review"] == NOON and saved["stability"] > 0
    now.t += DAY  # "Hard" gives 1 day: the next day the 12 items are due again
    assert len(client.get("/api/review/due", headers=h, params={"date": "2026-10-10"}).json()["items"]) == 12


def test_an_item_that_is_not_due_cannot_be_rated(client, auth_headers, now):
    h = auth_headers
    db.init()
    rid = db.review_add("quiz", "p1", "A question about a paper?", "An answer.", "A quote of the paper in the text.", 1)
    assert client.post(f"/api/review/{rid}", headers=h, json={"rating": "good", "date": TODAY}).status_code == 200
    r = client.post(f"/api/review/{rid}", headers=h, json={"rating": "good", "date": TODAY})
    assert r.status_code == 400 and "not due yet" in r.json()["detail"]  # no way to farm points
    assert client.get("/api/game", headers=h, params={"date": TODAY}).json()["xp"] == 2
    assert client.post("/api/review/nope", headers=h, json={"rating": "good", "date": TODAY}).status_code == 400
    assert client.post(f"/api/review/{rid}", headers=h, json={"rating": "great", "date": "2030-01-01"}).status_code == 400


# ------------------------------------------------------------------ garden
def test_the_garden_has_one_plant_for_each_paper(client, auth_headers, fake_ai, sample_pdfs, now):
    h = auth_headers
    a, b = read(client, h, sample_pdfs, "a.pdf"), read(client, h, sample_pdfs, "b.pdf")
    g = client.get("/api/review/garden", headers=h, params={"date": TODAY}).json()
    assert [p["paper_id"] for p in g["plants"]] == [a, b] and {p["state"] for p in g["plants"]} == {"ok"} and g["due_total"] >= 1
    plant_a = next(p for p in g["plants"] if p["paper_id"] == a)
    assert plant_a["items"] == 1 and plant_a["due"] == 1
    for i in client.get("/api/review/due", headers=h, params={"date": TODAY}).json()["items"]:
        client.post(f"/api/review/{i['id']}", headers=h, json={"rating": "good", "date": TODAY})
    g = client.get("/api/review/garden", headers=h, params={"date": TODAY}).json()
    assert {p["state"] for p in g["plants"]} == {"fresh"} and g["due_total"] == 0  # all watered
    g = client.get("/api/review/garden", headers=h, params={"date": "2026-10-30"}).json()
    assert {p["state"] for p in g["plants"]} == {"dry"}  # three weeks later, with no review: dry. It does not die.
    assert len(g["plants"]) == 2


def test_the_items_go_with_the_paper_or_card_but_the_words_stay(client, auth_headers, fake_ai, sample_pdfs, now):
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    cid = client.post(f"/api/papers/{pid}/cards", headers=h, json={"focus": "Sysmon logs"}).json()["id"]
    for _ in range(100):
        if client.get(f"/api/papers/{pid}/cards/{cid}", headers=h).json()["paper"]["status"] == "ready":
            break
    client.get("/api/review/due", headers=h, params={"date": TODAY})
    assert len(db.review_list(pid, "idea")) == 2
    client.delete(f"/api/papers/{pid}/cards/{cid}", headers=h)
    assert [r["card_id"] for r in db.review_list(pid, "idea")] == [""]
    client.post("/api/glossary", headers=h, json={"term": "hypothesis", "paper_id": pid})
    client.delete(f"/api/papers/{pid}", headers=h)
    assert [r["kind"] for r in db.review_list()] == ["glossary"]


def test_old_review_items_get_a_date(client):
    """A database from Sprint 02 has review items with no FSRS columns. init() adds them, and the old items are due."""
    old = config.DATA_DIR / "old.sqlite3"
    c = sqlite3.connect(old)
    c.executescript("CREATE TABLE review_items(id TEXT PRIMARY KEY, kind TEXT, paper_id TEXT, question TEXT, answer TEXT, quote TEXT, page INTEGER DEFAULT 0, created_at REAL,"
                    " card_id TEXT DEFAULT '', ref_id TEXT DEFAULT '', last_mark TEXT DEFAULT '', tries INTEGER DEFAULT 0);"
                    "INSERT INTO review_items(id,kind,paper_id,question,answer,quote,page,created_at) VALUES('q1','quiz','p1','A question?','An answer.','A quote of the paper.',2,12345.0);")
    c.commit()
    c.close()
    real = config.DB_PATH
    try:
        config.DB_PATH = old
        db.init()
        db.init()
        r = db.review_get("q1")
        assert r["due"] == 12345.0 and r["reps"] == 0 and r["fsrs_json"] is None and r["question"] == "A question?"
    finally:
        config.DB_PATH = real


def test_login_and_switch(client, auth_headers):
    h = auth_headers
    for path in ("/api/review/due", "/api/review/garden", "/api/journey/map"):
        assert client.get(path).status_code == 401
    client.put("/api/features", headers=h, json={"features": {"review": False}})
    for path in ("/api/review/due", "/api/review/garden"):
        assert client.get(path, headers=h).status_code == 403
    assert client.post("/api/review/x", headers=h, json={"rating": "good"}).status_code == 403
    assert client.get("/api/journey/map", headers=h).status_code == 200  # the map has its own switch
    client.put("/api/features", headers=h, json={"features": {"map": False}})
    assert client.get("/api/journey/map", headers=h).status_code == 403


def test_backup_keeps_the_dates_of_the_review(client, auth_headers, fake_ai, sample_pdfs, now):
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    client.post("/api/glossary", headers=h, json={"term": "hypothesis", "paper_id": pid})
    for i in client.get("/api/review/due", headers=h, params={"date": TODAY}).json()["items"]:
        client.post(f"/api/review/{i['id']}", headers=h, json={"rating": "easy", "date": TODAY})
    before = {(r["kind"], r["question"]): r["due"] for r in db.review_list()}
    backup = client.get("/api/export", headers=h).json()
    assert len(backup["review_state"]) == 2
    with db.conn() as c:  # the schedule is lost
        c.execute("UPDATE review_items SET due=created_at, reps=0, fsrs_json=NULL, stability=NULL")
    client.post("/api/import", headers=h, json=backup)
    assert {(r["kind"], r["question"]): r["due"] for r in db.review_list()} == before
    assert all(r["reps"] == 1 for r in db.review_list())


# ------------------------------------------------------------------ the map
def test_the_map_of_a_new_student_is_empty_and_kind(client, auth_headers):
    m = client.get("/api/journey/map", headers=auth_headers).json()
    assert [r["code"] for r in m["regions"]] == ["peak", "forest", "workshop", "mines", "coast", "castle"]
    assert [r["name"] for r in m["regions"]][0] == "Question Peak" and m["total"] == 0
    assert all(r["percent"] == 0 and r["state"] == "not_started" and r["first_step"] for r in m["regions"])
    assert m["regions"][0]["first_step"] == "Write your thesis title." and "later sprint" in m["regions"][2]["first_step"]


def test_question_peak_fills_with_title_question_and_sub_questions(client, auth_headers):
    h = auth_headers
    client.put("/api/project", headers=h, json={"title": "Validation agents"})
    assert journey.question_peak()["percent"] == 25
    client.put("/api/project", headers=h, json={"question": "Do validation agents reduce false hypotheses?"})
    assert journey.question_peak()["percent"] == 50 and "sub-questions" in journey.question_peak()["first_step"]
    db.add_sub_question("What data exists?")
    assert journey.question_peak()["percent"] == 67  # 0.5 + 0.5 * 1/3 of 50
    db.add_sub_question("Which method works best?")
    db.add_sub_question("How do we measure it?")
    assert journey.question_peak() | {} and journey.question_peak()["percent"] == 100 and "in view" in journey.question_peak()["first_step"]


def test_literature_forest_counts_ready_cards_and_feynman_passes_for_each_sub_question(client):
    db.init()
    assert journey.literature_forest()["percent"] == 0
    # no sub-question: 5 ready cards and 3 Feynman passes fill the forest
    for i in range(5):
        db.xp_add("card_ready", f"p{i}:", 10, NOON, TODAY)
    assert journey.literature_forest()["percent"] == 50
    for i in range(3):
        db.xp_add("feynman_pass", f"p{i}", 25, NOON, TODAY)
    assert journey.literature_forest()["percent"] == 100
    # with sub-questions: each one needs 2 papers with a ready card and 1 with a Feynman pass
    s1, s2 = db.add_sub_question("What data exists?")["id"], db.add_sub_question("Which method works best?")["id"]
    db.set_tags("p0", "", [s1])
    db.set_tags("p1", "", [s1])
    db.set_tags("p2", "", [s2])
    f = journey.literature_forest()
    assert f["percent"] == round(100 * (1.0 + (0.25 + 0.5)) / 2)  # SQ1: 2 cards, 2 passes = 1.0. SQ2: 1 card (0.25) + 1 pass (0.5)
    assert "SQ2" in f["first_step"]


def test_the_regions_of_later_sprints_wait_for_their_tables(client):
    db.init()
    assert journey.method_workshop()["percent"] == journey.data_mines()["percent"] == journey.writing_coast()["percent"] == journey.defense_castle()["percent"] == 0
    with db.conn() as c:  # a later sprint makes these tables
        c.execute("CREATE TABLE journal(id TEXT, kind TEXT)")
        c.executemany("INSERT INTO journal VALUES(?,?)", [(str(i), "idea") for i in range(5)] + [("e1", "experiment")])
    db.review_section_add(db.review_doc()["id"], "A section", "", "word " * 300)  # the literature review builder (Sprint 08)
    assert journey.method_workshop()["percent"] == 50 and journey.data_mines()["percent"] == 10 and journey.writing_coast()["percent"] == 20


def test_the_texts_of_the_garden_and_the_map_are_kind(client):
    """Rule 5: a dry plant and a region at 0% show no blame. The texts that the student reads have no word of blame."""
    import re
    db.init()
    texts = [r[k] for r in journey.build()["regions"] for k in ("first_step", "detail", "name")] + list(review.KIND_LABEL.values())
    texts += ["Not started"]
    assert not re.search(r"(dead|dies|died|failed|lazy|behind|missed|shame|overdue|late)", " ".join(texts), re.I)
