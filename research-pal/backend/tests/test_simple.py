"""Simple mode (A3): the simple version of a text of the AI. The server keeps the original when a number or a name changes."""
from app import db as db_mod, llm, ste
from helpers import upload, wait_ready

RESULT = "Precision is 91.4 percent. Recall is 95.0 percent."
SIMPLE_FAKE = "You help a student who is new to a research field"  # the start of the prompt of the simple editor
LONG = "The system reads the logs of the network and then it sends the logs to the second agent which checks each one today."
GOOD = "The system reads the logs. It sends each log to the second agent."


def test_simple_level_has_a_lower_limit():
    ten = "The system reads the logs and sends them to the agent."  # 11 words
    eighteen = "The system reads the logs of the network and then it sends the logs to the second agent today."  # 18 words
    assert len(ten.split()) <= 12 < len(eighteen.split()) <= 20
    assert ste.lint(ten, "simple") == [] and ste.lint(eighteen) == []  # the standard level allows 20 words
    assert any("maximum is 12" in p for p in ste.lint(eighteen, "simple"))


def test_a_rewrite_that_changes_a_number_is_refused(fake_ai):
    old = "The system reaches 91.4% precision on OpTC and it also reaches 84.2% recall which is a good result for the analysts of the team."
    fake_ai.when("technical editor", {"a": "The system reaches 90% precision on OpTC. It reaches 84.2% recall. The result is good."})
    assert ste.enforce({"a": old}, "simple") == {}


def read(client, h, sample_pdfs, **form):
    pid = upload(client, h, sample_pdfs["a.pdf"].path, **form)
    return pid, wait_ready(client, h, pid)


def test_simplify_a_field(client, auth_headers, fake_ai, sample_pdfs):
    pid, got = read(client, auth_headers, sample_pdfs)
    answer = got["card"]["fields"]["method"]["answer"]
    fake_ai.when(SIMPLE_FAKE, {"text": "Two agents work together. One agent proposes ideas. One agent tests them."})
    r = client.post(f"/api/papers/{pid}/simplify", headers=auth_headers, json={"field": "method"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["ok"] is True and out["text"].startswith("Two agents work together.") and out["label"] == "AI simplification" and out["message"] == ""
    assert db_mod.get_card(pid)["fields"]["method"]["answer"] == answer  # the card is not changed


def test_truth_a_changed_number_keeps_the_original(client, auth_headers, fake_ai, sample_pdfs):
    pid, got = read(client, auth_headers, sample_pdfs)
    original = got["card"]["fields"]["result"]["answer"]
    assert original == RESULT
    fake_ai.when(SIMPLE_FAKE, {"text": "Precision is 90 percent. Recall is 95.0 percent."})  # 91.4 became 90
    out = client.post(f"/api/papers/{pid}/simplify", headers=auth_headers, json={"field": "result"}).json()
    assert out["ok"] is False and out["reason"] == "changed_fact" and out["text"] == original
    assert "kept the original" in out["message"]


def test_truth_a_new_number_or_a_lost_name_keeps_the_original(fake_ai):
    fake_ai.when(SIMPLE_FAKE, {"text": "Precision is 91.4 percent. Recall is 95.0 percent. The test used 3 runs."})  # a new number
    assert ste.simplify(RESULT)["reason"] == "changed_fact"
    fake_ai.when(SIMPLE_FAKE, {"text": "The tool reaches good precision."})  # AUTOMA is lost
    out = ste.simplify("AUTOMA reaches a precision of 91.4 percent.")
    assert out["ok"] is False and out["text"] == "AUTOMA reaches a precision of 91.4 percent."


def test_long_sentences_get_one_more_try(fake_ai):
    answers = iter([{"text": LONG}, {"text": GOOD}])
    fake_ai.when(SIMPLE_FAKE, lambda messages: next(answers))
    out = ste.simplify(LONG)
    assert out == {"text": GOOD, "ok": True, "reason": ""} and len(fake_ai.calls) == 2
    assert "problems" in fake_ai.calls[1]["user"]  # the second call lists the problems


def test_an_answer_that_is_not_simpler_is_refused(fake_ai):
    fake_ai.when(SIMPLE_FAKE, {"text": LONG})
    assert ste.simplify(LONG)["reason"] == "not_simple" and len(fake_ai.calls) == 2


def test_the_text_of_the_student_is_never_rewritten(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid, _ = read(client, h, sample_pdfs, purpose="How do others validate hypotheses?")
    n = len(fake_ai.calls)
    assert client.post(f"/api/papers/{pid}/simplify", headers=h, json={"field": "question"}).status_code == 400  # the question of the student
    client.patch(f"/api/papers/{pid}/card", headers=h, json={"fields": {"problem": "My own words about the problem."}})
    assert client.post(f"/api/papers/{pid}/simplify", headers=h, json={"field": "problem"}).status_code == 400  # an edit of the student
    assert len(fake_ai.calls) == n


def test_bad_requests(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid, _ = read(client, h, sample_pdfs)
    assert client.post(f"/api/papers/{pid}/simplify", headers=h, json={"field": "nope"}).status_code == 400
    assert client.post(f"/api/papers/{pid}/simplify", headers=h, json={"field": "limitation"}).status_code == 400  # hidden: no text
    assert client.post(f"/api/papers/{pid}/simplify", headers=h, json={"field": "method", "card_id": "nope"}).status_code == 404
    assert client.post("/api/papers/nope/simplify", headers=h, json={"field": "method"}).status_code == 404
    assert client.post("/api/simplify", headers=h, json={"text": "  "}).status_code == 400
    assert client.post("/api/simplify", headers=h, json={"text": "x" * 3001}).status_code == 400
    assert client.post("/api/simplify", json={"text": "x"}).status_code == 401


def test_simplify_a_text_of_the_chat_and_a_text_of_the_card(client, auth_headers, fake_ai, sample_pdfs):
    pid, _ = read(client, auth_headers, sample_pdfs)
    out = client.post("/api/simplify", headers=auth_headers, json={"text": "AUTOMA reaches 91.4 percent precision."}).json()
    assert out["ok"] is True and out["text"] == "Simple: AUTOMA reaches 91.4 percent precision."
    assert client.post(f"/api/papers/{pid}/simplify", headers=auth_headers, json={"field": "verdict_reason"}).json()["ok"] is True
    fake_ai.when(SIMPLE_FAKE, {"text": "AUTOMA reaches 99 percent precision."})
    assert client.post("/api/simplify", headers=auth_headers, json={"text": "AUTOMA reaches 91.4 percent precision."}).json()["ok"] is False


def test_an_ai_error_gives_error_502(client, auth_headers, fake_ai, sample_pdfs):
    pid, _ = read(client, auth_headers, sample_pdfs)
    fake_ai.when(SIMPLE_FAKE, llm.LLMError("The AI is down."))
    r = client.post(f"/api/papers/{pid}/simplify", headers=auth_headers, json={"field": "method"})
    assert r.status_code == 502 and "down" in r.json()["detail"]


def test_the_switch_turns_simple_mode_off(client, auth_headers, fake_ai, sample_pdfs):
    pid, _ = read(client, auth_headers, sample_pdfs)
    client.put("/api/features", headers=auth_headers, json={"features": {"simple": False}})
    assert client.post(f"/api/papers/{pid}/simplify", headers=auth_headers, json={"field": "method"}).status_code == 403
    assert client.post("/api/simplify", headers=auth_headers, json={"text": "x y"}).status_code == 403


def test_the_second_request_uses_the_saved_answer(client, auth_headers, fake_ai, sample_pdfs, http_ai):
    pid, _ = read(client, auth_headers, sample_pdfs)  # the card is made with the fake AI
    http_ai.answer = {"text": "Two agents work together."}
    http_ai.activate()  # from here, the real llm.py runs with a fake provider
    body = {"field": "method"}
    assert client.post(f"/api/papers/{pid}/simplify", headers=auth_headers, json=body).json()["text"] == "Two agents work together."
    assert len(http_ai.calls) == 1
    assert client.post(f"/api/papers/{pid}/simplify", headers=auth_headers, json=body).json()["text"] == "Two agents work together."
    assert len(http_ai.calls) == 1  # no AI call
