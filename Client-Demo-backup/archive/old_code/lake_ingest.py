"""
lake_ingest.py – Clean, universal ingestion pipeline for Jeeves.
Chunks text, tags with Phi‑3‑mini, stores in the new memory_lake collection.
"""
import re
import datetime
import uuid
import requests
import chromadb
from chromadb.utils import embedding_functions

# Constants
CHUNK_SIZE = 500          # max characters per chunk
CHUNK_OVERLAP = 50        # characters of overlap between chunks
LLM_URL = "http://127.0.0.1:8081/v1/chat/completions"
COLLECTION_NAME = "memory_lake"
DB_PATH = "/mnt/lake/index"

# Embedding function – must match what the collection was created with
EMBED_FN = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

def _get_collection():
    """Return the ChromaDB collection, creating it if needed with the correct embedding function."""
    client = chromadb.PersistentClient(path=DB_PATH)
    try:
        collection = client.get_collection(COLLECTION_NAME)
    except Exception:
        # Collection doesn't exist yet, create it
        collection = client.create_collection(
            name=COLLECTION_NAME,
            embedding_function=EMBED_FN
        )
    return collection

def _split_text(text):
    """
    Split text into coherent chunks of at most CHUNK_SIZE characters,
    with CHUNK_OVERLAP overlap, respecting sentence boundaries where possible.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) <= CHUNK_SIZE:
            current = (current + " " + sentence).strip()
        else:
            if current:
                chunks.append(current)
            # Start new chunk with overlap: take the last few words of the previous chunk
            if chunks:
                last_chunk = chunks[-1]
                overlap_words = " ".join(last_chunk.split()[-5:])  # roughly 50 chars
                current = overlap_words + " " + sentence
            else:
                current = sentence
    if current:
        chunks.append(current)
    return chunks

def _generate_tags(chunk_text):
    """Ask Phi‑3‑mini to generate 3‑5 keywords for a chunk of text."""
    prompt = (
        "You are a keyword generator. Given a piece of text, list 3‑5 relevant keywords "
        "separated by commas. Only output the keywords, nothing else.\n\n"
        f"Text: {chunk_text[:300]}\nKeywords:"
    )
    try:
        resp = requests.post(
            LLM_URL,
            json={
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 20,
                "temperature": 0.0,
            },
            timeout=5
        )
        if resp.status_code == 200:
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            # Clean up and return as a list
            tags = [t.strip().lower() for t in raw.split(",") if t.strip()]
            return tags[:5]
    except Exception:
        pass
    return []

def ingest_text(text, source_name, tags=None):
    """
    Ingest a block of text into the knowledge lake.
    - text: the full text to be chunked and stored.
    - source_name: a label like 'chat_summary', 'web_search', 'journal'.
    - tags: optional list of manual tags to be added to every chunk.
    Returns the number of chunks stored.
    """
    if tags is None:
        tags = []
    collection = _get_collection()
    chunks = _split_text(text)
    now = datetime.datetime.now().isoformat()
    ids = []
    documents = []
    metadatas = []
    for i, chunk in enumerate(chunks):
        # Generate AI tags for this chunk
        ai_tags = _generate_tags(chunk)
        all_tags = list(set(tags + ai_tags))  # combine manual and AI tags
        chunk_id = f"{source_name}_{uuid.uuid4().hex[:8]}"
        ids.append(chunk_id)
        documents.append(chunk)
        metadatas.append({
            "source": source_name,
            "date": now,
            "tags": ",".join(all_tags),
        })
    if ids:
        collection.add(ids=ids, documents=documents, metadatas=metadatas)
    return len(ids)

# ---------- quick test ----------
if __name__ == "__main__":
    sample = (
        "Sharks are a group of elasmobranch fish characterized by a cartilaginous skeleton, "
        "five to seven gill slits on the sides of the head, and pectoral fins that are not fused to the head. "
        "Modern sharks are classified within the clade Selachimorpha and are the sister group to the rays. "
        "There are over 500 species of sharks, ranging in size from the small dwarf lanternshark, "
        "a deep sea species of only 17 centimeters in length, to the whale shark, the largest fish in the world, "
        "which reaches approximately 12 meters in length."
    )
    count = ingest_text(sample, "test", tags=["sharks", "marine biology"])
    print(f"Ingested {count} chunks.")
