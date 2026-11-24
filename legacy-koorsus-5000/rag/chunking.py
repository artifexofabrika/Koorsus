"""
rag/chunking.py — Token-based, section-aware text splitter.

Splits documents into chunks of roughly CHUNK_TOKENS tokens with
CHUNK_OVERLAP_TOKENS of overlap. Recognises section headings (short,
all-caps or colon-terminated lines) as hard boundaries so that chunks
do not straddle unrelated sections. Each chunk is prefixed with its
section heading to keep embedding context clean.
"""

import re
import config
from transformers import AutoTokenizer

_TOKENIZER = None

# Heading detection: a paragraph is treated as a heading if it is short
# and either (a) is mostly uppercase, or (b) ends with a colon, or
# (c) matches patterns like "SECTION 1:", "Chapter 3.", etc.
_HEADING_PATTERN = re.compile(
    r'^\s*(SECTION\s+\d+|CHAPTER\s+\d+|PART\s+\d+|[A-Z][A-Z0-9 ,\-&]{4,80}:?)\s*$'
)


def _get_tokenizer():
    global _TOKENIZER
    if _TOKENIZER is None:
        _TOKENIZER = AutoTokenizer.from_pretrained(
            f"sentence-transformers/{config.EMBED_MODEL_NAME}"
        )
    return _TOKENIZER


def token_len(text):
    return len(_get_tokenizer().encode(text, add_special_tokens=False))


def _split_paragraphs(text):
    parts = re.split(r'\n\s*\n', text)
    result = [p.strip() for p in parts if p.strip()]
    return result if result else [text.strip()]


def _split_sentences(text):
    parts = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in parts if s.strip()]


def _is_heading(paragraph):
    """Heuristic: is this paragraph a section heading?"""
    if not paragraph:
        return False
    text = paragraph.strip()
    if len(text) > 100:
        return False
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    # All letters uppercase: e.g. "SECTION 1: FACILITY OVERVIEW"
    if all(c.isupper() for c in letters):
        return True
    # Or explicit marker with mixed case
    if re.match(r"^(SECTION|CHAPTER|PART)\s+\d+", text, re.IGNORECASE):
        return True
    return False


def _tail_for_overlap(sentences, overlap_tokens):
    if not sentences or overlap_tokens <= 0:
        return []
    tail = []
    total = 0
    for sent in reversed(sentences):
        t = token_len(sent)
        if tail and total + t > overlap_tokens:
            break
        tail.insert(0, sent)
        total += t
        if total >= overlap_tokens:
            break
    return tail


def _hard_split(sentence, max_tokens):
    tok = _get_tokenizer()
    ids = tok.encode(sentence, add_special_tokens=False)
    pieces = []
    for i in range(0, len(ids), max_tokens):
        piece = tok.decode(ids[i:i + max_tokens], skip_special_tokens=True)
        if piece.strip():
            pieces.append(piece.strip())
    return pieces


def chunk_text(text, max_tokens=None, overlap_tokens=None):
    """Section-aware chunking with overlap."""
    if max_tokens is None:
        max_tokens = config.CHUNK_TOKENS
    if overlap_tokens is None:
        overlap_tokens = config.CHUNK_OVERLAP_TOKENS

    if not text or not text.strip():
        return []

    paragraphs = _split_paragraphs(text)
    chunks = []
    current = []
    current_tokens = 0
    current_heading = ""

    def flush():
        nonlocal current, current_tokens
        if current:
            body = " ".join(current)
            if current_heading:
                body = f"{current_heading} {body}"
            chunks.append(body)
        current = []
        current_tokens = 0

    for para in paragraphs:
        # Heading: hard boundary. Flush current chunk, start a new section.
        if _is_heading(para):
            flush()
            current_heading = para.strip()
            continue

        for sent in _split_sentences(para):
            sent_tokens = token_len(sent)

            if sent_tokens > max_tokens:
                flush()
                for piece in _hard_split(sent, max_tokens):
                    body = f"{current_heading} {piece}" if current_heading else piece
                    chunks.append(body)
                continue

            if current and current_tokens + sent_tokens > max_tokens:
                flush()
                # Overlap within the same section only.
                # We deliberately do not carry overlap across headings,
                # because the heading prefix already provides continuity.
                current = _tail_for_overlap(current, overlap_tokens)
                current_tokens = sum(token_len(s) for s in current)

            current.append(sent)
            current_tokens += sent_tokens

    flush()
    return chunks


def chunk_stats(chunks):
    if not chunks:
        return {"count": 0}
    sizes = [token_len(c) for c in chunks]
    return {
        "count": len(chunks),
        "min": min(sizes),
        "max": max(sizes),
        "mean": round(sum(sizes) / len(sizes), 1),
    }


# ---------- quick test ----------
if __name__ == "__main__":
    sample = (
        "SECTION 1: FACILITY OVERVIEW\n\n"
        "Midwest Precision operates a 68,000 square foot facility. Annual "
        "revenue was 14.2 million dollars. No single customer represents "
        "more than 32 percent of revenue.\n\n"
        "SECTION 2: QUALITY MANAGEMENT\n\n"
        "First-pass yield averaged 97.3 percent. The target is 98.0 percent. "
        "The largest single source of scrap is tool breakage on Cell 2."
    )
    chunks = chunk_text(sample)
    stats = chunk_stats(chunks)
    print(f"Chunks: {stats['count']}  min/mean/max: {stats['min']}/{stats['mean']}/{stats['max']}")
    for i, c in enumerate(chunks):
        print(f"\n--- chunk {i} ({token_len(c)} tokens) ---")
        print(c)
