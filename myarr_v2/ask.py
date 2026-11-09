"""Stage D: Text-to-SQL for plain-English questions about the plant."""
import json, requests, sqlite3

LLM_URL = "http://127.0.0.1:8080/v1/chat/completions"
LLM_TIMEOUT = 60
DB_PATH = "/mnt/lake/myarra.db"

AVAILABLE_VIEWS = [
    "v_oee_by_line_day",
    "v_oee_summary",
    "v_operator_perf_by_line_day",
    "v_production_vs_standard",
    "v_changeover_variance",
    "v_changeover_by_station",
    "v_unaccounted_by_line_day",
    "v_maintenance_by_station",
    "v_pdca_trend",
]

def _get_schemas():
    conn = sqlite3.connect(DB_PATH)
    parts = []
    for view in AVAILABLE_VIEWS:
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(%s)" % view).fetchall()]
            parts.append(view + ": " + ", ".join(cols))
        except Exception:
            pass
    conn.close()
    return "\n".join(parts)

_VIEW_SCHEMAS = _get_schemas()

SYSTEM_PROMPT = (
    "You are a SQL analyst for a manufacturing plant. "
    "Translate the user's question into a single, safe SQLite SELECT query.\n\n"
    "Here are the available VIEWS and their exact column names. Use ONLY these views and columns:\n\n"
    + _VIEW_SCHEMAS +
    "\n\nRules:\n"
    "- Return ONLY the SQL query. No prose, no markdown, no code fences.\n"
    "- Never use INSERT, UPDATE, DELETE, DROP, ALTER, or ATTACH.\n"
    "- If asked about OEE, use v_oee_summary and the 'oee' column.\n"
    "- If asked about line names (e.g. 'Line 1'), use line_id = 1.\n"
    "- If asked about stations (e.g. 'labeler'), use the 'station' column.\n"
    "- If the question cannot be answered with these views, return 'UNANSWERABLE'.\n"
    "- If the question is ambiguous, make a reasonable assumption and return the SQL."
)

def ask(question, timeout=LLM_TIMEOUT):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question}
    ]
    try:
        r = requests.post(LLM_URL, json={
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 300,
        }, timeout=timeout)
        r.raise_for_status()
        raw = r.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        return {"error": "LLM request failed: " + str(e)}

    if raw.upper().strip() == 'UNANSWERABLE':
        return {"error": "I cannot answer that question with the available data."}

    sql = raw.strip().strip('`').strip()
    if not sql.upper().startswith('SELECT'):
        return {"error": "Refused unsafe query: " + sql[:80]}

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.execute(sql)
        rows = [dict(r) for r in cur.fetchall()]
        cols = [d[0] for d in cur.description] if cur.description else []
        conn.close()
        return {"sql": sql, "columns": cols, "rows": rows, "count": len(rows)}
    except Exception as e:
        return {"error": "Query failed: " + str(e), "sql": sql}
