"""Local vector store (ChromaDB). Embeddings are made on the server. No data goes out."""
import hashlib, math, re, threading

import chromadb
from chromadb.config import Settings

from . import config

_lock = threading.Lock()
_client = None
_ef = None
_dim = 384


def _hash_embed(text: str) -> list[float]:
    """Simple word-hash vectors. For tests only."""
    v = [0.0] * _dim
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        h = int(hashlib.md5(w.encode()).hexdigest(), 16)
        v[h % _dim] += 1.0 if (h >> 20) & 1 else -1.0
        v[(h >> 8) % _dim] += 0.5
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def embed(texts: list[str]) -> list[list[float]]:
    global _ef
    if config.EMBEDDING_BACKEND == "hash":
        return [_hash_embed(t) for t in texts]
    with _lock:
        if _ef is None:
            from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
            _ef = DefaultEmbeddingFunction()
    return [[float(x) for x in v] for v in _ef(texts)]


def _col(name: str):
    global _client
    with _lock:
        if _client is None:
            config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
            _client = chromadb.PersistentClient(path=str(config.CHROMA_DIR), settings=Settings(anonymized_telemetry=False))
    return _client.get_or_create_collection(name, metadata={"hnsw:space": "cosine"}, embedding_function=None)


def index_chunks(paper_id: str, chunks: list[dict]) -> None:
    col = _col("chunks")
    col.delete(where={"paper_id": paper_id})
    for i in range(0, len(chunks), 48):
        part = chunks[i : i + 48]
        col.add(
            ids=[f"{paper_id}:{c['id']}" for c in part],
            documents=[c["text"] for c in part],
            embeddings=embed([c["text"] for c in part]),
            metadatas=[{"paper_id": paper_id, "page": c["page"], "idx": c["idx"]} for c in part],
        )


def query_paper(paper_id: str, query: str, n: int = 4) -> list[dict]:
    col = _col("chunks")
    r = col.query(query_embeddings=embed([query]), n_results=n, where={"paper_id": paper_id})
    return [{"page": m["page"], "idx": m["idx"], "text": d} for d, m in zip(r["documents"][0], r["metadatas"][0])]


def search(query: str, n: int = 8) -> list[dict]:
    col = _col("chunks")
    if col.count() == 0:
        return []
    r = col.query(query_embeddings=embed([query]), n_results=min(n, col.count()))
    out = []
    for d, m, dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0]):
        out.append({"paper_id": m["paper_id"], "page": m["page"], "text": d, "score": round(1 - float(dist), 3)})
    return out


def index_card(paper_id: str, text: str) -> None:
    col = _col("cards")
    col.upsert(ids=[paper_id], documents=[text], embeddings=embed([text]), metadatas=[{"paper_id": paper_id}])


def card_embeddings() -> dict[str, list[float]]:
    col = _col("cards")
    if col.count() == 0:
        return {}
    r = col.get(include=["embeddings"])
    return {i: [float(x) for x in e] for i, e in zip(r["ids"], r["embeddings"])}


def delete_paper(paper_id: str) -> None:
    _col("chunks").delete(where={"paper_id": paper_id})
    try:
        _col("cards").delete(ids=[paper_id])
    except Exception:
        pass
