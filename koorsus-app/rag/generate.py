"""Build prompts and call the local LLM (llama.cpp).

The model is constrained to return JSON, so refusal is a boolean rather than
a phrase we guess at, and so the citations it returns can be checked against
the documents actually supplied.
"""
import json

import requests

import config
from rag.retrieve import format_context

_SYSTEM = config.SYSTEM_PROMPT + (
    " Reply with a single JSON object and nothing else, with exactly these"
    " keys: found (true or false), answer (two sentences at most, drawn only"
    " from the context), cites (the list of source document names you used)."
    " Set found to false and cites to an empty list when the context does not"
    " contain the answer. Set found to true only when the context"
    " states the answer explicitly; never infer or compute it."
    " Amounts alleged, claimed, or demanded are not amounts awarded,"
    " and a motion is not a ruling."
)

_SCHEMA = {"type": "json_object"}


def build_messages(query, results):
    if results:
        context = format_context(results)
    else:
        context = "(no relevant documents found)"
    user = "Context:\n" + context + "\n\nQuestion: " + query
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user},
    ]


def call_llm(messages, timeout=120):
    payload = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "max_tokens": config.LLM_MAX_TOKENS,
        "temperature": config.LLM_TEMPERATURE,
        "stream": False,
        "response_format": _SCHEMA,
    }
    resp = requests.post(config.LLM_URL, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def answer(query, results):
    """Return (text, found, cites). Raises if the model returns no JSON."""
    raw = call_llm(build_messages(query, results))
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("model returned no JSON object")
    data = json.loads(raw[start:end + 1])
    found = bool(data.get("found"))
    text = str(data.get("answer") or "").strip()
    cites = data.get("cites") or []
    if not isinstance(cites, list):
        cites = []
    cites = [str(c) for c in cites]
    if not text:
        found = False
    return text, found, cites
