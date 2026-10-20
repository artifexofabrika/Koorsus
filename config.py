"""
config.py — Central configuration for the Jeeves RAG appliance.
"""

import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from pathlib import Path

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = "/mnt/lake/index"          # ChromaDB persistence directory
COLLECTION_NAME = "memory_lake"      # single collection for the client
SAMPLE_DOCS_DIR = BASE_DIR / "demo" / "sample_docs"

# --- Embedding model ---
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
EMBED_DEVICE = "cpu"                 # leave GPU memory to the LLM

# --- Local LLM (llama.cpp server) ---
LLM_URL = "http://127.0.0.1:8080/v1/chat/completions"
LLM_MODEL = "local"                  # llama.cpp ignores this field, but it must be present
LLM_MAX_TOKENS = 512                 # response length ceiling
LLM_TEMPERATURE = 0.0                # deterministic, for SOPs

# --- Chunking (token-based) ---
CHUNK_TOKENS = 120                   # target tokens per chunk
CHUNK_OVERLAP_TOKENS = 30            # overlap between consecutive chunks

# --- Retrieval ---
RETRIEVAL_TOP_K = 5                  # final chunks passed to the LLM
SEMANTIC_CANDIDATES = 10             # semantic search breadth before fusion
KEYWORD_CANDIDATES = 10              # keyword search breadth before fusion
MAX_CONTEXT_TOKENS = 900            # total retrieved context ceiling for the LLM

# --- Ingestion ---
SUPPORTED_EXTENSIONS = [".txt", ".md", ".pdf", ".docx", ".odt"]

# --- Grounding policy ---
# strict: answer only from retrieved context; say "not in the documents" otherwise.
GROUNDING = "strict"

SYSTEM_PROMPT = (
    "You are a private assistant for manufacturing operations. "
    "Answer only using the provided context. "
    "If the context does not contain the answer, say plainly that it is not in the documents. "
    "Cite the source document for every claim."
)

# Telegram
TELEGRAM_BOT_TOKEN = "8803200140:AAGi3JObWNfVktqJ9aXjYc-cpsQe_sIt5_c"
TELEGRAM_CHAT_ID = 7451582244
