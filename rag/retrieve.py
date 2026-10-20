"""
rag/retrieve.py — Hybrid retrieval: semantic + keyword, fused by rank.

Returns a list of results, each with document text, metadata, and scores.
No arithmetic mixing of incomparable scales; rank fusion only.
"""

import re
import config
from rag import store

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is",
    "are", "was", "were", "be", "been", "being", "with", "by", "at", "as",
    "it", "its", "this", "that", "these", "those", "from", "into", "but",
    "not", "no", "do", "does", "did", "how", "what", "when", "where",
    "who", "why", "which", "i", "we", "you", "they", "he", "she",
}


def _tokenize(text):
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w for w in words if w not in _STOPWORDS and len(w) > 1]


def _semantic_search(query, n):
    collection = store.get_collection()
    q_vec = store.embed([query])[0]
    res = collection.query(
        query_embeddings=[q_vec],
        n_results=n,
        include=["documents", "metadatas", "distances"],
    )
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    return [
        {"doc": d, "meta": m, "distance": dist}
        for d, m, dist in zip(docs, metas, dists)
    ]


def _keyword_search(query, n):
    collection = store.get_collection()
    data = collection.get(include=["documents", "metadatas"])
    docs = data.get("documents", [])
    metas = data.get("metadatas", [])
    q_terms = _tokenize(query)
    if not q_terms:
        return []
    scored = []
    for doc, meta in zip(docs, metas):
        doc_terms = set(_tokenize(doc))
        overlap = len(set(q_terms) & doc_terms)
        if overlap > 0:
            scored.append({"doc": doc, "meta": meta, "hits": overlap})
    scored.sort(key=lambda x: x["hits"], reverse=True)
    return scored[:n]


def _rrf_fuse(rankings, k=60):
    """Reciprocal rank fusion. rankings is a list of ordered result lists."""
    fused = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            key = item["doc"]
            if key not in fused:
                fused[key] = {"doc": item["doc"], "meta": item["meta"], "score": 0.0}
            fused[key]["score"] += 1.0 / (k + rank + 1)
    return sorted(fused.values(), key=lambda x: x["score"], reverse=True)


def retrieve(query, top_k=None):
    if top_k is None:
        top_k = config.RETRIEVAL_TOP_K
    semantic = _semantic_search(query, config.SEMANTIC_CANDIDATES)
    keyword = _keyword_search(query, config.KEYWORD_CANDIDATES)
    fused = _rrf_fuse([semantic, keyword])
    return fused[:top_k]


def format_context(results):
    """Render retrieved chunks as a labeled context block for the LLM."""
    parts = []
    for i, r in enumerate(results, 1):
        src = (r.get("meta") or {}).get("source", "unknown")
        parts.append(f"Source: {src}\n{r['doc']}")
    return "\n\n".join(parts)


# ---------- quick test ----------
if __name__ == "__main__":
    questions = [
        "What is the mean time between failures on the passivation line?",
        "How many recordable incidents occurred last year?",
        "What was the largest kaizen saving and where did it come from?",
        "What percentage of revenue comes from the largest customer?",
        "How many weeks of bar stock are held as buffer?",
        "What is the first-pass yield target?",
        "When does the safety committee meet?",
        "What is the capital of France?",
    ]
    for q in questions:
        print(f"\nQ: {q}")
        results = retrieve(q, top_k=2)
        if not results:
            print("  (no results)")
            continue
        for i, r in enumerate(results, 1):
            src = (r.get("meta") or {}).get("source", "?")
            snippet = r["doc"][:180].replace("\n", " ")
            print(f"  [{i}] {src} | score {r['score']:.4f}")
            print(f"      {snippet}...")
