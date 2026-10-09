"""ASD-STE100 in all four agents: same rules in each prompt, a server check, and a safe rewrite."""
from app import cards, chat, links, llm, ste

GOOD = "The system has two agents. The first agent reads the logs. It proposes 3 hypotheses."
OLD = "The system reaches 91.4% precision on OpTC and it also reaches 84.2% recall which is very good and it beats the baseline of 72.0% by a large margin on the same logs."
SAFE = "The system reaches 91.4% precision on OpTC. It reaches 84.2% recall. The baseline reaches 72.0%."


def test_rules_reach_each_prompt():
    # the mind map has no AI prompt: it is built from the cards
    for p in (cards.system_prompt(True, False), cards.system_prompt(False, True), chat.SYSTEM, links.SYSTEM):
        assert "ASD-STE100" in p and "maximum 20 words" in p and "active voice" in p and "contractions" in p and "@STE@" not in p


def test_lint_finds_what_it_can_measure():
    assert ste.lint(GOOD) == []
    long = "The proposed system reads the logs of the network and then it sends the logs to the second agent which checks each hypothesis against the rules of the analyst team."
    assert any("words" in p for p in ste.lint(long))
    assert any("filler" in p for p in ste.lint("The system is very fast."))
    assert any("contractions" in p for p in ste.lint("The system doesn't scale."))
    assert ste.lint("The paper's method is simple.") == []  # a possessive is not a contraction
    assert any("semicolon" in p for p in ste.lint("It is fast; it is cheap."))
    assert ste.lint("See Fig. 3 for the result. The authors (Smith et al. 2020) agree. Precision is 91.4% on the test set.") == []  # no false split


def test_rewrite_is_kept_only_when_safe(fake_ai):
    fake_ai.when("technical editor", {
        "a": SAFE,
        "b": SAFE.replace("91.4", "99.9"),  # a number changed
        "c": "The system reaches 91.4% precision. It reaches 84.2% recall. The baseline reaches 72.0%.",  # OpTC lost
    })
    out = ste.enforce({"a": OLD, "b": OLD, "c": OLD, "ok": GOOD})
    assert out.keys() == {"a"} and ste.lint(out["a"]) == [], out


def test_ai_error_keeps_the_original_text(fake_ai):
    fake_ai.when("technical editor", llm.LLMError("down"))
    assert ste.enforce({"a": OLD}) == {}


def test_no_problem_means_no_ai_call(fake_ai):
    assert ste.enforce({"ok": GOOD}) == {} and not fake_ai.calls


def test_card_texts_are_checked_but_not_the_text_of_the_student(fake_ai):
    # the answers, the verdict reason and the opinion are checked. The text of the student and the quotes are not.
    fake_ai.when("technical editor", {"result": SAFE, "verdict_reason": "The paper is a direct baseline."})
    fields = {"result": {"answer": OLD, "kind": "paper", "evidence": [{"quote": "keep me", "page": 1}]},
              "question": {"answer": OLD, "kind": "user"}, "problem": {"answer": cards.NOT_STATED, "kind": "paper"}}
    reason, inferred = cards.apply_ste(fields, "The paper is really a direct baseline for the thesis of the student " * 2, "")
    assert fields["result"]["answer"].startswith("The system reaches 91.4% precision on OpTC.") and fields["result"]["evidence"][0]["quote"] == "keep me"
    assert fields["question"]["answer"] == OLD and fields["problem"]["answer"] == cards.NOT_STATED
    assert reason == "The paper is a direct baseline." and inferred == ""
