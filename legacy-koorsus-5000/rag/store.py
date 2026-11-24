"""
rag/store.py — ChromaDB storage layer.

Owns the client, the embedding model, and the operations that write
chunks into the collection. Embeddings are computed explicitly, on CPU,
using the same model the query side will use.
"""

import datetime
import chromadb
from sentence_transformers import SentenceTransformer

import config

_embedder = None
_client = None


def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(
            config.EMBED_MODEL_NAME, device=config.EMBED_DEVICE
        )
    return _embedder


def get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=config.DB_PATH)
    return _client


def get_collection():
    """Return the collection, creating it with cosine distance if absent."""
    client = get_client()
    try:
        return client.get_collection(config.COLLECTION_NAME)
    except Exception:
        return client.create_collection(
            name=config.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )


def reset_collection():
    """Delete the collection entirely and recreate it. Use with intent."""
    client = get_client()
    try:
        client.delete_collection(config.COLLECTION_NAME)
    except Exception:
        pass
    return get_collection()


def embed(texts):
    """Return a list of normalized embedding vectors."""
    vectors = get_embedder().encode(
        texts,
        batch_size=16,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return vectors.tolist()


def add_chunks(chunks, source, extra_metadata=None):
    """Add a list of chunk strings to the collection under one source label."""
    if not chunks:
        return 0
    collection = get_collection()
    now = datetime.datetime.now().isoformat()
    embeddings = embed(chunks)
    ids = [f"{source}::{i:04d}" for i in range(len(chunks))]
    metadatas = []
    for i in range(len(chunks)):
        meta = {
            "source": source,
            "chunk_id": i,
            "ingested_at": now,
        }
        if extra_metadata:
            meta.update(extra_metadata)
        metadatas.append(meta)
    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    return len(chunks)


def stats():
    """Return total chunk count and a per-source breakdown."""
    collection = get_collection()
    data = collection.get(include=["metadatas"])
    ids = data.get("ids", [])
    sources = {}
    for meta in data.get("metadatas", []):
        src = (meta or {}).get("source", "unknown")
        sources[src] = sources.get(src, 0) + 1
    return {"total_chunks": len(ids), "sources": sources}
