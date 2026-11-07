"""bot/handover.py — Shift handover and takeover.

Two commands:
    handover job WO-XXXX-XXX    — the outgoing operator records notes
    taking over job WO-XXXX-XXX — the incoming operator reads them

Handover notes are stored in two places for compatibility:
    jobs.handover_notes         (legacy, overwritten each time)
    shift_handovers             (history, append-only)
"""
import re
from datetime import datetime

from . import db
from parsers import parse_job_number


def _resolve_job(conn, job_no):
    r = conn.execute("SELECT * FROM jobs WHERE job_number=?", (job_no,)).fetchone()
    return dict(r) if r else None


def h_handover(conn, s, text, user):
    job_no = parse_job_number(text)
    if job_no:
        job = _resolve_job(conn, job_no)
        if not job:
            return f"No job found for '{job_no}'."
    elif s.get('active_job_id'):
        r = conn.execute("SELECT job_number FROM jobs WHERE id=?",
                         (s['active_job_id'],)).fetchone()
        job = _resolve_job(conn, r['job_number']) if r else None
    else:
        return "Which job? Say: 'handover job WO-2026-001'."
    if not job:
        return "Job not found."

    s.set('pending_job_id', job['id'])
    s.set('state', 'awaiting_handover_notes')
    s.save()
    return f"What are the handover notes for {job['job_number']}?"


def cont_handover_notes(conn, s, text, user):
    notes = (text or '').strip()
    if not notes:
        return "Please provide the notes, or say 'cancel'."
    if notes.lower() in ('cancel', 'stop', 'quit'):
        s.set('state', 'idle')
        s.set('pending_job_id', None)
        s.save()
        return "Handover cancelled."

    job_id = s.get('pending_job_id')
    if not job_id:
        s.set('state', 'idle')
        s.save()
        return "Handover lost. Please start over."

    job_row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not job_row:
        s.set('state', 'idle')
        s.set('pending_job_id', None)
        s.save()
        return "Job not found."

    line_id = job_row['line_id']
    from_uid = user['id'] if user else None
    now = datetime.now().isoformat()

    conn.execute("UPDATE jobs SET handover_notes=? WHERE id=?", (notes, job_id))
    conn.execute(
        "INSERT INTO shift_handovers (job_id, line_id, from_user_id, notes, created_at) "
        "VALUES (?,?,?,?,?)",
        (job_id, line_id, from_uid, notes, now))
    conn.commit()

    s.set('pending_job_id', None)
    s.set('state', 'idle')
    s.save()

    return (
        f"Handover noted for {job_row['job_number']}. "
        f"Incoming operator can say 'taking over job {job_row['job_number']}' to see it."
    )


def h_takeover(conn, s, text, user):
    job_no = parse_job_number(text)
    if job_no:
        job = _resolve_job(conn, job_no)
        if not job:
            return f"No job found for '{job_no}'."
    elif s.get('active_job_id'):
        r = conn.execute("SELECT job_number FROM jobs WHERE id=?",
                         (s['active_job_id'],)).fetchone()
        job = _resolve_job(conn, r['job_number']) if r else None
    else:
        return "Which job are you taking over? Say: 'taking over job WO-2026-001'."
    if not job:
        return "Job not found."

    open_h = conn.execute(
        "SELECT * FROM shift_handovers WHERE job_id=? AND taken_at IS NULL "
        "ORDER BY created_at DESC LIMIT 1",
        (job['id'],)).fetchone()

    handover_notes = job.get('handover_notes') or 'none'

    if open_h:
        now = datetime.now().isoformat()
        to_uid = user['id'] if user else None
        conn.execute(
            "UPDATE shift_handovers SET to_user_id=?, taken_at=? WHERE id=?",
            (to_uid, now, open_h['id']))
        conn.commit()
        handover_notes = open_h['notes'] or 'none'

    s.set('active_job_id', job['id'])
    s.set('line_id', job['line_id'])
    s.set('state', 'idle')
    s.save()

    db.transition_line(conn, job['line_id'], 'production', job_id=job['id'],
                       user_id=user['id'] if user else None)

    return (
        f"Taking over {job['job_number']}. Line {job['line_id']} back in production.\n"
        f"Handover notes: {handover_notes}"
    )
