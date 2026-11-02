"""Myarra bot v3 - fast-path for structured triggers, LLM for natural language."""
import re, sys
import intent as intent_mod
import bot_v2

STRUCTURED_PATTERNS = [
    r'^(run|running)\b',
    r'^record\b',
    r'^(end|ending|finish|finishing)\b',
    r'^(and|en)\s+(lunch|cip|maintenance|change|job|shift|wo|work|order)',
    r'^clos\w*\b',
    r'^(start|starting|begin|beginning)\b',
    r'^change[\s-]*over\b',
    r'^status\b',
    r'^(sop|ask|question)\b',
    r'^handover\b',
    r'^(taking\s+over|take\s+over|took\s+over)\b',
    r'^(pause|pausing|suspend|suspending|hold|holding)\b',
    r'^(resume|resuming|restart|restarting|unpause|continue|continuing)\b',
    r'^back\s+to\b',
    r'^(cancel|stop|quit|exit)\s*$',
    r'^confirm[\s,]',
]


def _is_structured(text):
    low = text.lower().strip()
    return any(re.match(p, low) for p in STRUCTURED_PATTERNS)


def _running(p):
    s = f"running job {p.get('job_number') or ''}"
    if p.get('hour') is not None:
        s += f", hour {p['hour']}"
    u = p.get('units') or p.get('bottles')
    if u is not None:
        s += f", {u} units"
    for d in (p.get('downtime') or []):
        s += f", {d.get('minutes', 0)} minutes down {d.get('reason') or ''} at {d.get('station') or ''}"
    return s


def rebuild(intent_name, p):
    if intent_name == 'running_job':    return _running(p)
    if intent_name == 'start_job':
        if p.get('hour') is not None and (p.get('units') or p.get('bottles')):
            return _running(p)
        return f"start job {p.get('job_number') or ''}"
    if intent_name == 'record_hour':
        parts = ["record production hour"]
        if p.get('hour') is not None: parts.append(str(p['hour']))
        if p.get('duration_min') is not None: parts.append(f"{p['duration_min']} minutes")
        u = p.get('units') or p.get('bottles')
        if u is not None: parts.append(f"{u} units")
        job_part = f" for {p['job_number']}" if p.get('job_number') else ""
        return ", ".join(parts) + job_part
    if intent_name == 'ending_job':
        return f"end {p.get('job_number') or ''}"
    if intent_name == 'changeover_start':
        return f"changeover job {p.get('job_number') or ''} to {p.get('target_job_number') or ''}"
    if intent_name == 'end_changeover':
        return "end changeover"
    if intent_name == 'pause_job':
        return f"pause {p.get('job_number') or ''}"
    if intent_name == 'resume_job':
        return f"resume {p.get('job_number') or ''}"
    if intent_name == 'status_job':
        return f"status {p.get('job_number') or ''}"
    if intent_name == 'status_line':
        return f"status line {p.get('line') or ''}"
    if intent_name == 'handover':
        return f"handover job {p.get('job_number') or ''}"
    if intent_name == 'takeover':
        return f"taking over job {p.get('job_number') or ''}"
    if intent_name == 'sop':
        return f"sop, {p.get('question') or ''}"
    if intent_name == 'cancel':
        return "cancel"
    return None


def dispatch(conn, s, text, user):
    text = (text or "").strip()
    if not text:
        return None

    if s.get('state') != 'idle':
        return bot_v2.dispatch(conn, s, text, user)

    if _is_structured(text):
        return bot_v2.dispatch(conn, s, text, user)

    parsed = intent_mod.extract(text)
    name = parsed.get('intent', 'unknown')
    if parsed.get('error'):
        print(f"[v3] LLM error: {parsed['error']} -> regex fallback", file=sys.stderr)
        return bot_v2.dispatch(conn, s, text, user)
    if name == 'unknown':
        print(f"[v3] unknown -> regex fallback", file=sys.stderr)
        return bot_v2.dispatch(conn, s, text, user)

    clean = rebuild(name, parsed)
    if clean is None:
        print(f"[v3] no rebuild for {name} -> regex fallback", file=sys.stderr)
        return bot_v2.dispatch(conn, s, text, user)

    print(f"[v3] {name} -> {clean[:110]}", file=sys.stderr)
    return bot_v2.dispatch(conn, s, clean, user)
