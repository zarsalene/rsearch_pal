"""Size fallback, partial-text wording, quote repair and JSON retry."""
from app import cards, chat, config, llm


def test_partial_text_wording():
    # the field says "Not found in the excerpts", and the prompt tells the AI that the text is partial
    f = cards.verify_field({"answer": "Not stated in the paper.", "evidence": []}, [], "", False, complete=False)
    assert f["status"] == "not_found" and f["answer"] == cards.NOT_FOUND
    assert cards.verify_field({"answer": "Not found in the excerpts."}, [], "", False)["status"] == "not_stated"
    assert "only a PART" in cards.system_prompt(False, False) and "FULL text" in cards.system_prompt(True, False)
    assert "@" not in cards.system_prompt(True, True) and "FOCUS MODE" in cards.system_prompt(True, True)

    # ASD-STE100 rules reach the card prompt (also in focus mode) and the chat prompt
    for p in (cards.system_prompt(True, False), cards.system_prompt(False, True), chat.SYSTEM):
        assert "ASD-STE100" in p and "maximum 20 words" in p and "active voice" in p and "@STE@" not in p


def test_size_fallback_and_repair(monkeypatch):
    # the provider refuses the size: the server sends a smaller part, then stops at the minimum
    limits, calls = [], []
    monkeypatch.setattr(cards, "build_context", lambda pid, pages, chunks, q, focus="", limit=None: (limits.append(limit) or ("[page 1]\ntext", False)))

    def too_large_twice(messages, max_tokens=None):
        calls.append(1)
        if len(calls) < 3:
            raise llm.LLMTooLarge("big")
        return {"ok": 1}

    monkeypatch.setattr(llm, "chat_json", too_large_twice)
    raw, _, complete = cards._ask("p", [], [], "", "", "")
    assert raw == {"ok": 1} and complete is False
    assert limits == [config.LLM_CONTEXT_CHARS, config.LLM_CONTEXT_CHARS // 2, config.LLM_CONTEXT_CHARS // 4], limits

    def always_large(messages, max_tokens=None):
        raise llm.LLMTooLarge("big")

    monkeypatch.setattr(llm, "chat_json", always_large)
    try:
        cards._ask("p", [], [], "", "", "")
        raise AssertionError("must stop")
    except llm.LLMError as e:
        assert not isinstance(e, llm.LLMTooLarge)
    assert limits[-1] == config.LLM_MIN_CONTEXT_CHARS

    # repair: an AI error in the repair call is not fatal
    def fail(messages, max_tokens=None):
        raise llm.LLMError("down")

    monkeypatch.setattr(llm, "chat_json", fail)
    assert cards._repair("x", True, {"limitation": "draft"}) == {}


def test_bad_json_and_cut_answers(monkeypatch, real_chat_json):
    # the server asks again
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

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    monkeypatch.setattr(config, "LLM_API_KEY", "k")
    assert real_chat_json([{"role": "user", "content": "x"}]) == {"a": 1}
    assert len(sent) == 3 and sent[2]["max_tokens"] > sent[0]["max_tokens"]
