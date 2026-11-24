"""
rag/retrieve.py - Hybrid retrieval: semantic + keyword, fused by rank.
Agreed 2026-11-15: optional matter filter for legal document sets.
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


def _semantic_search(query, n, matter=None):
    collection = store.get_collection()
    q_vec = store.embed([query])[0]
    kwargs = {
        "query_embeddings": [q_vec],
        "n_results": n,
        "include": ["documents", "metadatas", "distances"],
    }
    if matter:
        if isinstance(matter, dict):
            kwargs["where"] = matter
        else:
            kwargs["where"] = {"tag": matter}
    res = collection.query(**kwargs)
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    return [
        {"doc": d, "meta": m, "distance": dist}
        for d, m, dist in zip(docs, metas, dists)
    ]


def _keyword_search(query, n, matter=None):
    collection = store.get_collection()
    kwargs = {"include": ["documents", "metadatas"]}
    if matter:
        if isinstance(matter, dict):
            kwargs["where"] = matter
        else:
            kwargs["where"] = {"tag": matter}
    data = collection.get(**kwargs)
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
    fused = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            key = item["doc"]
            if key not in fused:
                fused[key] = {"doc": item["doc"], "meta": item["meta"], "score": 0.0}
            fused[key]["score"] += 1.0 / (k + rank + 1)
    return sorted(fused.values(), key=lambda x: x["score"], reverse=True)


def retrieve(query, top_k=None, matter=None):
    if top_k is None:
        top_k = config.RETRIEVAL_TOP_K
    semantic = _semantic_search(query, config.SEMANTIC_CANDIDATES, matter=matter)
    keyword = _keyword_search(query, config.KEYWORD_CANDIDATES, matter=matter)
    fused = _rrf_fuse([semantic, keyword])
    return fused[:top_k]


def format_context(results):
    parts = []
    for i, r in enumerate(results, 1):
        src = (r.get("meta") or {}).get("source", "unknown")
        tag = (r.get("meta") or {}).get("tag")
        label = src if not tag else src + " [" + tag + "]"
        parts.append("Source: " + label + "\n" + r["doc"])
    return "\n\n".join(parts)
