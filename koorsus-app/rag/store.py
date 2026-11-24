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
from rag import doctype

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
    """Return the collection, creating it with cosine distance only if absent.

    Existence is checked explicitly rather than by catching exceptions, so a
    corrupt or locked database raises instead of being mistaken for an empty one.
    """
    client = get_client()
    names = [c.name if hasattr(c, "name") else c for c in client.list_collections()]
    if config.COLLECTION_NAME not in names:
        return client.create_collection(
            name=config.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return client.get_collection(config.COLLECTION_NAME)


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
            "doc_type": doctype.classify(source),
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


def matters():
    """Return [{tag, count}] sorted by tag, for the scope dropdown."""
    collection = get_collection()
    data = collection.get(include=["metadatas"])
    counts = {}
    for meta in data.get("metadatas", []):
        tag = (meta or {}).get("tag")
        if tag:
            counts[tag] = counts.get(tag, 0) + 1
    return [{"tag": t, "count": counts[t]} for t in sorted(counts)]


def reload():
    """Forces the client to reconnect to the database (used after restore/reset)."""
    global _client
    _client = None

def delete_source(source, tag=None):
    """Delete every chunk belonging to one document.

    Returns the number of chunks removed. Two keys in a Chroma where clause
    are invalid, so the tagged case is expressed as an explicit $and.
    """
    collection = get_collection()
    if tag:
        where = {"$and": [{"source": source}, {"tag": tag}]}
    else:
        where = {"source": source}
    found = collection.get(where=where, include=[])
    ids = found.get("ids", [])
    if ids:
        collection.delete(ids=ids)
    return len(ids)
