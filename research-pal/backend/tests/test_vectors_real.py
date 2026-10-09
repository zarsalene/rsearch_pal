"""The real ChromaDB. The other tests use a fake index (see tests/fake_vectors.py)."""


def chunk(i, text, page):
    return {"id": f"c{i}", "text": text, "page": page, "idx": i}


def test_index_search_and_delete(real_vectors):
    v = real_vectors
    v.index_chunks("p1", [chunk(0, "multi agent threat hunting with sysmon logs", 1), chunk(1, "precision and recall on the optc dataset", 2)])
    v.index_chunks("p2", [chunk(0, "cooking pasta with tomato sauce and basil", 1)])
    hits = v.search("threat hunting sysmon", 3)
    assert hits[0]["paper_id"] == "p1" and hits[0]["page"] == 1
    assert [h["text"] for h in v.query_paper("p2", "pasta", 4)] == ["cooking pasta with tomato sauce and basil"]
    v.index_card("p1", "AUTOMA threat hunting")
    assert set(v.card_embeddings()) == {"p1"}
    v.delete_paper("p1")
    assert all(h["paper_id"] == "p2" for h in v.search("threat hunting sysmon", 3)) and v.card_embeddings() == {}


def test_a_search_that_fails_by_chance_is_tried_again(monkeypatch):
    """ChromaDB can fail by chance for an index that it just made. The search tries again, then makes the index again from the saved text."""
    import chromadb
    from app import db, vectors
    from fake_vectors import FakeIndex

    index = FakeIndex()
    monkeypatch.setattr(vectors, "_col", index.col)
    monkeypatch.setattr(vectors.time, "sleep", lambda s: None)
    vectors.index_chunks("p1", [{"id": "c0", "text": "multi agent threat hunting with sysmon logs", "page": 1, "idx": 0}])
    real_query, fails = index.col("chunks").query, {"n": 0}

    def flaky(**kw):
        fails["n"] += 1
        if fails["n"] <= 2:
            raise chromadb.errors.InternalError("Error creating hnsw segment reader: Nothing found on disk")
        return real_query(**kw)

    monkeypatch.setattr(index.col("chunks"), "query", flaky)
    assert vectors.query_paper("p1", "threat hunting", 2)[0]["page"] == 1 and fails["n"] == 3  # two failures, then it works

    # it never works: the server makes the index again from the saved text, then it tries more
    db.init()
    db.save_pages("p2", ["A long page of text. " * 20])
    calls = {"n": 0}

    def broken_until_reindex(**kw):
        calls["n"] += 1
        if not index.col("chunks").rows or not any(r["metadata"].get("paper_id") == "p2" for r in index.col("chunks").rows.values()):
            raise chromadb.errors.InternalError("Error finding id")
        return real_query(**kw)

    monkeypatch.setattr(index.col("chunks"), "query", broken_until_reindex)
    got = vectors.query_paper("p2", "long page", 2)
    assert got and calls["n"] >= 4  # it failed 3 times, then the index was made again

    def always(**kw):
        raise chromadb.errors.InternalError("Nothing found on disk")

    monkeypatch.setattr(index.col("chunks"), "query", always)
    try:
        vectors.query_paper("p1", "x", 1)
        raise AssertionError("must raise")
    except chromadb.errors.InternalError:
        pass
