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
