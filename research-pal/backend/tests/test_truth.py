"""Truth tests: the rule "no wrong data". The fake AI gives a quote that is not in the PDF, or a number that the PDF does not have.
The server must hide the claim, drop it, or label it. Each AI feature must have a test like this."""
import copy

from app import db as db_mod
from fake_ai import default_answers
from helpers import assert_no_false_quote, upload, wait_ready
from pdfs import INVENTED_QUOTE


def read_paper(client, h, sample_pdfs, name="a.pdf", **form):
    pid = upload(client, h, sample_pdfs[name].path, **form)
    return pid, wait_ready(client, h, pid)


def test_card_hides_a_claim_with_an_invented_quote(client, auth_headers, fake_ai, sample_pdfs):
    pid, got = read_paper(client, auth_headers, sample_pdfs)
    fields = got["card"]["fields"]
    # the invented quote: the claim is hidden. The draft stays apart, so the student can see it in red.
    assert fields["limitation"]["status"] == "unverified" and fields["limitation"]["answer"] == ""
    assert "encrypted" in fields["limitation"]["draft"] and not any(e["verified"] for e in fields["limitation"]["evidence"])
    # the true claims stay
    assert fields["problem"]["status"] == "verified" and fields["method"]["status"] == "verified"
    assert_no_false_quote(got["card"], pages=db_mod.get_pages(pid), invented=[INVENTED_QUOTE])


def test_card_flags_a_number_that_is_not_in_the_pdf(client, auth_headers, fake_ai, sample_pdfs):
    pid, got = read_paper(client, auth_headers, sample_pdfs)
    result = got["card"]["fields"]["result"]
    assert result["status"] == "check" and result["unverified_numbers"] == ["95.0"]  # 91.4 is in the PDF, 95.0 is not


def test_card_with_only_invented_quotes_shows_no_claim(client, auth_headers, fake_ai, sample_pdfs):
    def all_invented(messages):
        raw = copy.deepcopy(default_answers(messages))
        for name in ("problem", "method", "result", "limitation"):
            raw[name]["evidence"] = [{"quote": INVENTED_QUOTE, "page": 1}]
        return raw

    fake_ai.when("<paper>", all_invented)
    pid, got = read_paper(client, auth_headers, sample_pdfs)
    for name in ("problem", "method", "result", "limitation"):
        assert got["card"]["fields"][name]["status"] == "unverified" and got["card"]["fields"][name]["answer"] == "", name
    assert_no_false_quote(got["card"], pages=db_mod.get_pages(pid), invented=[INVENTED_QUOTE])


def test_chat_marks_an_invented_quote(client, auth_headers, fake_ai, sample_pdfs):
    pid, _ = read_paper(client, auth_headers, sample_pdfs)
    r = client.post("/api/chat", headers=auth_headers, json={"question": "INVENT something", "paper_ids": [pid]})
    assert r.status_code == 200, r.text
    answer = r.json()
    assert answer["status"] == "unverified" and [e["verified"] for e in answer["evidence"]] == [False]
    assert_no_false_quote(answer, pages={pid: db_mod.get_pages(pid)}, invented=[INVENTED_QUOTE])


def test_chat_flags_a_number_that_is_not_in_the_pdf(client, auth_headers, fake_ai, sample_pdfs):
    pid, _ = read_paper(client, auth_headers, sample_pdfs)
    answer = client.post("/api/chat", headers=auth_headers, json={"question": "What precision does AUTOMA reach?", "paper_ids": [pid]}).json()
    assert answer["status"] == "check" and answer["unverified_numbers"] == ["99.9"]  # 91.4 is in the PDF, 99.9 is not
    assert_no_false_quote(answer, pages={pid: db_mod.get_pages(pid)}, invented=[INVENTED_QUOTE])


def test_link_explanation_with_only_invented_quotes_is_not_verified(client, auth_headers, fake_ai, sample_pdfs):
    ids = [read_paper(client, auth_headers, sample_pdfs, n)[0] for n in ("a.pdf", "b.pdf")]
    fake_ai.when("You explain how two papers", {
        "relation": "same_method", "summary": "Both papers talk about methods.", "shared": ["methods"], "differences": "One is about threats.",
        "evidence": [{"paper": 1, "quote": INVENTED_QUOTE, "page": 3}, {"paper": 2, "quote": "The pasta must cook for two hours in cold milk.", "page": 2}]})
    r = client.post("/api/links/explain", headers=auth_headers, json={"a": ids[0], "b": ids[1]})
    assert r.status_code == 200, r.text
    link = r.json()
    assert link["status"] == "unverified" and not any(e["verified"] for e in link["evidence"])
    assert_no_false_quote(link, pages={pid: db_mod.get_pages(pid) for pid in ids}, invented=[INVENTED_QUOTE])


def test_the_client_cannot_write_a_verified_quote(client, auth_headers, fake_ai, sample_pdfs):
    pid, _ = read_paper(client, auth_headers, sample_pdfs)
    lie = {"paper_id": pid, "quote": INVENTED_QUOTE, "page": 3, "verified": True}  # the client says "verified". The server must not believe it.
    truth = {"paper_id": pid, "quote": "AUTOMA reaches a precision of 91.4 percent and a recall of 84.2 percent.", "page": 3, "verified": False}
    r = client.post(f"/api/papers/{pid}/notes", headers=auth_headers, json={"question": "q", "answer": "A note.", "evidence": [lie, truth]})
    assert r.status_code == 200, r.text
    evidence = r.json()["notes"][0]["evidence"]
    assert [e["quote"] for e in evidence] == [truth["quote"]] and evidence[0]["verified"] is True
    assert_no_false_quote(r.json()["notes"], pages={pid: db_mod.get_pages(pid)}, invented=[INVENTED_QUOTE])
