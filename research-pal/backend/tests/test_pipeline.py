"""End-to-end test with a fake AI. It checks: PDF reading, quote checks, hiding of false claims, search, links, export and import."""
import os, sys, tempfile, time
from pathlib import Path

tmp = tempfile.mkdtemp()
os.environ.update(DATA_DIR=tmp, APP_PASSWORD="test-password-123", SECRET_KEY="x" * 40, EMBEDDING_BACKEND="hash",
                  GROQ_API_KEY="fake", GEMINI_API_KEY="", LLM_PROVIDER="gemini", LLM_FALLBACK="groq", LLM_MODEL="", LLM_API_KEY="",MIN_TEXT_CHARS="200", FRONTEND_ORIGIN="http://localhost:5173")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app import llm, main

PAPERS = {
    "a.pdf": ("AUTOMA: Multi-agent threat hunting", [
        "AUTOMA: Multi-agent threat hunting\nAbstract\nWe present AUTOMA, a multi agent system for cyber threat hunting. Analysts spend many hours on manual log review and miss attacks.",
        "Method\nOur system uses a hypothesis agent and a validation agent. The hypothesis agent reads Sysmon logs and proposes attack hypotheses that map to MITRE ATT&CK techniques.",
        "Results\nOn the OpTC dataset, AUTOMA reaches a precision of 91.4 percent and a recall of 84.2 percent. The baseline reaches 72.0 percent precision on the same logs.\nLimitations\nWe test only on one dataset. Future work will add more datasets and real networks.",
        "Conclusion\nThe multi agent design reduces manual work for threat hunting analysts.\nReferences\n[1] Smith. Old paper about firewalls. 2001.",
    ]),
    "b.pdf": ("Cooking pasta with tomatoes", [
        "Cooking pasta with tomatoes\nAbstract\nThis paper explains how to cook pasta with tomato sauce and basil for dinner. Boil water with salt and add the pasta.",
        "Method\nWe boil the pasta for nine minutes and stir the tomato sauce slowly with fresh basil leaves.",
        "Results\nTen testers liked the dish. The sauce tastes better with basil and olive oil.",
        "Conclusion\nPasta with tomato sauce is easy to cook at home and cheap for students.",
    ]),
}


def make_pdf(path, pages):
    c = canvas.Canvas(str(path), pagesize=A4)
    for text in pages:
        y = 800
        for line in text.split("\n"):
            while line:
                c.drawString(50, y, line[:95]); line = line[95:]; y -= 16
        c.showPage()
    c.save()


def fake_chat(messages, max_tokens=2500):
    user = messages[-1]["content"]
    system = messages[0]["content"]
    if "You make a mind map" in system:
        def node(i, parent, label, quote, page, text="Explained."):
            return {"id": i, "parent": parent, "label": label, "explanation": text, "evidence": [{"quote": quote, "page": page}]}
        return {"nodes": [
            node("1", "root", "Problem", "Analysts spend many hours on manual log review and miss attacks.", 1),
            node("2", "root", "Method", "Our system uses a hypothesis agent and a validation agent.", 2),
            node("2.1", "2", "Hypothesis agent", "The hypothesis agent reads Sysmon logs and proposes attack hypotheses", 2),
            node("3", "root", "Results", "AUTOMA reaches a precision of 91.4 percent and a recall of 84.2 percent.", 3, "Precision is 77.7 percent."),
            node("4", "root", "Limits", "The system completely fails on encrypted network traffic in all cases.", 3),
            node("5", "nowhere", "Wrong parent", "Analysts spend many hours on manual log review and miss attacks.", 1),  # dropped: the parent does not exist
            node("2.1.1", "2.1", "Too deep", "Analysts spend many hours on manual log review and miss attacks.", 1),  # dropped: level 3
        ]}
    if "You explain how two papers" in system:
        auto = 1 if "Paper 1: AUTOMA" in user else 2
        return {"relation": " SAME_METHOD ", "summary": "Both papers talk about methods.", "shared": ["methods", "", "tests"], "differences": "One is about threats. One is about food.",
                "evidence": [{"paper": auto, "quote": "Analysts spend many hours on manual log review and miss attacks.", "page": 1},
                             {"paper": 3 - auto, "quote": "We boil the pasta for nine minutes and stir the tomato sauce", "page": 2}]}
    if "<papers>" in user:  # the chat
        bad = {"paper": 1, "quote": "The system completely fails on encrypted network traffic in all cases.", "page": 3}
        good = {"paper": 1, "quote": "AUTOMA reaches a precision of 91.4 percent and a recall of 84.2 percent.", "page": 3}
        if "INVENT" in user:
            return {"answer": "The system fails on encrypted traffic.", "evidence": [bad]}
        if "NOTHING" in user:
            return {"answer": "I did not find it in the passages.", "evidence": []}
        return {"answer": "AUTOMA reaches a precision of 91.4 percent. The recall is 99.9 percent.", "evidence": [good, bad]}
    if "<focus>" in user:
        # the focus rules and the focus line in the answer shape must reach the AI
        assert "FOCUS MODE" in messages[0]["content"] and '"focus":' in user
        assert "<focus>Sysmon logs</focus>" in user
        base = fake_chat([messages[0], {"role": "user", "content": user.replace("<focus>", "")}], max_tokens)
        base["focus"] = {"answer": "The hypothesis agent reads Sysmon logs.", "evidence": [{"quote": "The hypothesis agent reads Sysmon", "page": 2}]}
        return base
    if "AUTOMA" in user:
        return {
            "title": "AUTOMA: Multi-agent threat hunting", "keywords": ["threat hunting", "multi agent", "Sysmon", "quantum blockchain"],
            "verdict": "read", "verdict_reason": "Direct baseline.", "question": "",
            "problem": {"answer": "Analysts spend many hours on manual log review.", "evidence": [{"quote": "Analysts spend many hours on manual log review and miss attacks.", "page": 1}]},
            "method": {"answer": "A hypothesis agent and a validation agent work together.", "evidence": [{"quote": "Our system uses a hypothesis agent and a validation agent.", "page": 2}]},
            # false number: 95.0 is NOT in the paper
            "result": {"answer": "Precision is 91.4 percent. Recall is 95.0 percent.", "evidence": [{"quote": "AUTOMA reaches a precision of 91.4 percent and a recall of 84.2 percent.", "page": 3}]},
            # invented quote: must be hidden
            "limitation": {"answer": "The system fails on encrypted traffic.", "evidence": [{"quote": "The system completely fails on encrypted network traffic in all cases.", "page": 3}]},
            "inferred_limitations": "One dataset only.", "use": "It is the baseline for the thesis.",
        }
    return {
        "title": "Cooking pasta with tomatoes", "keywords": ["pasta", "tomato sauce", "basil"], "verdict": "skip", "verdict_reason": "Not related.", "question": "",
        "problem": {"answer": "Not stated in the paper.", "evidence": []},
        "method": {"answer": "Boil the pasta for nine minutes.", "evidence": [{"quote": "We boil the pasta for nine minutes and stir the tomato sauce", "page": 2}]},
        "result": {"answer": "Ten testers liked the dish.", "evidence": [{"quote": "Ten testers liked the dish. The sauce tastes better with basil", "page": 3}]},
        "limitation": {"answer": "Not stated in the paper.", "evidence": []}, "inferred_limitations": "", "use": "No use.",
    }


REAL_CHAT_JSON = llm.chat_json
llm.chat_json = fake_chat
main.llm.chat_json = fake_chat


def wait_ready(client, h, pid):
    for _ in range(100):
        p = client.get(f"/api/papers/{pid}", headers=h).json()
        if p["paper"]["status"] in ("ready", "error"):
            return p
        time.sleep(0.1)
    raise AssertionError("timeout")


def test_all():
    with TestClient(main.app) as client:
        assert client.get("/api/papers").status_code == 401
        assert client.post("/api/login", json={"password": "wrong"}).status_code == 401
        token = client.post("/api/login", json={"password": "test-password-123"}).json()["token"]
        h = {"Authorization": "Bearer " + token}
        assert client.get("/api/config", headers=h).json()["llm_ready"] is True
        assert client.put("/api/settings", headers=h, json={"thesis_question": "Do validation agents reduce false hypotheses?"}).status_code == 200

        # the student chooses the AI: the order and the model of each provider. A wrong choice is refused. Keys never go through the page.
        cfg = client.get("/api/config", headers=h).json()
        assert cfg["ai_choice"]["primary"] == "gemini" and cfg["ai_choice"]["custom"] is False and {o["provider"] for o in cfg["ai_options"]} == {"gemini", "groq", "openrouter", "ollama"}
        assert "key" not in str(cfg["ai_options"]).lower().replace("ready", "")
        assert client.put("/api/ai", headers=h, json={"primary": "nope"}).status_code == 400
        assert client.put("/api/ai", headers=h, json={"primary": "groq", "models": {"groq": "bad model!"}}).status_code == 400
        cfg = client.put("/api/ai", headers=h, json={"primary": "groq", "fallbacks": ["gemini", "groq"], "models": {"groq": "openai/gpt-oss-20b"}}).json()
        assert cfg["ai_choice"] == {"primary": "groq", "fallbacks": ["gemini"], "models": {"groq": "openai/gpt-oss-20b", "gemini": "gemini-2.5-flash"}, "custom": True}, cfg["ai_choice"]
        assert [p["provider"] for p in cfg["providers"]] == ["groq", "gemini"] and cfg["model"] == "openai/gpt-oss-20b"
        llm.load_choice()  # the choice is saved in the database: it is the same after a restart
        assert llm.choice()["primary"] == "groq"
        cfg = client.delete("/api/ai", headers=h).json()
        assert cfg["ai_choice"]["primary"] == "gemini" and cfg["ai_choice"]["custom"] is False

        # a text file with a .pdf name is refused
        r = client.post("/api/papers", headers=h, files={"file": ("x.pdf", b"hello", "application/pdf")})
        assert r.status_code == 400

        ids = {}
        for name, (title, pages) in PAPERS.items():
            path = Path(tmp) / name
            make_pdf(path, pages)
            r = client.post("/api/papers", headers=h, files={"file": (name, path.read_bytes(), "application/pdf")}, data={"purpose": "How do others validate hypotheses?"})
            assert r.status_code == 200, r.text
            ids[name] = r.json()["id"]
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
        from app import cards as cards_mod, db as db_mod, pdf as pdf_mod
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
        from app import chat as chat_mod
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
        calls_before = []
        real_fake = llm.chat_json
        llm.chat_json = lambda *a, **k: calls_before.append(1) or real_fake(*a, **k)
        r = client.post(f"/api/papers/{pa}/mindmap", headers=h)
        assert r.status_code == 200, r.text
        nodes = {n["id"]: n for n in r.json()["mindmap"]["nodes"]}
        assert list(nodes) == ["problem", "method", "result", "limitation"] and all(n["parent"] == "root" for n in nodes.values()), list(nodes)
        assert nodes["method"]["status"] == "verified" and nodes["method"]["evidence"][0]["page"] == 2
        assert nodes["result"]["status"] == "check" and "95.0" in nodes["result"]["unverified_numbers"]
        assert nodes["limitation"]["status"] == "unverified" and nodes["limitation"]["answer"] == "" and nodes["limitation"]["draft"]  # a hidden claim stays hidden
        assert calls_before == [], "the mind map must not call the AI"
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
        n_calls = len(calls_before)
        xm = client.post(f"/api/papers/{pa}/cards/{xid}/mindmap", headers=h).json()["mindmap"]["nodes"]
        assert len(calls_before) == n_calls, "the mind map must not call the AI"
        assert [n["id"] for n in xm] == ["focus", "problem", "method", "result", "limitation"]
        assert client.delete(f"/api/papers/{pa}/cards/{xid}", headers=h).status_code == 200
        assert len(client.get(f"/api/papers/{pa}", headers=h).json()["card"]["mindmap"]["nodes"]) == 4  # back to one card
        assert client.post(f"/api/papers/{pa}/regenerate", headers=h, json={}).status_code == 200
        assert len(wait_ready(client, h, pa)["card"]["mindmap"]["nodes"]) == 4  # a new reading keeps the map
        assert "mindmap" not in client.delete(f"/api/papers/{pa}/mindmap", headers=h).json()
        llm.chat_json = real_fake

        # fields that were "not found" (the AI saw only a part of the paper): search again with excerpts chosen for them
        from app import cards as cards_mod2
        c0 = db_mod.get_card(pa)
        for n in ("problem", "result"):
            c0["fields"][n] = {"answer": cards_mod2.NOT_FOUND, "status": "not_found", "kind": "paper", "evidence": [], "draft": "", "unverified_numbers": [], "edited": False}
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


def test_reliability():
    """Size fallback, partial-text wording, quote repair and JSON retry."""
    from app import cards, config

    # 1. partial text: the field says "Not found in the excerpts", and the prompt tells the AI that the text is partial
    f = cards.verify_field({"answer": "Not stated in the paper.", "evidence": []}, [], "", False, complete=False)
    assert f["status"] == "not_found" and f["answer"] == cards.NOT_FOUND
    assert cards.verify_field({"answer": "Not found in the excerpts."}, [], "", False)["status"] == "not_stated"
    assert "only a PART" in cards.system_prompt(False, False) and "FULL text" in cards.system_prompt(True, False)
    assert "@" not in cards.system_prompt(True, True) and "FOCUS MODE" in cards.system_prompt(True, True)

    # ASD-STE100 rules reach the card prompt (also in focus mode) and the chat prompt
    from app import chat
    for p in (cards.system_prompt(True, False), cards.system_prompt(False, True), chat.SYSTEM):
        assert "ASD-STE100" in p and "maximum 20 words" in p and "active voice" in p and "@STE@" not in p

    # 2. the provider refuses the size: the server sends a smaller part, then stops at the minimum
    limits, calls = [], []
    real_build, real_chat = cards.build_context, cards.llm.chat_json
    cards.build_context = lambda pid, pages, chunks, q, focus="", limit=None: (limits.append(limit) or ("[page 1]\ntext", False))

    def too_large_twice(messages, max_tokens=None):
        calls.append(1)
        if len(calls) < 3:
            raise llm.LLMTooLarge("big")
        return {"ok": 1}

    cards.llm.chat_json = too_large_twice
    try:
        raw, _, complete = cards._ask("p", [], [], "", "", "")
        assert raw == {"ok": 1} and complete is False
        assert limits == [config.LLM_CONTEXT_CHARS, config.LLM_CONTEXT_CHARS // 2, config.LLM_CONTEXT_CHARS // 4], limits

        def always_large(messages, max_tokens=None):
            raise llm.LLMTooLarge("big")

        cards.llm.chat_json = always_large
        try:
            cards._ask("p", [], [], "", "", "")
            raise AssertionError("must stop")
        except llm.LLMError as e:
            assert not isinstance(e, llm.LLMTooLarge)
        assert limits[-1] == config.LLM_MIN_CONTEXT_CHARS

        # 3. repair: an AI error in the repair call is not fatal
        def fail(messages, max_tokens=None):
            raise llm.LLMError("down")

        cards.llm.chat_json = fail
        assert cards._repair("x", True, {"limitation": "draft"}) == {}
    finally:
        cards.build_context, cards.llm.chat_json = real_build, real_chat

    # 4. bad JSON and cut answers: the server asks again
    answers = iter([
        {"choices": [{"message": {"content": "no json here"}, "finish_reason": "stop"}]},
        {"choices": [{"message": {"content": '{"a": 1'}, "finish_reason": "length"}]},
        {"choices": [{"message": {"content": '```json\n{"a": 1}\n```'}, "finish_reason": "stop"}]},
    ])
    sent = []

    class R:
        status_code = 200
        headers = {}

        def __init__(self, data): self.data = data
        def json(self): return self.data

    def fake_post(url, json=None, headers=None, timeout=None):
        sent.append(dict(json))
        return R(next(answers))

    real_post, real_key = llm.httpx.post, config.LLM_API_KEY
    llm.httpx.post, config.LLM_API_KEY = fake_post, "k"
    try:
        assert REAL_CHAT_JSON([{"role": "user", "content": "x"}]) == {"a": 1}
    finally:
        llm.httpx.post, config.LLM_API_KEY = real_post, real_key
    assert len(sent) == 3 and sent[2]["max_tokens"] > sent[0]["max_tokens"]
    print("RELIABILITY TESTS PASSED")


def test_providers():
    """Gemini first. On an error, Groq answers. The next request tries Gemini again. Same request = saved answer."""
    from app import config, db as db_mod
    down = {"gemini": False, "groq": False}
    calls = []

    class R:
        headers = {"retry-after": "0"}

        def __init__(self, code, data): self.status_code, self.data = code, data
        def json(self): return self.data

    def fake_post(url, json=None, headers=None, timeout=None):
        who = "gemini" if "generativelanguage" in url else "groq"
        calls.append(who)
        if down[who]:
            return R(429, {"error": {"message": "quota"}})
        return R(200, {"choices": [{"message": {"content": '{"who": "%s"}' % who}, "finish_reason": "stop"}]})

    real_post, real_key = llm.httpx.post, config.LLM_API_KEY
    llm.httpx.post, config.LLM_API_KEY = fake_post, "g"
    llm._down_until.clear()
    msg = lambda t: [{"role": "user", "content": t}]
    try:
        assert [p["name"] for p in llm._chain()] == ["gemini", "groq"]
        # Gemini works: it answers, the card label says so
        assert REAL_CHAT_JSON(msg("one")) == {"who": "gemini"} and llm.used_model().startswith("gemini:")
        # Gemini fails: Groq answers in the same request, with no long wait
        down["gemini"] = True
        calls.clear()
        assert REAL_CHAT_JSON(msg("two")) == {"who": "groq"} and calls == ["gemini", "groq"] and llm.used_model().startswith("groq:")
        # Gemini rests for a short time, so the next request goes to Groq at once
        calls.clear()
        assert REAL_CHAT_JSON(msg("three")) == {"who": "groq"} and calls == ["groq"]
        assert [s["paused"] for s in llm.status()] == [True, False]
        # The rest ends and Gemini works again: the server returns to Gemini
        llm._down_until.clear()
        down["gemini"] = False
        calls.clear()
        assert REAL_CHAT_JSON(msg("four")) == {"who": "gemini"} and calls == ["gemini"]
        # Saved answers: the same request does not call the AI
        calls.clear()
        assert REAL_CHAT_JSON(msg("four")) == {"who": "gemini"} and calls == []
        with llm.cache_scope("paperX", fresh=True):
            assert REAL_CHAT_JSON(msg("four")) == {"who": "gemini"}
        assert calls == ["gemini"]
        # A saved answer of a paper goes when the paper goes
        with llm.cache_scope("paperX"):
            REAL_CHAT_JSON(msg("five"))
        calls.clear()
        db_mod.delete_paper("paperX")
        REAL_CHAT_JSON(msg("five"))
        assert calls == ["gemini"]
        # Both fail: the error names both providers
        down.update(gemini=True, groq=True)
        llm._down_until.clear()
        try:
            REAL_CHAT_JSON(msg("six"))
            raise AssertionError("must fail")
        except llm.LLMError as e:
            assert "Gemini" in str(e) and "Groq" in str(e), str(e)
    finally:
        llm.httpx.post, config.LLM_API_KEY = real_post, real_key
        llm._down_until.clear()
    print("PROVIDER TESTS PASSED")


def test_ste():
    """ASD-STE100 in all four agents: same rules in each prompt, a server check, and a safe rewrite."""
    from app import cards, chat, links, ste

    # the same rules are in the prompt of each agent (the mind map has no AI prompt: it is built from the cards)
    for p in (cards.system_prompt(True, False), cards.system_prompt(False, True), chat.SYSTEM, links.SYSTEM):
        assert "ASD-STE100" in p and "maximum 20 words" in p and "active voice" in p and "contractions" in p and "@STE@" not in p

    # the check finds what it can measure
    good = "The system has two agents. The first agent reads the logs. It proposes 3 hypotheses."
    assert ste.lint(good) == []
    long = "The proposed system reads the logs of the network and then it sends the logs to the second agent which checks each hypothesis against the rules of the analyst team."
    assert any("words" in p for p in ste.lint(long))
    assert any("filler" in p for p in ste.lint("The system is very fast."))
    assert any("contractions" in p for p in ste.lint("The system doesn't scale."))
    assert ste.lint("The paper's method is simple.") == []  # a possessive is not a contraction
    assert any("semicolon" in p for p in ste.lint("It is fast; it is cheap."))
    assert ste.lint("See Fig. 3 for the result. The authors (Smith et al. 2020) agree. Precision is 91.4% on the test set.") == []  # no false split

    # the rewrite is kept only when it is safe
    real = ste.llm.chat_json
    old = "The system reaches 91.4% precision on OpTC and it also reaches 84.2% recall which is very good and it beats the baseline of 72.0% by a large margin on the same logs."
    try:
        ste.llm.chat_json = lambda m, max_tokens=None: {"a": "The system reaches 91.4% precision on OpTC. It reaches 84.2% recall. The baseline reaches 72.0%.",
                                                        "b": "The system reaches 99.9% precision on OpTC. It reaches 84.2% recall. The baseline reaches 72.0%.",  # a number changed
                                                        "c": "The system reaches 91.4% precision. It reaches 84.2% recall. The baseline reaches 72.0%."}  # OpTC lost
        out = ste.enforce({"a": old, "b": old, "c": old, "ok": good})
        assert out.keys() == {"a"} and ste.lint(out["a"]) == [], out

        def down(m, max_tokens=None):
            raise llm.LLMError("down")

        ste.llm.chat_json = down
        assert ste.enforce({"a": old}) == {}  # an AI error keeps the original text
        calls = []
        ste.llm.chat_json = lambda m, max_tokens=None: calls.append(1) or {}
        assert ste.enforce({"ok": good}) == {} and not calls  # no problem: no AI call

        # a card: the answers, the verdict reason and the opinion are checked. The text of the student and the quotes are not.
        ste.llm.chat_json = lambda m, max_tokens=None: {"result": "The system reaches 91.4% precision on OpTC. It reaches 84.2% recall. The baseline reaches 72.0%.",
                                                        "verdict_reason": "The paper is a direct baseline."}
        fields = {"result": {"answer": old, "kind": "paper", "evidence": [{"quote": "keep me", "page": 1}]},
                  "question": {"answer": old, "kind": "user"}, "problem": {"answer": cards.NOT_STATED, "kind": "paper"}}
        reason, inferred = cards.apply_ste(fields, "The paper is really a direct baseline for the thesis of the student " * 2, "")
        assert fields["result"]["answer"].startswith("The system reaches 91.4% precision on OpTC.") and fields["result"]["evidence"][0]["quote"] == "keep me"
        assert fields["question"]["answer"] == old and fields["problem"]["answer"] == cards.NOT_STATED
        assert reason == "The paper is a direct baseline." and inferred == ""
    finally:
        ste.llm.chat_json = real
    print("STE TESTS PASSED")


if __name__ == "__main__":
    test_all()
    test_reliability()
    test_providers()
    test_ste()
