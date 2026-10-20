"""
rag/ingest.py — Multi-format document ingestion.

Extracts text from .txt, .md, .pdf, .docx, and .odt files, chunks it with
the token-aware splitter, and stores it in the collection with source
metadata. Can be run as a module:

    python -m rag.ingest <file_or_directory> [--reset]
"""

import sys
from pathlib import Path

import config
from rag import chunking, store


# --- Extractors, one per format ---

def extract_txt(path):
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_md(path):
    return extract_txt(path)


def extract_pdf(path):
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text.strip():
            pages.append(text)
    return "\n\n".join(pages)


def extract_docx(path):
    from docx import Document
    doc = Document(str(path))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_odt(path):
    from odf.opendocument import load
    from odf import text as odf_text, teletype
    doc = load(str(path))
    parts = []
    for para in doc.getElementsByType(odf_text.P):
        text = teletype.extractText(para)
        if text.strip():
            parts.append(text)
    return "\n\n".join(parts)


EXTRACTORS = {
    ".txt": extract_txt,
    ".md": extract_md,
    ".pdf": extract_pdf,
    ".docx": extract_docx,
    ".odt": extract_odt,
}


def extract_text(path):
    ext = path.suffix.lower()
    fn = EXTRACTORS.get(ext)
    if fn is None:
        raise ValueError(f"Unsupported extension: {ext}")
    return fn(path)


# --- Ingest entry points ---

def ingest_file(path, reset=False, source_name=None):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if reset:
        store.reset_collection()
    text = extract_text(path)
    chunks = chunking.chunk_text(text)
    source = source_name if source_name else path.name
    count = store.add_chunks(
        chunks,
        source=source,
        extra_metadata={
            "file_type": path.suffix.lower(),
            "original_path": str(path),
        },
    )
    return count


def ingest_directory(dirpath, reset=False):
    dirpath = Path(dirpath)
    files = sorted(
        p for p in dirpath.iterdir()
        if p.is_file() and p.suffix.lower() in config.SUPPORTED_EXTENSIONS
    )
    if reset:
        store.reset_collection()
    total = 0
    for f in files:
        try:
            n = ingest_file(f, reset=False)
            print(f"  {f.name}: {n} chunks")
            total += n
        except Exception as e:
            print(f"  {f.name}: ERROR — {e}")
    return total


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m rag.ingest <file_or_directory> [--reset]")
        sys.exit(1)
    target = Path(sys.argv[1])
    reset = "--reset" in sys.argv
    if target.is_dir():
        total = ingest_directory(target, reset=reset)
    else:
        total = ingest_file(target, reset=reset)
    print(f"\nTotal chunks ingested: {total}")
    s = store.stats()
    print(f"Collection total: {s['total_chunks']}")
    for src, cnt in sorted(s["sources"].items()):
        print(f"  {src}: {cnt}")
