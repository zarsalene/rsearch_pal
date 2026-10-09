"""A fake AI. It replaces llm.chat_json in the tests, so no test calls a real AI.
Without a rule, the fake AI gives the scripted answers of the test PDFs in pdfs.py.
Some answers are false on purpose (an invented quote, a number that is not in the PDF). The truth tests use them."""


def default_answers(messages, max_tokens=None):
    user = messages[-1]["content"]
    system = messages[0]["content"]
    if "You are a careful research mentor" in system:  # the question helper (Sprint 03)
        if "You suggest 3 to 5 sub-questions" in system:
            return {"sub_questions": ["What data exists for this topic?", "Which method works best?", "How do we measure the result?", "What are the limits of the method?"]}
        vague = "AI in health" in user  # a vague question gets weak ratings and a "too wide" scope. A clear question passes.
        rate = lambda key: {"rating": "weak" if vague and key == "feasible" else "ok", "why": f"The {key} point is {'weak' if vague and key == 'feasible' else 'clear'}."}
        return {"finer": {k: rate(k) for k in ("feasible", "interesting", "novel", "ethical", "relevant")},
                "scope": {"status": "too_wide" if vague else "ok", "why": "The question covers a whole field." if vague else "The scope is good."},
                "versions": ["Can deep learning find lung cancer in X-ray images?", "Does AI cut the time of a diagnosis in a hospital?", "How do nurses use AI tools in a clinic?"]}
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
        base = default_answers([messages[0], {"role": "user", "content": user.replace("<focus>", "")}], max_tokens)
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


class FakeAI:
    """Use it through the fixture fake_ai.
    fake_ai.when("text", answer)  A call whose system or user text contains "text" gets this answer.
                                  answer is a dict, a function(messages) that returns a dict, or an exception (it is raised).
                                  The last rule that matches wins. "text" can also be a function(system, user) that returns True or False.
    fake_ai.calls                 Each call: {"system", "user", "messages", "max_tokens"}. Use it to check that the AI was or was not called."""

    def __init__(self):
        self.calls = []
        self.rules = []

    def when(self, match, answer):
        self.rules.append((match, answer))
        return self

    def reset(self):
        self.calls.clear()
        self.rules.clear()

    def __call__(self, messages, max_tokens=None):
        system, user = messages[0]["content"], messages[-1]["content"]
        self.calls.append({"system": system, "user": user, "messages": messages, "max_tokens": max_tokens})
        for match, answer in reversed(self.rules):
            hit = match(system, user) if callable(match) else (match in system or match in user)
            if hit:
                if isinstance(answer, BaseException):
                    raise answer
                return answer(messages) if callable(answer) else answer
        return default_answers(messages, max_tokens)
