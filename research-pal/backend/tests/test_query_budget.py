"""Each database block (db.conn) costs trips to Supabase on a real server. This test sets a ceiling for the number of blocks that one request uses,
so a new feature cannot make a page slow by accident. If a page needs more blocks, first try to read the data in one query. Raise the ceiling only if you cannot."""
from contextlib import contextmanager

import pytest

from app import db
from helpers import upload, wait_ready

# path -> the most blocks that one request may use (the real number today, plus a little room)
BUDGET = {
    "/api/papers": 3,
    "/api/config": 3,
    "/api/features": 1,
    "/api/project": 2,
    "/api/sub-questions": 2,
    "/api/today": 14,
    "/api/game": 26,
    "/api/glossary": 2,
    "/api/play": 9,
    "/api/journey/map": 11,
    "/api/to-read": 13,
    "/api/plan": 4,
    "/api/quests": 16,
    "/api/review/due": 11,
    "/api/goals": 2,
    "/api/wins": 2,
    "/api/graph": 2,
    "/api/search?q=agent": 2,
}


@pytest.fixture
def block_counter(monkeypatch):
    count = {"n": 0}
    real = db.conn

    @contextmanager
    def counting():
        count["n"] += 1
        with real() as c:
            yield c

    monkeypatch.setattr(db, "conn", counting)
    return count


@pytest.mark.parametrize("path", sorted(BUDGET))
def test_a_request_stays_inside_its_budget(client, auth_headers, fake_ai, sample_pdfs, block_counter, path):
    pid = upload(client, auth_headers, sample_pdfs["a.pdf"].path)
    wait_ready(client, auth_headers, pid)
    block_counter["n"] = 0
    r = client.get(path, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert block_counter["n"] <= BUDGET[path], f"{path} used {block_counter['n']} database blocks. The ceiling is {BUDGET[path]}."


def test_one_paper_stays_inside_its_budget(client, auth_headers, fake_ai, sample_pdfs, block_counter):
    pid = upload(client, auth_headers, sample_pdfs["a.pdf"].path)
    wait_ready(client, auth_headers, pid)
    block_counter["n"] = 0
    assert client.get(f"/api/papers/{pid}", headers=auth_headers).status_code == 200
    assert block_counter["n"] <= 4, f"the card used {block_counter['n']} database blocks"
