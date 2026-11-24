"""
config.py - Central configuration for Arkiv.
"""
import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# --- Paths ---
DB_PATH = "/mnt/lake/arkiv_index"
COLLECTION_NAME = "arkiv_documents"

# --- Authentication (shared office PIN) ---
# CHANGE BOTH BEFORE ANY CUSTOMER INSTALL.
SECRET_KEY = "REPLACE-WITH-A-RANDOM-64-CHAR-STRING"
ARKIV_PIN = "REPLACE-WITH-A-STRONG-OFFICE-PIN"
SESSION_TIMEOUT_MIN = 480

# --- Embedding model ---
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
EMBED_DEVICE = "cpu"

# --- Local LLM (shared llama.cpp server on 8080) ---
LLM_URL = "http://127.0.0.1:8080/v1/chat/completions"
LLM_MODEL = "local"
LLM_MAX_TOKENS = 512
LLM_TEMPERATURE = 0.0

# --- Chunking (token-based) ---
CHUNK_TOKENS = 120
CHUNK_OVERLAP_TOKENS = 30

# --- Retrieval ---
RETRIEVAL_TOP_K = 8
SEMANTIC_CANDIDATES = 10
KEYWORD_CANDIDATES = 10
MAX_CONTEXT_TOKENS = 900

# --- Ingestion ---
SUPPORTED_EXTENSIONS = [".txt", ".md", ".pdf", ".docx", ".odt"]

# --- Grounding policy ---
GROUNDING = "strict"

SYSTEM_PROMPT = (
    "You are a private document assistant for a professional office. "
    "Answer only using the provided context. "
    "If the context does not contain the answer, say plainly that it is not in the documents. "
    "Cite the source document for every claim. "
    "Do not speculate. Do not use outside knowledge."
)
