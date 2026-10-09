"""A small in-memory stand-in for a ChromaDB collection. Only the calls of app/vectors.py are supported.
Why: ChromaDB breaks by chance when a process makes and deletes many collections (the error says "Nothing found on disk"
or "Error finding id"). The app makes two collections one time, so it is safe. A test run makes a new index for each test, so it is not.
The code of vectors.py still runs in the tests. Only the collection object is fake. tests/test_vectors_real.py uses the real ChromaDB."""
import math


class FakeCollection:
    def __init__(self):
        self.rows = {}  # id -> {"document", "embedding", "metadata"}

    def count(self):
        return len(self.rows)

    def _put(self, ids, documents=None, embeddings=None, metadatas=None):
        for i, id_ in enumerate(ids):
            self.rows[id_] = {"document": (documents or [""] * len(ids))[i], "embedding": list(embeddings[i]), "metadata": dict((metadatas or [{}] * len(ids))[i])}

    add = upsert = _put

    def _match(self, row, where):
        return all(row["metadata"].get(k) == v for k, v in (where or {}).items())

    def delete(self, ids=None, where=None):
        for id_ in list(self.rows):
            if (ids is not None and id_ in ids) or (where is not None and self._match(self.rows[id_], where)):
                del self.rows[id_]

    def query(self, query_embeddings, n_results=10, where=None):
        q = query_embeddings[0]
        scored = []
        for id_, row in self.rows.items():
            if not self._match(row, where):
                continue
            dot = sum(a * b for a, b in zip(q, row["embedding"]))
            norm = math.sqrt(sum(a * a for a in q)) * math.sqrt(sum(b * b for b in row["embedding"])) or 1.0
            scored.append((1 - dot / norm, id_, row))
        scored.sort(key=lambda s: s[0])
        top = scored[:n_results]
        return {"ids": [[i for _, i, _ in top]], "documents": [[r["document"] for _, _, r in top]],
                "metadatas": [[r["metadata"] for _, _, r in top]], "distances": [[d for d, _, _ in top]]}

    def get(self, ids=None, include=None):
        keep = [i for i in self.rows if ids is None or i in ids]
        out = {"ids": keep}
        if include and "embeddings" in include:
            out["embeddings"] = [self.rows[i]["embedding"] for i in keep]
        return out


class FakeIndex:
    """One fake collection for each name. A new FakeIndex is empty, so each test starts clean."""

    def __init__(self):
        self.collections = {}

    def col(self, name):
        return self.collections.setdefault(name, FakeCollection())
