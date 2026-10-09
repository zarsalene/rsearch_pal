"""End-to-end test with a fake AI. It checks: PDF reading, quote checks, hiding of false claims, search, links, export and import."""
import time

from app import cards as cards_mod, chat as chat_mod, db as db_mod, pdf as pdf_mod
from helpers import login, upload, wait_ready


def test_all(client, fake_ai, sample_pdfs):
    assert client.get("/api/papers").status_code == 401
    assert client.post("/api/login", json={"password": "wrong"}).status_code == 401
    h = login(client)
    assert client.get("/api/config", headers=h).json()["llm_ready"] is True
    assert client.put("/api/settings", headers=h, json={"thesis_question": "Do validation agents reduce false hypotheses?"}).status_code == 200

    # a text file with a .pdf name is refused
    r = client.post("/api/papers", headers=h, files={"file": ("x.pdf", b"hello", "application/pdf")})
    assert r.status_code == 400

    ids = {}
    for name, pdf_file in sample_pdfs.items():
        ids[name] = upload(client, h, pdf_file.path, purpose="How do others validate hypotheses?")
    a = wait_ready(client, h, ids["a.pdf"])
    b = wait_ready(client, h, ids["b.pdf"])
    assert a["paper"]["status"] == "ready", a["paper"]["error"]
    f = a["card"]["fields"]
    assert f["problem"]["status"] == "verified" and f["problem"]["evidence"][0]["verified"]
    assert f["method"]["status"] == "verified" and f["method"]["evidence"][0]["page"] == 2
    assert f["result"]["status"] == "check" and "95.0" in f["result"]["unverified_numbers"], f["result"]
    assert f["limitation"]["status"] == "unverified" and f["limitation"]["answer"] == "" and "encrypted" in f["limitation"]["draft"]
    assert f["question"]["status"] == "yours" and f["use"]["status"] == "suggestion"
    assert "quantum blockchain" not in a["card"]["keywords"] and "Sysmon" in a["card"]["keywords"]
    assert b["card"]["fields"]["problem"]["status"] == "not_stated"
    assert a["paper"]["title"].startswith("AUTOMA")

    # search finds the right passage and page
    s = client.get("/api/search", headers=h, params={"q": "precision recall OpTC dataset"}).json()
    assert s and s[0]["paper_id"] == ids["a.pdf"] and s[0]["page"] == 3, s[:1]
    # references are not indexed
    assert not any("firewalls" in x["text"] for x in client.get("/api/search", headers=h, params={"q": "Old paper about firewalls"}).json() if x["paper_id"] == ids["a.pdf"])

    g = client.get("/api/graph", headers=h).json()
    assert len(g["nodes"]) == 2

    # no focus given: no focus field
    assert "focus" not in f and a["card"]["focus"] == ""
    # focus topic: the card gets a checked focus field, and the topic is saved with the paper
    assert client.post(f"/api/papers/{ids['a.pdf']}/regenerate", headers=h, json={"focus": "Sysmon logs"}).status_code == 200
    af = wait_ready(client, h, ids["a.pdf"])
    assert af["paper"]["status"] == "ready", af["paper"]["error"]
    assert af["paper"]["focus"] == "Sysmon logs" and af["card"]["focus"] == "Sysmon logs"
    ff = af["card"]["fields"]["focus"]
    assert ff["status"] == "verified" and ff["evidence"][0]["page"] == 2, ff
    # the word search puts the right passage first
    chunks = pdf_mod.chunk_pages(db_mod.get_pages(ids["a.pdf"]))
    hit = cards_mod.focus_hits([c for c in chunks if not c["refs"]], "Sysmon logs")
    assert hit and hit[0]["page"] == 2, hit
    # an empty focus turns the mode off
    assert client.post(f"/api/papers/{ids['a.pdf']}/regenerate", headers=h, json={"focus": ""}).status_code == 200
    assert "focus" not in wait_ready(client, h, ids["a.pdf"])["card"]["fields"]

    # more cards for one paper: each has its own focus, status and edits. No new upload.
    pa = ids["a.pdf"]
    assert client.post(f"/api/papers/{pa}/cards", headers=h, json={}).status_code == 400
    r = client.post(f"/api/papers/{pa}/cards", headers=h, json={"focus": "Sysmon logs"})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    for _ in range(100):
        x = client.get(f"/api/papers/{pa}/cards/{cid}", headers=h).json()
        if x["paper"]["status"] in ("ready", "error"):
            break
        time.sleep(0.1)
    assert x["paper"]["status"] == "ready", x["paper"]["error"]
    assert x["paper"]["focus"] == "Sysmon logs" and x["card"]["focus"] == "Sysmon logs"
    assert x["card"]["fields"]["focus"]["status"] == "verified"
    first = client.get(f"/api/papers/{pa}", headers=h).json()
    assert first["card"]["focus"] == "" and [c["id"] for c in first["card_list"]] == ["", cid]
    assert client.post(f"/api/papers/{pa}/cards", headers=h, json={"focus": "sysmon LOGS"}).status_code == 409
    r = client.patch(f"/api/papers/{pa}/cards/{cid}", headers=h, json={"fields": {"problem": "My own words."}})
    assert r.json()["fields"]["problem"]["status"] == "edited"
    assert client.get(f"/api/papers/{pa}", headers=h).json()["card"]["fields"]["problem"]["status"] != "edited"  # the first card is not changed
    exp_x = client.get("/api/export", headers=h).json()["papers"]
    assert [e["focus"] for p in exp_x if p["id"] == pa for e in p["extra_cards"]] == ["Sysmon logs"]
    assert client.delete(f"/api/papers/{pa}/cards/{cid}", headers=h).status_code == 200
    assert client.get(f"/api/papers/{pa}/cards/{cid}", headers=h).status_code == 404
    assert len(client.get(f"/api/papers/{pa}", headers=h).json()["card_list"]) == 1
    # edit by the user
    r = client.patch(f"/api/papers/{ids['a.pdf']}/card", headers=h, json={"fields": {"limitation": "One dataset only (page 3)."}})
    assert r.json()["fields"]["limitation"]["status"] == "edited"

    # chat: answers carry quotes that the server checks. Wrong input is refused.
    pa, pb = ids["a.pdf"], ids["b.pdf"]
    r = client.post("/api/chat", headers=h, json={"question": "What precision does AUTOMA reach?", "paper_ids": [pa, pb]})
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["status"] == "check" and "99.9" in c["unverified_numbers"] and "91.4" not in c["unverified_numbers"], c
    assert [e["verified"] for e in c["evidence"]] == [True, False] and c["evidence"][0]["paper_id"] == pa and c["evidence"][0]["page"] == 3
    qs = chat_mod.paper_queries("what is the link between them?", [db_mod.get_paper(pa), db_mod.get_paper(pb)], [db_mod.get_card(pa), db_mod.get_card(pb)])
    assert "AUTOMA" in qs[0] and "pasta" in qs[1].lower(), qs
    assert "AUTOMA" not in chat_mod.paper_queries("a long question that already has many topic words in it", [db_mod.get_paper(pa)], [None])[0]
    assert "Overview of paper 1" in chat_mod.overview(1, db_mod.get_card(pa))
    assert client.post("/api/chat", headers=h, json={"question": "INVENT", "paper_ids": [pa]}).json()["status"] == "unverified"
    assert client.post("/api/chat", headers=h, json={"question": "NOTHING here", "paper_ids": [pa]}).json()["status"] == "no_evidence"
    assert client.post("/api/chat", headers=h, json={"question": "x y", "paper_ids": []}).status_code == 400
    assert client.post("/api/chat", headers=h, json={"question": "x y", "paper_ids": ["nope"]}).status_code == 400
    assert client.post("/api/chat", headers=h, json={"question": "x y", "paper_ids": [pa] * 3, "history": [{"role": "user", "content": "q"}, {"role": "x", "content": "bad"}]}).status_code == 200
    # add the answer to a card: only the verified quote is kept. A new reading keeps the note.
    r = client.post(f"/api/papers/{pa}/notes", headers=h, json={"question": "q", "answer": c["answer"], "evidence": c["evidence"]})
    assert r.status_code == 200, r.text
    notes = r.json()["notes"]
    assert len(notes) == 1 and len(notes[0]["evidence"]) == 1 and notes[0]["evidence"][0]["page"] == 3
    assert client.post(f"/api/papers/{pa}/notes", headers=h, json={"answer": " "}).status_code == 400
    assert client.post(f"/api/papers/{pa}/regenerate", headers=h, json={}).status_code == 200
    assert len(wait_ready(client, h, pa)["card"]["notes"]) == 1
    assert client.delete(f"/api/papers/{pa}/notes/{notes[0]['id']}", headers=h).json()["notes"] == []

    # link explanation: both quotes are checked against their own paper. The answer is saved for the pair.
    r = client.post("/api/links/explain", headers=h, json={"a": pb, "b": pa})
    assert r.status_code == 200, r.text
    ex = r.json()
    assert ex["relation"] == "same_method" and ex["shared"] == ["methods", "tests"] and ex["status"] == "verified", ex
    assert [e["verified"] for e in ex["evidence"]] == [True, True] and {e["paper_id"] for e in ex["evidence"]} == {pa, pb}
    assert client.post("/api/links/explain", headers=h, json={"a": pa, "b": pb}).json()["generated_at"] == ex["generated_at"]  # saved
    assert client.post("/api/links/explain", headers=h, json={"a": pa, "b": pb, "refresh": True}).json()["generated_at"] > ex["generated_at"]
    assert client.post("/api/links/explain", headers=h, json={"a": pa, "b": pa}).status_code == 400
    assert client.post("/api/links/explain", headers=h, json={"a": pa, "b": "nope"}).status_code == 404

    # mind map: built from the cards, with no AI call. The status and the quotes come from the cards.
    n_ai = len(fake_ai.calls)
    r = client.post(f"/api/papers/{pa}/mindmap", headers=h)
    assert r.status_code == 200, r.text
    nodes = {n["id"]: n for n in r.json()["mindmap"]["nodes"]}
    assert list(nodes) == ["problem", "method", "result", "limitation"] and all(n["parent"] == "root" for n in nodes.values()), list(nodes)
    assert nodes["method"]["status"] == "verified" and nodes["method"]["evidence"][0]["page"] == 2
    assert nodes["result"]["status"] == "check" and "95.0" in nodes["result"]["unverified_numbers"]
    assert nodes["limitation"]["status"] == "unverified" and nodes["limitation"]["answer"] == "" and nodes["limitation"]["draft"]  # a hidden claim stays hidden
    assert len(fake_ai.calls) == n_ai, "the mind map must not call the AI"
    # several cards: one branch for each card. The map of the paper follows the cards.
    xr = client.post(f"/api/papers/{pa}/cards", headers=h, json={"focus": "Sysmon logs"})
    xid = xr.json()["id"]
    for _ in range(100):
        if client.get(f"/api/papers/{pa}/cards/{xid}", headers=h).json()["paper"]["status"] == "ready":
            break
        time.sleep(0.1)
    got = client.get(f"/api/papers/{pa}", headers=h).json()["card"]["mindmap"]["nodes"]  # read again: the map is rebuilt from both cards
    by = {n["id"]: n for n in got}
    assert by["c0"]["label"] == "Whole paper" and by["c1"]["label"] == "Sysmon logs" and by["c1"]["status"] == "verified", list(by)
    assert by["c1.method"]["parent"] == "c1" and "c1.focus" not in by and by["c0.limitation"]["parent"] == "c0"
    n_calls = len(fake_ai.calls)
    xm = client.post(f"/api/papers/{pa}/cards/{xid}/mindmap", headers=h).json()["mindmap"]["nodes"]
    assert len(fake_ai.calls) == n_calls, "the mind map must not call the AI"
    assert [n["id"] for n in xm] == ["focus", "problem", "method", "result", "limitation"]
    assert client.delete(f"/api/papers/{pa}/cards/{xid}", headers=h).status_code == 200
    assert len(client.get(f"/api/papers/{pa}", headers=h).json()["card"]["mindmap"]["nodes"]) == 4  # back to one card
    assert client.post(f"/api/papers/{pa}/regenerate", headers=h, json={}).status_code == 200
    assert len(wait_ready(client, h, pa)["card"]["mindmap"]["nodes"]) == 4  # a new reading keeps the map
    assert "mindmap" not in client.delete(f"/api/papers/{pa}/mindmap", headers=h).json()

    # fields that were "not found" (the AI saw only a part of the paper): search again with excerpts chosen for them
    c0 = db_mod.get_card(pa)
    for n in ("problem", "result"):
        c0["fields"][n] = {"answer": cards_mod.NOT_FOUND, "status": "not_found", "kind": "paper", "evidence": [], "draft": "", "unverified_numbers": [], "edited": False}
    c0["fields"]["method"]["status"] = "edited"
    db_mod.save_card(pa, c0)
    r = client.post(f"/api/papers/{pa}/fill", headers=h, json={"fields": ["problem", "method"]})  # "method" has an answer: it is not touched
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["filled"] == ["problem"] and out["missing"] == ["result"], out
    assert out["card"]["fields"]["problem"]["status"] == "verified" and out["card"]["fields"]["problem"]["evidence"][0]["verified"]
    assert out["card"]["fields"]["method"]["status"] == "edited" and out["card"]["fields"]["result"]["status"] == "not_found"
    assert client.post(f"/api/papers/{pa}/fill", headers=h, json={}).json()["filled"] in ([], ["result"])  # all missing fields, one more try
    assert client.post(f"/api/papers/nope/fill", headers=h, json={}).status_code == 404

    # backup and restore into a clean store
    exp = client.get("/api/export", headers=h).json()
    assert len(exp["papers"]) == 2
    for pid in ids.values():
        assert client.delete(f"/api/papers/{pid}", headers=h).status_code == 200
    assert client.get("/api/papers", headers=h).json() == []
    assert db_mod.get_setting(f"link:{min(pa, pb)}:{max(pa, pb)}") == ""  # saved link explanations are removed with the paper
    assert client.post("/api/import", headers=h, json=exp).json()["added"] == 2
    for pid in ids.values():
        assert wait_ready(client, h, pid)["paper"]["status"] == "ready"
    s = client.get("/api/search", headers=h, params={"q": "tomato sauce basil"}).json()
    assert s and s[0]["paper_id"] == ids["b.pdf"]
    print("ALL TESTS PASSED")
