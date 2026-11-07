"""bot/dispatch.py — The router. Single entry point for bot_live_v3.py.

Agreed 2026-11-07: replaces the dispatch() function in bot_v2.py.

Order of routing:
    1. If the session is awaiting a specific state, route to its handler.
    2. Otherwise, match the command against the pattern table.
    3. Unknown commands fall through to h_unknown.
"""
import re
from datetime import datetime

from . import db
from . import production, changeover, maintenance, handover, notes, support, jobs, shift

from parsers import (parse_job_number, parse_hour, parse_line_number)


# Agreed 2026-11-06: every incoming message is logged before routing.
def _audit(conn, user, text):
    conn.execute(
        "INSERT INTO audit_log (user_id, raw_text, created_at) VALUES (?,?,?)",
        (user['id'] if user else None, text, datetime.now().isoformat()))
    conn.commit()


def dispatch(conn, s, text, user):
    _audit(conn, user, text)
    text = (text or '').strip()
    if not text:
        return None
    low = text.lower()

    # ---- State machine ----
    state = s.get('state')
    if state == 'awaiting_variance_reason':
        return jobs.cont_variance_reason(conn, s, text, user)
    if state == 'awaiting_relog_reason':
        return notes.cont_relog_reason(conn, s, text, user)
    if state == 'awaiting_maint_minutes':
        return maintenance.cont_maint_minutes(conn, s, text, user)
    if state == 'maint_prompt':
        return maintenance.handle_maint_prompt(conn, s, text, user)
    if state == 'awaiting_shift_reason':
        return shift.cont_shift_reason(conn, s, text, user)
    if state == 'awaiting_start_minutes':
        return jobs.cont_start_minutes(conn, s, text, user)
    if state == 'awaiting_end_minutes':
        return jobs.cont_end_minutes(conn, s, text, user)
    if state == 'awaiting_co_minutes':
        return changeover.cont_co_minutes(conn, s, text, user)
    if state == 'awaiting_co_step':
        return changeover.cont_co_step(conn, s, text, user)
    if state == 'awaiting_handover_notes':
        return handover.cont_handover_notes(conn, s, text, user)

    # ---- Command matching ----
    # Help / unknown
    if low in ('help', '/help'):
        return support.h_help(conn, s, text, user)

    # Notes and relog first (they use "note" and "relog" prefixes that could
    # confuse the command matchers below).
    reply = notes.try_note(conn, s, text, user)
    if reply is not None:
        return reply
    reply = notes.try_relog(conn, s, text, user)
    if reply is not None:
        return reply

    # Shift
    if re.match(r'^start\s+shift\b', low):
        return shift.h_start_shift(conn, s, text, user)
    if re.match(r'^end\s+shift\b', low):
        return shift.h_end_shift(conn, s, text, user)

    # Maintenance
    if re.match(r'^end\s+maintenance\b', low):
        return maintenance.h_end_maintenance(conn, s, text, user)
    if re.match(r'^(start\s+)?maintenance\b', low):
        return maintenance.h_start_maintenance(conn, s, text, user)
    if re.match(r'^idle\b', low):
        return maintenance.h_idle(conn, s, text, user)
    if re.match(r'^unscheduled\b', low):
        return maintenance.h_unscheduled(conn, s, text, user)

    # Changeover
    if re.match(r'^end\s+change[\s-]*over\b', low):
        return changeover.h_end_changeover(conn, s, text, user)
    if re.match(r'^change[\s-]*over\b', low):
        return changeover.h_changeover_start(conn, s, text, user)

    # Production
    if re.match(r'^(running|run)\b', low):
        return production.h_running_job(conn, s, text, user)
    if re.match(r'^record\b', low) and 'production hour' in low:
        return production.h_record_hour(conn, s, text, user)

    # Job lifecycle
    if re.match(r'^(end(ing)?|finish(ing)?|clos\w*)\b', low):
        return jobs.h_ending_job(conn, s, text, user)
    if re.match(r'^(start|starting|begin|beginning)\b', low):
        return jobs.h_start_job(conn, s, text, user)
    if re.match(r'^(pause|pausing|suspend|suspending|hold|holding)\b', low):
        return jobs.h_pause_job(conn, s, text, user)
    if re.match(r'^(resume|resuming|restart|restarting|unpause|continue|continuing)\b', low) \
       or re.match(r'^back\s+to\b', low):
        return jobs.h_resume_job(conn, s, text, user)

    # Handover
    if re.match(r'^handover\b', low):
        return handover.h_handover(conn, s, text, user)
    if re.match(r'^(taking\s+over|take\s+over|took\s+over)\b', low):
        return handover.h_takeover(conn, s, text, user)

    # Status
    if re.match(r'^status\b', low):
        if 'line' in low:
            return support.h_status_line(conn, s, text, user)
        if parse_job_number(text):
            return support.h_status_job(conn, s, text, user)
        return "Say: 'status line N' or 'status WO-XXXX-XXX'."

    # SOP
    if re.match(r'^(sop|ask|question)\b', low):
        return support.h_sop(conn, s, text, user)

    # Fallback
    return support.h_unknown(conn, s, text, user)
