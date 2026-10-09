"""Sprint 11: suggestions, timeline, weekly review, research journal."""
import datetime as dt

import pytest

from app import db, game, journey, plan, sources, suggestions
from helpers import upload, wait_ready
from recorded_sources import AUTOMA_DOI, route

QUESTION = "How can multi agent systems find cyber threats in network logs?"
TODAY = dt.date(2026, 10, 9)  # a Friday
DAY = dt.datetime(2026, 10, 9, 12, 0, tzinfo=dt.timezone.utc).timestamp()


@pytest.fixture
def fake_net(monkeypatch, sample_pdfs):
    pdf = sample_pdfs["a.pdf"].path.read_bytes()
    state = {"calls": [], "down": False}

    def fetch(url, params=None):
        state["calls"].append(url)
        if state["down"]:
            raise sources.SourceError("The app could not reach the source. Check the internet connection.")
        return route(url, params, pdf, True)

    monkeypatch.setattr(sources, "fetch", fetch)
    monkeypatch.setenv("CONTACT_EMAIL", "student@example.org")
    sources._cache.clear()
    return state


@pytest.fixture
def friday(monkeypatch):
    monkeypatch.setattr(db, "now", lambda: DAY)
    return TODAY


def library(client, h, sample_pdfs):
    """Two library papers with a DOI each: AUTOMA (W100) and the closed paper (W101)."""
    a = upload(client, h, sample_pdfs["a.pdf"].path)
    b = upload(client, h, sample_pdfs["b.pdf"].path)
    wait_ready(client, h, a), wait_ready(client, h, b)
    db.update_paper(a, doi=AUTOMA_DOI)
    db.update_paper(b, doi="10.9999/closed.1", title="A closed paper about threat hunting")
    return a, b


# ------------------------------------------------------------------ suggestions
def test_suggestions_have_a_reason_that_is_true_and_the_best_links_come_first(client, auth_headers, fake_ai, fake_net, sample_pdfs):
    h = auth_headers
    db.save_project({"question": QUESTION})
    library(client, h, sample_pdfs)
    r = client.post("/api/suggestions/refresh", headers=h).json()
    assert r["added"] == 3, r
    items = {i["title"]: i for i in client.get("/api/to-read", headers=h).json()}
    assert set(items) == {"Hunting threats with agents in network logs", "Cooking pasta with tomatoes", "Validation agents for threat hunting"}
    assert all(i["source"] == "suggested" for i in items.values())
    assert items["Hunting threats with agents in network logs"]["reason"].startswith("Cited by 2 of your papers")  # both library papers cite it
    assert items["Validation agents for threat hunting"]["reason"].startswith("Cites 2 of your papers")  # it cites both library papers
    assert items["Cooking pasta with tomatoes"]["reason"].startswith("Cited by 2 of your papers")
    top = client.get("/api/to-read", headers=h).json()
    assert top[0]["score"] >= top[1]["score"] >= top[2]["score"]
    assert top[0]["title"] == "Hunting threats with agents in network logs"  # two links and a fit to the question


def test_a_paper_that_is_in_the_library_is_never_suggested(client, auth_headers, fake_ai, fake_net, sample_pdfs):
    h = auth_headers
    library(client, h, sample_pdfs)
    client.post("/api/suggestions/refresh", headers=h)
    titles = [i["title"] for i in client.get("/api/to-read", headers=h).json()]
    assert "A paper that you have already" not in titles  # W202 has the DOI of a library paper
    assert not any(i["doi"] in (AUTOMA_DOI, "10.9999/closed.1") for i in db.to_read_list())


def test_a_suggestion_that_you_called_not_useful_does_not_come_back(client, auth_headers, fake_ai, fake_net, sample_pdfs):
    h = auth_headers
    library(client, h, sample_pdfs)
    client.post("/api/suggestions/refresh", headers=h)
    item = next(i for i in client.get("/api/to-read", headers=h).json() if i["title"].startswith("Cooking"))
    client.put(f"/api/to-read/{item['id']}", headers=h, json={"status": "not_useful"})
    again = client.post("/api/suggestions/refresh", headers=h).json()
    assert again["added"] == 0 and "No new suggestion" in again["message"]
    assert len(client.get("/api/to-read", headers=h).json()) == 2


def test_suggestions_need_papers_with_a_doi_and_a_source_that_answers(client, auth_headers, fake_ai, fake_net, sample_pdfs):
    h = auth_headers
    r = client.post("/api/suggestions/refresh", headers=h).json()
    assert r["added"] == 0 and "DOI" in r["message"]
    library(client, h, sample_pdfs)
    fake_net["down"] = True
    sources._cache.clear()
    r = client.post("/api/suggestions/refresh", headers=h)
    assert r.status_code == 200 and r.json()["added"] == 0 and "did not answer" in r.json()["message"]


def test_suggestions_run_once_a_day_in_the_background(client, auth_headers, fake_ai, fake_net, sample_pdfs, monkeypatch):
    h = auth_headers
    library(client, h, sample_pdfs)
    assert suggestions.due()
    assert client.get("/api/to-read", headers=h).json() == []  # the first call starts the run in the background
    items = client.get("/api/to-read", headers=h).json()
    assert len(items) == 3 and not suggestions.due()
    calls = len(fake_net["calls"])
    sources._cache.clear()
    client.get("/api/to-read", headers=h)
    assert len(fake_net["calls"]) == calls  # not again on the same day
    db.set_setting("suggest_last", str(db.now() - 2 * 24 * 3600))
    assert suggestions.due()


def test_the_suggest_switch_turns_the_suggestions_off(client, auth_headers, fake_ai, fake_net, sample_pdfs):
    h = auth_headers
    library(client, h, sample_pdfs)
    client.put("/api/features", headers=h, json={"features": {"suggest": False}})
    assert client.post("/api/suggestions/refresh", headers=h).status_code == 403
    assert client.get("/api/to-read", headers=h).json() == []  # the list works, and nothing starts in the background


# ------------------------------------------------------------------ timeline
def test_the_default_milestones_follow_the_stage(client, auth_headers, friday):
    h = auth_headers
    client.put("/api/project", headers=h, json={"stage": "final_year"})
    v = client.post("/api/milestones/defaults", headers=h).json()
    assert [m["title"] for m in v["milestones"]] == ["Thesis draft", "Defense"] and all(m["days_left"] > 0 for m in v["milestones"])
    assert v["current"] == v["milestones"][0]["id"] and v["today"] == "2026-10-09"
    assert client.post("/api/milestones/defaults", headers=h).status_code == 400  # a second call changes nothing


def test_milestones_can_be_made_edited_checked_and_deleted(client, auth_headers, friday):
    h = auth_headers
    m = client.post("/api/milestones", headers=h, json={"title": "First paper", "due": "2027-03-01"}).json()
    assert client.post("/api/milestones", headers=h, json={"title": "", "due": "2027-03-01"}).status_code == 400
    assert client.post("/api/milestones", headers=h, json={"title": "X", "due": "tomorrow"}).status_code == 400
    assert client.put(f"/api/milestones/{m['id']}", headers=h, json={"due": "2027-04-01", "done": True}).json()["due"] == "2027-04-01"
    assert client.put("/api/milestones/unknown", headers=h, json={"done": True}).status_code == 400
    client.post(f"/api/milestones/{m['id']}/tasks", headers=h, json={"week": "2026-10-14", "text": "Read the method papers"})
    v = client.get("/api/plan", headers=h).json()
    assert v["milestones"][0]["done"] is True and v["milestones"][0]["tasks"][0]["week"] == "2026-10-12"  # a task goes to the Monday of its week
    client.delete(f"/api/milestones/{m['id']}", headers=h)
    assert client.get("/api/plan", headers=h).json()["milestones"] == [] and db.tasks_list() == []


def test_split_gives_tasks_with_the_label_ai_suggestion_and_the_student_edits_them(client, auth_headers, fake_ai, friday):
    h = auth_headers
    m = client.post("/api/milestones", headers=h, json={"title": "First paper", "due": "2026-12-15"}).json()
    v = client.post(f"/api/milestones/{m['id']}/split", headers=h).json()
    tasks = v["milestones"][0]["tasks"]
    assert [t["text"] for t in tasks] == ["Read two papers about the method.", "Tag the papers to your sub-questions.", "Write the plan of the first test.", "Ask your supervisor to check the plan."]
    assert all(t["label"] == "AI suggestion" and t["ai"] for t in tasks)  # the bad weeks and the empty text were dropped
    assert [t["week"] for t in tasks] == ["2026-10-05", "2026-10-05", "2026-10-12", "2026-10-19"] and all(dt.date.fromisoformat(t["week"]).weekday() == 0 for t in tasks)
    edited = client.put(f"/api/tasks/{tasks[0]['id']}", headers=h, json={"text": "Read the three method papers of my supervisor."}).json()
    assert edited["label"] == "" and edited["edited"] is True  # the student wrote it: it is no AI text any more
    own = client.post(f"/api/milestones/{m['id']}/tasks", headers=h, json={"week": "2026-10-26", "text": "My own task"}).json()
    client.put(f"/api/tasks/{tasks[1]['id']}", headers=h, json={"done": True})
    v2 = client.post(f"/api/milestones/{m['id']}/split", headers=h).json()
    texts = [t["text"] for t in v2["milestones"][0]["tasks"]]
    assert "Read the three method papers of my supervisor." in texts and "My own task" in texts and "Tag the papers to your sub-questions." in texts  # edited, own and checked tasks stay
    assert texts.count("Write the plan of the first test.") == 1  # an AI task that was not touched is replaced, not doubled


def test_split_refuses_a_past_due_date_and_junk_from_the_ai(client, auth_headers, fake_ai, friday):
    h = auth_headers
    m = client.post("/api/milestones", headers=h, json={"title": "Old", "due": "2026-01-01"}).json()
    assert client.post(f"/api/milestones/{m['id']}/split", headers=h).status_code == 400
    m2 = client.post("/api/milestones", headers=h, json={"title": "New", "due": "2026-12-15"}).json()
    fake_ai.when("You help a PhD student to plan the weeks", {"tasks": [{"week": 99, "text": "x"}, "bad", {"week": 1, "text": ""}]})
    r = client.post(f"/api/milestones/{m2['id']}/split", headers=h)
    assert r.status_code == 400 and "no usable task" in r.json()["detail"]
    assert db.tasks_list() == []


def test_split_gives_at_most_three_tasks_for_a_week(client, auth_headers, fake_ai, friday):
    h = auth_headers
    m = client.post("/api/milestones", headers=h, json={"title": "New", "due": "2026-12-15"}).json()
    fake_ai.when("You help a PhD student to plan the weeks", {"tasks": [{"week": 1, "text": f"Task {i}"} for i in range(8)]})
    assert len(client.post(f"/api/milestones/{m['id']}/split", headers=h).json()["milestones"][0]["tasks"]) == 3


# ------------------------------------------------------------------ weekly review
def test_one_review_for_each_week_and_the_second_updates_the_first_with_points_one_time(client, auth_headers, friday):
    h = auth_headers
    body = {"done": "Read 3 papers", "blocked": "The data", "learned": "Agents need checks", "next_goal": "Write the method", "mood": 4}
    first = client.put("/api/weekly-review", headers=h, json=body).json()
    assert first["review"]["week"] == "2026-10-05" and first["xp_gained"] == 15
    second = client.put("/api/weekly-review", headers=h, json={**body, "mood": 2, "learned": "More"}).json()
    assert second["review"]["id"] == first["review"]["id"] and second["review"]["mood"] == 2 and second["xp_gained"] == 0
    v = client.get("/api/weekly-review", headers=h).json()
    assert len(v["reviews"]) == 1 and v["this_week"]["learned"] == "More" and v["due"] is False
    assert client.get("/api/game", headers=h).json()["xp"] == 15
    other = client.put("/api/weekly-review", headers=h, json={**body, "week": "2026-09-28"}).json()  # an earlier week is a new review
    assert other["xp_gained"] == 15 and len(client.get("/api/weekly-review", headers=h).json()["reviews"]) == 2


def test_the_review_checks_its_input_and_is_due_from_friday(client, auth_headers, friday, monkeypatch):
    h = auth_headers
    ok = {"done": "x", "mood": 3}
    assert client.put("/api/weekly-review", headers=h, json={"mood": 3}).status_code == 400  # nothing written
    assert client.put("/api/weekly-review", headers=h, json={**ok, "mood": 6}).status_code == 400
    assert client.put("/api/weekly-review", headers=h, json={**ok, "mood": "a"}).status_code == 400
    assert client.put("/api/weekly-review", headers=h, json={**ok, "week": "2026-11-02"}).status_code == 400  # a week that has not started
    assert client.put("/api/weekly-review", headers=h, json={**ok, "week": "next"}).status_code == 400
    assert client.get("/api/weekly-review", headers=h).json()["due"] is True  # Friday and no review
    monkeypatch.setattr(plan, "today", lambda: dt.date(2026, 10, 7))  # a Wednesday
    assert client.get("/api/weekly-review", headers=h).json()["due"] is False


# ------------------------------------------------------------------ journal
def test_a_journal_entry_links_papers_and_unknown_links_are_dropped(client, auth_headers, fake_ai, friday, sample_pdfs):
    h = auth_headers
    a = upload(client, h, sample_pdfs["a.pdf"].path)
    wait_ready(client, h, a)
    r = client.post("/api/journal", headers=h, json={"kind": "decision", "text": "I use a validation agent.", "paper_ids": [a, "nothing"], "card_ids": ["nothing"]}).json()
    assert r["paper_ids"] == [a] and r["card_ids"] == [] and r["xp_gained"] == 3 and r["date"] == "2026-10-09"
    assert client.post("/api/journal", headers=h, json={"kind": "joke", "text": "x"}).status_code == 400
    assert client.post("/api/journal", headers=h, json={"kind": "idea", "text": "  "}).status_code == 400
    listing = client.get("/api/journal", headers=h).json()
    assert listing[0]["label"] == "Decision" and listing[0]["papers"][0]["title"] == "AUTOMA: Multi-agent threat hunting"
    assert client.get("/api/journal?kind=idea", headers=h).json() == [] and client.get("/api/journal?kind=x", headers=h).status_code == 400
    e = client.put(f"/api/journal/{r['id']}", headers=h, json={"text": "I use two agents."}).json()
    assert e["text"] == "I use two agents." and e["kind"] == "decision" and e["paper_ids"] == [a]
    client.delete(f"/api/journal/{r['id']}", headers=h)
    assert client.get("/api/journal", headers=h).json() == []


def test_a_journal_gives_points_for_5_entries_a_day_at_most(client, auth_headers, friday):
    h = auth_headers
    gained = [client.post("/api/journal", headers=h, json={"kind": "idea", "text": f"Idea {i}"}).json()["xp_gained"] for i in range(7)]
    assert gained == [3, 3, 3, 3, 3, 0, 0] and client.get("/api/game", headers=h).json()["xp"] == 15


def test_the_journal_fills_the_map_regions(client, auth_headers, friday):
    h = auth_headers
    assert journey.method_workshop()["percent"] == 0 and "Plan tab" in journey.method_workshop()["first_step"]
    for i in range(5):
        client.post("/api/journal", headers=h, json={"kind": "decision", "text": f"Decision {i}"})
    client.post("/api/journal", headers=h, json={"kind": "idea", "text": "An idea does not fill a region"})
    client.post("/api/journal", headers=h, json={"kind": "experiment", "text": "Test 1"})
    client.post("/api/journal", headers=h, json={"kind": "result", "text": "Result 1"})
    regions = {r["code"]: r for r in client.get("/api/journey/map", headers=h).json()["regions"]}
    assert regions["workshop"]["percent"] == 50 and regions["mines"]["percent"] == 20 and regions["workshop"]["target"] == "plan"


def test_the_plan_and_the_journal_are_in_the_backup(client, auth_headers, fake_ai, friday):
    h = auth_headers
    m = client.post("/api/milestones", headers=h, json={"title": "First paper", "due": "2026-12-15"}).json()
    client.post(f"/api/milestones/{m['id']}/split", headers=h)
    client.put("/api/weekly-review", headers=h, json={"done": "x", "mood": 5})
    client.post("/api/journal", headers=h, json={"kind": "result", "text": "A result"})
    before = (client.get("/api/plan", headers=h).json(), client.get("/api/weekly-review", headers=h).json(), client.get("/api/journal", headers=h).json())
    backup = client.get("/api/export", headers=h).json()
    assert len(backup["milestones"]) == 1 and len(backup["milestone_tasks"]) == 4 and len(backup["weekly_reviews"]) == 1 and len(backup["journal"]) == 1
    with db.conn() as c:
        for t in ("milestones", "milestone_tasks", "weekly_reviews", "journal"):
            c.execute(f"DELETE FROM {t}")
    client.post("/api/import", headers=h, json=backup)
    client.post("/api/import", headers=h, json=backup)  # a second restore adds nothing
    after = (client.get("/api/plan", headers=h).json(), client.get("/api/weekly-review", headers=h).json(), client.get("/api/journal", headers=h).json())
    assert [len(x) for x in after[2:]] == [1] and len(after[0]["milestones"][0]["tasks"]) == 4 and len(after[1]["reviews"]) == 1 and after[0]["milestones"][0]["title"] == before[0]["milestones"][0]["title"]


def test_the_plan_switch_turns_the_plan_off(client, auth_headers):
    h = auth_headers
    client.put("/api/features", headers=h, json={"features": {"plan": False}})
    for path in ("/api/plan", "/api/weekly-review", "/api/journal"):
        assert client.get(path, headers=h).status_code == 403
