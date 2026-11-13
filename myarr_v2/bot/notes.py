"""bot/notes.py — Free-text notes and relog with audit trail.

Two commands:
    note: <text>              — attach note to most recent hour on active job
    note hour N: <text>       — attach note to a specific hour on user's line

    relog job WO-XXXX hour N, <units>[, <scrap>]
        Marks the original hourly_run as superseded=1 and prompts for a
        reason. After the reason, the relog re-runs as a normal production
        entry with override_reason set.

Agreed 2026-11-06/07: operator notes are free text; scrap on relog is
captured like any other hour; every relog carries a stated reason.
"""
import re

from . import db, production
from parsers import parse_job_number, parse_hour


NOTE_RE = re.compile(
    r'^(note|comment|memo)\s*(?:hour\s*(\d+))?:?\s+(.*)',
    re.IGNORECASE)
RELOG_RE = re.compile(
    r'^(relog|re-log|correct)\s+(.*)',
    re.IGNORECASE)


def try_note(conn, s, text, user):
    """If text is a note command, handle it. Returns reply or None."""
    m = NOTE_RE.match(text)
    if not m:
        return None
    note_hour = m.group(2)
    note_text = m.group(3).strip()
    if not note_text:
        return "Please provide note text. E.g. 'note: label roll change' or 'note hour 3: case feeder jam'."

    if note_hour:
        period = f"H{note_hour}"
        line_id = s.get('line_id') or (user.get('line_id') if user else None)
        if line_id:
            target = conn.execute("""
                SELECT id FROM hourly_runs
                WHERE line_id=? AND period=? AND date(recorded_at)=date('now')
                  AND (superseded IS NULL OR superseded=0)
                ORDER BY id DESC LIMIT 1
            """, (line_id, period)).fetchone()
        elif s.get('active_job_id'):
            target = conn.execute("""
                SELECT id FROM hourly_runs WHERE job_id=? AND period=?
                  AND (superseded IS NULL OR superseded=0)
                ORDER BY id DESC LIMIT 1
            """, (s['active_job_id'], period)).fetchone()
        else:
            return "Need a line or active job to attach this note."
        if not target:
            return f"No existing {period} entry found today for your line."
    else:
        job_id = s.get('active_job_id')
        if not job_id:
            line_id = s.get('line_id') or (user.get('line_id') if user else None)
            if line_id:
                cur = db.current_line_event(conn, line_id)
                if cur and cur['job_id']:
                    job_id = cur['job_id']
        if not job_id:
            return "No active job. Say 'note hour N: text' to target a specific hour."
        target = conn.execute("""
            SELECT id, period FROM hourly_runs
            WHERE job_id=? AND (superseded IS NULL OR superseded=0)
            ORDER BY id DESC LIMIT 1
        """, (job_id,)).fetchone()
        if not target:
            return "No hourly entries found for the current job."
        period = target['period']

    conn.execute("UPDATE hourly_runs SET notes=? WHERE id=?", (note_text, target['id']))
    conn.commit()
    return f"Note added to {period}: '{note_text}'"


def try_relog(conn, s, text, user):
    """If text is a relog command, mark original and prompt for reason."""
    m = RELOG_RE.match(text)
    if not m:
        return None
    original = m.group(2).strip()
    job_no = parse_job_number(original)
    if not job_no:
        return ("You must specify the job number to relog. "
                "Example: 'relog job WO-2026-024 hour 5, 25000 units'")
    job = conn.execute("SELECT * FROM jobs WHERE job_number=?", (job_no,)).fetchone()
    if not job:
        return f"No job found for '{job_no}'."
    hour = parse_hour(original)
    if hour is None:
        return "Which hour are you relogging?"
    period = f"H{hour}"
    old = conn.execute(
        "SELECT id, units_filled FROM hourly_runs WHERE job_id=? AND period=? "
        "AND (superseded IS NULL OR superseded=0) ORDER BY id DESC LIMIT 1",
        (job['id'], period)).fetchone()
    if not old:
        return f"No existing {period} entry found to relog."
    conn.execute("UPDATE hourly_runs SET superseded=1 WHERE id=?", (old['id'],))
    conn.commit()
    s.set('state', 'awaiting_relog_reason')
    s.set('pending_text', original)
    s.set('pending_job_id', job['id'])
    s.save()
    return (f"Found original {period} entry ({old['units_filled']:,} units). "
            f"Marked superseded. What is the reason for this correction?")


def cont_relog_reason(conn, s, text, user):
    reason = (text or '').strip()
    if not reason:
        return "Please provide a reason for the correction."
    pending = s.get('pending_text')
    if not pending:
        s.set('state', 'idle')
        s.save()
        return "Session lost. Nothing was saved."

    s.set('state', 'idle')
    s.set('override_reason', reason)
    s.save()

    log_text = pending
    if not log_text.lower().startswith('running'):
        log_text = 'running ' + log_text

    reply = production.h_running_job(conn, s, log_text, user)

    s.set('override_reason', None)
    s.save()
    return f"Correction saved. Reason: {reason}\n\n{reply}"
