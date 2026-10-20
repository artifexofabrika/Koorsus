import os, re, json
import chromadb
from chromadb.utils import embedding_functions

DB_PATH = "/mnt/lake/index"
COLLECTION_NAME = "memory_lake"

def _make_ef():
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

def _keyword_search(query, collection, n=5):
    """Simple keyword-based search across all documents in the collection."""
    try:
        results = collection.get()
        docs = results.get("documents", [])
        if not docs:
            return []
        query_lower = query.lower()
        scored = []
        for doc in docs:
            # Count occurrences of each query word
            count = sum(doc.lower().count(word) for word in query_lower.split() if len(word) > 1)
            if count > 0:
                scored.append((count, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:n]]
    except:
        return []

def query_lake(query, n=3, semantic_weight=0.5, threshold=0.4):
    """
    Two-stage retrieval: semantic + keyword fallback.
    Returns (list of doc strings, best score).
    """
    ef = _make_ef()
    client = chromadb.PersistentClient(path=DB_PATH)
    collection = client.get_collection(name=COLLECTION_NAME)

    # Semantic search
    results = collection.query(query_texts=[query], n_results=max(10, n))
    docs = results.get('documents', [[]])[0]
    distances = results.get('distances', [[1.0]])[0]

    scored = []
    for doc, dist in zip(docs, distances):
        kw = 0.0
        query_words = set(query.lower().split())
        doc_words = set(doc.lower().split())
        if query_words:
            kw = len(query_words & doc_words) / len(query_words)
        combined = semantic_weight * dist + (1.0 - semantic_weight) * (1.0 - kw)
        scored.append((combined, doc))

    scored.sort(key=lambda x: x[0])
    best_score = scored[0][0] if scored else 1.0

    # Filter by threshold
    filtered = [doc for score, doc in scored if score < threshold]

    # Keyword fallback if nothing passed threshold
    if not filtered:
        kw_docs = _keyword_search(query, collection, n=n)
        if kw_docs:
            return kw_docs, 0.2   # low score indicates keyword match

    return filtered[:n] if filtered else [], best_score

def get_recent_conversation_context(user_msg, n=5):
    """
    Fetch recent chat summaries, optionally filtered by time cues in the message.
    Returns a formatted string of summaries, or empty string if none found.
    """
    try:
        client = chromadb.PersistentClient(path=DB_PATH)
        collection = client.get_collection(name=COLLECTION_NAME)
        results = collection.get(where={"source": "chat_summary"})
        docs = results.get("documents", [])
        metadatas = results.get("metadatas", [])
        if not docs:
            return ""

        import datetime
        lower_msg = user_msg.lower()
        now = datetime.datetime.now()

        # Determine time window from message cues
        if 'yesterday' in lower_msg:
            start = now - datetime.timedelta(days=2)
            end = now - datetime.timedelta(days=1)
        elif 'this morning' in lower_msg or 'today' in lower_msg:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now
        else:
            start = now - datetime.timedelta(days=1)
            end = now

        filtered = []
        for i, meta in enumerate(metadatas):
            if not meta or "date" not in meta:
                continue
            try:
                d = datetime.datetime.fromisoformat(meta["date"])
                if start <= d <= end:
                    filtered.append(docs[i])
            except:
                pass

        if filtered:
            return "\n".join(reversed(filtered[-n:]))
        return ""
    except:
        return ""

# Keep other existing functions intact (store_wellness_entry, memory, etc.)
# We'll append them below.

# ---- Wellness logging ----
def store_wellness_entry(text):
    import datetime
    client = chromadb.PersistentClient(path=DB_PATH)
    col = client.get_collection(COLLECTION_NAME)
    col.add(
        ids=[f"wellness_{datetime.datetime.now().isoformat()}"],
        documents=[text],
        metadatas=[{"source": "wellness", "filename": "wellness_log.txt", "date": datetime.datetime.now().isoformat()}]
    )

# ---- Raw message store ----
def store_raw_message(text):
    import datetime
    client = chromadb.PersistentClient(path=DB_PATH)
    col = client.get_collection(COLLECTION_NAME)
    col.add(
        ids=[f"raw_{datetime.datetime.now().isoformat()}"],
        documents=[text],
        metadatas=[{"source": "raw_message", "date": datetime.datetime.now().isoformat()}]
    )

# ---- Conversation memory (placeholder) ----
def clear_conversation_memory():
    pass
def save_conversation_baseline():
    return "Baseline saved."
def restore_conversation_baseline():
    return "Baseline restored."
def memory_status():
    return "Memory OK."
def store_conversation_summary(summary):
    import datetime
    client = chromadb.PersistentClient(path=DB_PATH)
    col = client.get_collection(COLLECTION_NAME)
    col.add(
        ids=[f"summary_{datetime.datetime.now().isoformat()}"],
        documents=[summary],
        metadatas=[{"source": "chat_summary", "date": datetime.datetime.now().isoformat()}]
    )

def delete_chunks_containing(phrase):
    """Delete all chunks whose document text contains the given phrase. Returns count deleted."""
    client = chromadb.PersistentClient(path=DB_PATH)
    col = client.get_collection(COLLECTION_NAME)
    results = col.get()
    ids = results.get("ids", [])
    docs = results.get("documents", [])
    delete_ids = [ids[i] for i, doc in enumerate(docs) if phrase.lower() in doc.lower()]
    if delete_ids:
        col.delete(ids=delete_ids)
    return len(delete_ids)

def delete_chunks_on_date(date_str):
    """Delete all chunks whose metadata date starts with the given date string (YYYY-MM-DD)."""
    client = chromadb.PersistentClient(path=DB_PATH)
    col = client.get_collection(COLLECTION_NAME)
    results = col.get()
    ids = results.get("ids", [])
    metadatas = results.get("metadatas", [])
    delete_ids = [ids[i] for i, meta in enumerate(metadatas) if meta and meta.get("date", "").startswith(date_str)]
    if delete_ids:
        col.delete(ids=delete_ids)
    return len(delete_ids)
