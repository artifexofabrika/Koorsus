"""
lake_router.py – Unified handler for all knowledge‑lake interactions.
Triggered by the classifier's LAKE_RECALL intent.
Returns a reply string.
"""
import requests
import threading
import config
import lake_utils
import chat_summarizer

LLM_URL = config.LLM_URL

def _ask_llm(prompt, max_tokens=150):
    """Send a prompt to the main LLM and return the reply text."""
    try:
        resp = requests.post(
            LLM_URL,
            json={
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.7,
            },
            timeout=60
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        return "I encountered an error, sir. Please try again."
    except Exception:
        return "I encountered an error, sir. Please try again."

def handle_lake_query(user_msg):
    """
    Called when the classifier returns LAKE_RECALL.
    Determines the sub‑type and returns the appropriate reply.
    """
    lower_msg = user_msg.lower()

    # --- Explicit safety‑valve commands (must come first) ---
    if lower_msg.startswith('/forget'):
        phrase = user_msg[8:].strip()
        if not phrase:
            return "What would you like me to forget, sir? Usage: /forget <topic or phrase>"
        deleted = lake_utils.delete_chunks_containing(phrase)
        return f'I have removed {deleted} references to "{phrase}", sir.'

    if lower_msg.startswith('/purge-date'):
        date_str = user_msg[12:].strip()
        if not date_str:
            return "Please specify a date, sir. Usage: /purge-date YYYY-MM-DD"
        deleted = lake_utils.delete_chunks_on_date(date_str)
        return f'I have removed {deleted} chunks from {date_str}, sir.'

    # --- Determine which sub‑handler to use ---
    # 1. Lake‑contents inquiry (no LLM)
    if any(p in lower_msg for p in ['in your data lake', 'in the knowledge lake',
                                      'what do you have in your lake', 'what information do you have',
                                      'what kind of information', 'what is in my lake']):
        try:
            import chromadb
            client = chromadb.PersistentClient(path="/mnt/lake/index")
            col = client.get_collection("memory_lake")
            results = col.get()
            sources = results.get("metadatas", [])
            if sources:
                source_counts = {}
                for m in sources:
                    if m and "source" in m:
                        src = m["source"]
                        source_counts[src] = source_counts.get(src, 0) + 1
                summary_lines = [f"- {src}: {cnt} chunks" for src, cnt in sorted(source_counts.items())]
                total_chunks = len(sources)
                return f"Your knowledge lake contains {total_chunks} total chunks across these sources:\n" + "\n".join(summary_lines)
            else:
                return "Your knowledge lake is currently empty, sir."
        except Exception as e:
            return f"Could not query the lake: {str(e)}"

    # 2. Past‑conversation recall
    if any(p in lower_msg for p in ['talked about', 'what did we', 'what have we', 'previous conversation',
                                      'earlier', 'this morning', 'today', 'yesterday', 'recall',
                                      'data from yesterday', 'information from yesterday', 'anything from yesterday',
                                      'any data from today', 'do you have any information']):
        ctx = lake_utils.get_recent_conversation_context(user_msg)
        if ctx:
            prompt = (
                f"You are Jeeves, a calm, erudite personal valet. The following are summaries of recent "
                f"conversations. Use them to answer the user's question in a warm, concise manner. Do not "
                f"mention that you are reading summaries; simply answer as if you remember.\n\n"
                f"Recent conversations:\n{ctx}\n\nUser: {user_msg}\nJeeves:"
            )
            reply = _ask_llm(prompt)
            threading.Thread(target=chat_summarizer.summarize_and_store,
                             args=(user_msg, reply), daemon=True).start()
            return reply
        else:
            return "I found nothing in your knowledge lake. Would you like me to search the web for that, sir?"

    # 3. Generic factual retrieval (fallback)
    # Extract a clean search phrase from the natural message
    search_phrase = user_msg
    for trigger in ['data lake', 'knowledge lake']:
        if trigger in lower_msg:
            idx = lower_msg.find(trigger)
            # Take the text after the trigger, or the text before it as the query
            after_trigger = user_msg[idx+len(trigger):].strip().lstrip(',:; ')
            if after_trigger:
                search_phrase = after_trigger
            else:
                # Use the part before the trigger if nothing follows it
                search_phrase = user_msg[:idx].strip()
            break
    docs, _ = lake_utils.query_lake(search_phrase, n=3)
    if docs:
        context = "\n".join(docs)
        prompt = (
            f"You are Jeeves, a calm, erudite personal valet. Use the information below to answer the "
            f"question. If the information does not contain the answer, say so.\n\n"
            f"Private knowledge lake:\n{context}\n\nUser: {user_msg}\nJeeves:"
        )
        reply = _ask_llm(prompt)
        threading.Thread(target=chat_summarizer.summarize_and_store,
                         args=(user_msg, reply), daemon=True).start()
        return reply
    else:
        return "I found nothing in your knowledge lake. Would you like me to search the web for that, sir?"
