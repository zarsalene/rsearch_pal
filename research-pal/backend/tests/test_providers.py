"""Gemini first. On an error, Groq answers. The next request tries Gemini again. Same request = saved answer."""
from app import config, db as db_mod, llm


def test_provider_chain(monkeypatch, real_chat_json):
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

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    monkeypatch.setattr(config, "LLM_API_KEY", "g")
    db_mod.init()
    ask = lambda t: real_chat_json([{"role": "user", "content": t}])

    assert [p["name"] for p in llm._chain()] == ["gemini", "groq"]
    # Gemini works: it answers, the card label says so
    assert ask("one") == {"who": "gemini"} and llm.used_model().startswith("gemini:")
    # Gemini fails: Groq answers in the same request, with no long wait
    down["gemini"] = True
    calls.clear()
    assert ask("two") == {"who": "groq"} and calls == ["gemini", "groq"] and llm.used_model().startswith("groq:")
    # Gemini rests for a short time, so the next request goes to Groq at once
    calls.clear()
    assert ask("three") == {"who": "groq"} and calls == ["groq"]
    assert [s["paused"] for s in llm.status()] == [True, False]
    # The rest ends and Gemini works again: the server returns to Gemini
    llm._down_until.clear()
    down["gemini"] = False
    calls.clear()
    assert ask("four") == {"who": "gemini"} and calls == ["gemini"]
    # Saved answers: the same request does not call the AI
    calls.clear()
    assert ask("four") == {"who": "gemini"} and calls == []
    with llm.cache_scope("paperX", fresh=True):
        assert ask("four") == {"who": "gemini"}
    assert calls == ["gemini"]
    # A saved answer of a paper goes when the paper goes
    with llm.cache_scope("paperX"):
        ask("five")
    calls.clear()
    db_mod.delete_paper("paperX")
    ask("five")
    assert calls == ["gemini"]
    # Both fail: the error names both providers
    down.update(gemini=True, groq=True)
    llm._down_until.clear()
    try:
        ask("six")
        raise AssertionError("must fail")
    except llm.LLMError as e:
        assert "Gemini" in str(e) and "Groq" in str(e), str(e)
