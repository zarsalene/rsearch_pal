"""Helpers that the tests share."""
import time

from app import cards


def login(client, password="test-password-123") -> dict:
    from app import config
    if config.MULTI_USER:  # Postgres test run: conftest.py makes every token belong to the user of the test
        return {"Authorization": "Bearer test"}
    token = client.post("/api/login", json={"password": password}).json()["token"]
    return {"Authorization": "Bearer " + token}


def upload(client, h, path, **form) -> str:
    r = client.post("/api/papers", headers=h, files={"file": (path.name, path.read_bytes(), "application/pdf")}, data=form)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def wait_ready(client, h, pid) -> dict:
    for _ in range(100):
        p = client.get(f"/api/papers/{pid}", headers=h).json()
        if p["paper"]["status"] in ("ready", "error"):
            return p
        time.sleep(0.1)
    raise AssertionError("timeout")


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _found(quote, pages) -> bool:
    q = cards.norm(quote)
    return bool(q) and any(q in cards.norm(p) for p in pages)


def assert_no_false_quote(response, pages=None, invented=()):
    """The truth test. Look at each part of an answer of the server (a card, a chat answer, a link, a mind map).
    - A quote that the server marks as verified must be in the PDF. Give pages (a list of page texts, or {paper_id: list}) to check this.
    - A claim with the status "verified" or "check" must have at least one verified quote.
    - A claim with the status "unverified" must show no answer. The draft is kept apart, so the student can see it in red.
    - invented: quotes that are not in the PDF. They must never show as verified.
    """
    for n in _walk(response):
        if "quote" in n and "verified" in n:
            assert n["verified"] is False or n["verified"] is True, n
            if n["verified"]:
                assert cards.norm(n["quote"]) not in {cards.norm(i) for i in invented}, f"An invented quote shows as verified: {n}"
                if pages is not None:
                    book = pages.get(n.get("paper_id"), []) if isinstance(pages, dict) else pages
                    assert _found(n["quote"], book), f"A verified quote is not in the PDF: {n}"
        evidence = n.get("evidence")
        if n.get("status") in ("verified", "check") and isinstance(evidence, list):
            assert any(e.get("verified", True) for e in evidence), f"A claim is {n['status']} with no verified quote: {n}"
        if n.get("status") == "unverified" and "draft" in n:
            assert n.get("answer") == "", f"A claim without a verified quote shows its answer: {n}"
