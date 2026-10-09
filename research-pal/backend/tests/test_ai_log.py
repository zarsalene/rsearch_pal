"""AI use log (H1): one row for each answer of an AI provider. A saved answer writes no row."""
from fake_ai import default_answers
from helpers import upload, wait_ready


def test_each_ai_call_writes_one_row_and_a_saved_answer_writes_none(client, auth_headers, sample_pdfs, http_ai):
    h = auth_headers
    http_ai.answer = lambda body: default_answers(body["messages"])
    http_ai.activate()
    assert client.get("/api/ai-log", headers=h).json() == {"total": 0, "by_feature": {}, "rows": []}

    pid = upload(client, h, sample_pdfs["a.pdf"].path)
    wait_ready(client, h, pid)
    log = client.get("/api/ai-log", headers=h).json()
    assert log["total"] == len(http_ai.calls) > 0  # one row for each call
    assert set(log["by_feature"]) == {"card"} and {r["paper_id"] for r in log["rows"]} == {pid}
    assert {(r["provider"], r["model"]) for r in log["rows"]} == {("groq", "llama-3.3-70b-versatile")}
    assert all(r["time"] > 0 for r in log["rows"])

    n_calls = len(http_ai.calls)
    body = {"question": "What precision does AUTOMA reach?", "paper_ids": [pid]}
    assert client.post("/api/chat", headers=h, json=body).status_code == 200
    chat_calls = len(http_ai.calls) - n_calls
    assert chat_calls >= 1
    assert client.get("/api/ai-log", headers=h).json()["by_feature"]["chat"] == chat_calls
    row = [r for r in client.get("/api/ai-log", headers=h).json()["rows"] if r["feature"] == "chat"][0]
    assert row["paper_id"] == pid

    before = client.get("/api/ai-log", headers=h).json()["total"]
    assert client.post("/api/chat", headers=h, json=body).status_code == 200  # the same question: a saved answer
    assert len(http_ai.calls) == n_calls + chat_calls  # no new request to the provider
    assert client.get("/api/ai-log", headers=h).json()["total"] == before  # and no new row


def test_each_feature_has_its_own_name(client, auth_headers, sample_pdfs, http_ai):
    h = auth_headers
    http_ai.answer = lambda body: default_answers(body["messages"])
    http_ai.activate()
    a = upload(client, h, sample_pdfs["a.pdf"].path)
    b = upload(client, h, sample_pdfs["b.pdf"].path)
    wait_ready(client, h, a)
    wait_ready(client, h, b)
    client.post(f"/api/papers/{a}/simplify", headers=h, json={"field": "method"})
    client.post(f"/api/papers/{a}/define", headers=h, json={"term": "ontology"})
    client.post("/api/links/explain", headers=h, json={"a": a, "b": b})
    assert {"card", "simplify", "define", "link"} <= set(client.get("/api/ai-log", headers=h).json()["by_feature"])
    assert len(client.get("/api/ai-log", headers=h, params={"limit": 2}).json()["rows"]) == 2
    assert client.get("/api/ai-log").status_code == 401


def test_the_log_is_in_the_backup_and_a_second_import_adds_nothing(client, auth_headers, sample_pdfs, http_ai):
    h = auth_headers
    http_ai.answer = lambda body: default_answers(body["messages"])
    http_ai.activate()
    wait_ready(client, h, upload(client, h, sample_pdfs["a.pdf"].path))
    backup = client.get("/api/export", headers=h).json()
    total = client.get("/api/ai-log", headers=h).json()["total"]
    assert len(backup["ai_log"]) == total > 0
    client.post("/api/import", headers=h, json=backup)
    assert client.get("/api/ai-log", headers=h).json()["total"] == total  # the rows exist already
