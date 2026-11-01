"""LLM-based intent extraction. Uses local Qwen on port 8080."""
import json, re, requests

LLM_URL = "http://127.0.0.1:8080/v1/chat/completions"
LLM_TIMEOUT = 30

SYSTEM_PROMPT = """You extract structured data from line-operator messages about factory production.

Reply with ONE JSON object. No prose, no markdown, no code fence.

Schema:
{
  "intent": "running_job" | "record_hour" | "ending_job" | "changeover_start" |
            "end_changeover" | "start_job" | "status_job" | "status_line" |
            "handover" | "takeover" | "sop" | "cancel" | "unknown",
  "job_number": "WO-NNNN-NNN" or null,
  "target_job_number": "WO-NNNN-NNN" or null,
  "hour": integer 1-8 or null,
  "bottles": integer or null,
  "duration_min": integer or null,
  "line": integer or null,
  "downtime": [{"minutes": number, "station": "Filler|Seamer|Labeler|Packaging|Quality", "reason": "..."}] or [],
  "question": string or null,
  "notes": string or null
}

Rules:
- Job numbers: any prefix works (wo, w0, WO, 20, wO). Normalize to WO-NNNN-NNN.
- Commas or spaces inside a number are thousands separators. "35,022" and "35 022" both = 35022.
- "thirty-four thousand" = 34000.
- running_job is hourly production logging. If bottles are stated, intent is running_job unless a keyword clearly says otherwise.
- If unsure of intent, "unknown". If unsure of a field, null."""

FEW_SHOT = [
    ("running job WO-2610-008, hour 5, 35022 bottles, 2 minutes down jam at the filler",
     '{"intent":"running_job","job_number":"WO-2610-008","target_job_number":null,"hour":5,"bottles":35022,"duration_min":60,"line":null,"downtime":[{"minutes":2,"station":"Filler","reason":"jam"}],"question":null,"notes":null}'),
    ("w0-2610-016 hour five 34 thousand bottles",
     '{"intent":"running_job","job_number":"WO-2610-016","target_job_number":null,"hour":5,"bottles":34000,"duration_min":60,"line":null,"downtime":[],"question":null,"notes":null}'),
    ("changeover job WO-2610-008 to job WO-2610-016",
     '{"intent":"changeover_start","job_number":"WO-2610-008","target_job_number":"WO-2610-016","hour":null,"bottles":null,"duration_min":null,"line":null,"downtime":[],"question":null,"notes":null}'),
    ("status line one",
     '{"intent":"status_line","job_number":null,"target_job_number":null,"hour":null,"bottles":null,"duration_min":null,"line":1,"downtime":[],"question":null,"notes":null}'),
    ("what's the status of line 1",
     '{"intent":"status_line","job_number":null,"target_job_number":null,"hour":null,"bottles":null,"duration_min":null,"line":1,"downtime":[],"question":null,"notes":null}'),
    ("how is job WO-2026-001 doing",
     '{"intent":"status_job","job_number":"WO-2026-001","target_job_number":null,"hour":null,"bottles":null,"duration_min":null,"line":null,"downtime":[],"question":null,"notes":null}'),
    ("sop, labeler E44 error",
     '{"intent":"sop","job_number":null,"target_job_number":null,"hour":null,"bottles":null,"duration_min":null,"line":null,"downtime":[],"question":"labeler E44 error","notes":null}'),
]

def extract(text, timeout=LLM_TIMEOUT):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for u, a in FEW_SHOT:
        messages.append({"role": "user", "content": u})
        messages.append({"role": "assistant", "content": a})
    messages.append({"role": "user", "content": text})
    try:
        r = requests.post(LLM_URL, json={
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 250,
        }, timeout=timeout)
        if r.status_code != 200:
            return {"intent": "unknown", "error": f"HTTP {r.status_code}", "raw": text}
        content = r.json()["choices"][0]["message"]["content"]
        parsed = _parse_json(content)
        if parsed is None:
            return {"intent": "unknown", "error": "invalid JSON", "raw": text, "raw_llm": content}
        parsed.setdefault("intent", "unknown")
        return parsed
    except Exception as e:
        return {"intent": "unknown", "error": str(e), "raw": text}

def _parse_json(s):
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```\w*\n?", "", s)
        s = re.sub(r"\n?```$", "", s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, re.DOTALL)
        if m:
            try: return json.loads(m.group(0))
            except: pass
    return None
