"""
rag/generate.py — Build prompts and call the local LLM (llama.cpp).

Strict grounding: the model is told to answer only from retrieved context
and to cite the source of every claim.
"""

import requests
import config
from rag.retrieve import format_context


def build_messages(query, results):
    context = format_context(results) if results else "(no relevant documents found)"
    system = config.SYSTEM_PROMPT
    user = (
        f"Context:\n{context}\n\n"
        f"Question: {query}\n\n"
        "Answer using only the context above. Cite the source document."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def call_llm(messages, timeout=120):
    payload = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "max_tokens": config.LLM_MAX_TOKENS,
        "temperature": config.LLM_TEMPERATURE,
        "stream": False,
    }
    resp = requests.post(config.LLM_URL, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def answer(query, results):
    messages = build_messages(query, results)
    return call_llm(messages)


# ---------- quick test ----------
if __name__ == "__main__":
    from rag.retrieve import retrieve
    q = "What is the mean time between failures on the passivation line?"
    results = retrieve(q, top_k=3)
    print(f"Q: {q}\n")
    print("Retrieved chunks:")
    for i, r in enumerate(results, 1):
        print(f"  [{i}] {(r.get('meta') or {}).get('source', '?')}")
    print("\nLLM answer:\n")
    print(answer(q, results))
