"""
chat_summarizer.py – Summarises meaningful chat exchanges and stores them in the knowledge lake.
Also extracts personal facts in real time and updates the personal graph.
Uses the Phi‑3‑mini model for speed.
"""
import threading
import requests

LLM_URL = "http://127.0.0.1:8081/v1/chat/completions"

def _ask_llm(prompt, max_tokens=50):
    """Send a prompt to the summarizer LLM and return the response text."""
    try:
        resp = requests.post(
            LLM_URL,
            json={
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.2,
            },
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        return ""
    except Exception:
        return ""

def extract_and_update_facts(summary):
    """
    Extract personal facts from a conversation summary and update the graph.
    Uses a flat JSON object from the LLM and maps keys to graph fields.
    """
    if len(summary.strip()) < 20:
        return
    prompt = (
        "You are a personal fact extractor. Given a sentence summarizing a conversation, "
        "extract any new personal facts about the user. Output them as a single JSON object "
        "where each key is a short label (e.g., 'name', 'project', 'location', 'preference') "
        "and each value is the fact. Only include facts explicitly stated. "
        "If no new facts, output an empty JSON object: {}\n\n"
        f"Sentence: {summary}\nFacts (JSON):"
    )
    try:
        import json, re, personal_graph
        resp = requests.post(
            "http://127.0.0.1:8081/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
                "temperature": 0.0,
            },
            timeout=10
        )
        if resp.status_code == 200:
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                facts = json.loads(match.group(0))
                # Simple mapping of common keywords to graph fields
                mapping = {
                    "name": "identity.name",
                    "preferred_address": "identity.preferred_address",
                    "age": "identity.age",
                    "location": "identity.location",
                    "project": "current_projects.primary",
                    "job": "biography.career",
                    "medication": "health_and_wellness.medications",
                    "weight": "health_and_wellness.weight",
                    "exercise": "health_and_wellness.exercise",
                    "diet": "health_and_wellness.dietary_preferences",
                    "mood": "emotional_state.current_mood",
                    "coffee": "preferences_and_quirks.coffee",
                    "philosophy": "preferences_and_quirks.philosophy",
                }
                for key, value in facts.items():
                    value_str = str(value)
                    if key in mapping:
                        personal_graph.update_field(mapping[key], value_str)
                    else:
                        personal_graph.update_field(f"custom_facts.{key}", value_str)
    except Exception:
        pass

def summarize_and_store(user_msg, assistant_reply):
    """
    If the exchange is substantial enough, generate a one‑sentence summary,
    store it in the knowledge lake, and extract personal facts.
    Runs in a background thread so the chat response is never delayed.
    """
    if len(user_msg.strip()) < 20:
        return

    prompt = (
        "Summarise the following conversation exchange in one concise sentence. "
        "Capture the key topic and any personal information the user revealed about themselves. "
        "Use a neutral, factual tone.\n\n"
        f"User: {user_msg}\nAssistant: {assistant_reply}\nSummary:"
    )

    def _run():
        summary = _ask_llm(prompt, max_tokens=60)
        if summary:
            # Do not store summaries that are clearly the LLM failing to recall
            lower = summary.lower()
            blocked = ["i don't have a record", "i couldn't find", "no specific conversation",
                       "no recollection", "don't retain information", "starting fresh",
                       "haven't discussed", "no record", "doesn't have a specific"]
            if not any(phrase in lower for phrase in blocked):
                from lake_ingest import ingest_text
                ingest_text(summary, "chat_summary", tags=["conversation"])

    threading.Thread(target=_run, daemon=True).start()
