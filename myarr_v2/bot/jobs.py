"""bot/jobs.py — Job lifecycle: start, end, pause, resume, variance.

TEMPORARY BRIDGE: resolve_job, _explain_no_job, _fuzzy_note, next_job_hour,
and cont_end_minutes are imported from bot_v2. They will be extracted into
bot/resolve.py in a follow-up session. Reason: fuzzy voice-to-text job
matching is non-trivial and duplicating it today risks re-introducing the
bugs we are eliminating. Extraction is a small, safe task for a fresh
session.

The handlers in this module are new and use bot/db.py for all state.
"""
import re
from datetime import datetime, timedelta

from . import db
from parsers import parse_job_number, parse_all_job_numbers, parse_int

from .resolve import resolve_job, _explain_no_job, _fuzzy_note, next_job_hour


def h_start_job(conn, s, text, user):
    job_no = parse_job_number(text)
    job, conf, alts = resolve_job(conn, job_no)
    if not job:
        return _explain_no_job(conn, job_no or text, conf, alts)

    if s.get('active_job_id') and s['active_job_id'] != job['id']:
        active = conn.execute(
            "SELECT job_number FROM jobs WHERE id=?", (s['active_job_id'],)).fetchone()
        if active:
            return f"You have {active['job_number']} active. End or pause it first."

    # Strict line enforcement: refuse if the line is running something else.
    active_line = conn.execute("""
        SELECT j.job_number, le.state FROM jobs j
        JOIN line_events le ON le.job_id = j.id
        WHERE j.line_id = ? AND le.ended_at IS NULL AND j.id != ?
    """, (job['line_id'], job['id'])).fetchone()
    if active_line:
        return (
            f"Line {job['line_id']} is currently running "
            f"{active_line['job_number']} ({active_line['state']}). "
            f"You must complete a changeover before starting {job['job_number']}."
        )

    conn.execute("UPDATE jobs SET status='running', actual_end=NULL WHERE id=?",
                 (job['id'],))
    conn.commit()

    s.set('pending_job_id', job['id'])
    s.set('line_id', job['line_id'])
    s.set('state', 'awaiting_start_minutes')
    s.save()

    note = _fuzzy_note(job_no, conf, job)
    return f"Starting {job['job_number']}{note}. Minutes into the current hour when it started?"


def cont_start_minutes(conn, s, text, user):
    mins = parse_int(text)
    if mins is None:
        return "Just a number, please. Minutes into hour?"

    job_id = s.get('pending_job_id')
    job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        s.set('state', 'idle')
        s.set('pending_job_id', None)
        s.save()
        return "Job lost. Please start over."
    job = dict(job)

    conn.execute(
        "UPDATE jobs SET status='running', actual_end=NULL, "
        "actual_start=COALESCE(actual_start, ?) WHERE id=?",
        (datetime.now().isoformat(), job_id))
    conn.commit()

    line_id = db.derive_line(conn, job, s, user)
    db.transition_line(conn, line_id, 'production', job_id=job_id,
                       user_id=user['id'] if user else None)

    s.set('active_job_id', job_id)
    s.set('pending_job_id', None)
    s.set('state', 'idle')
    s.set('start_offset', float(mins))
    s.save()

    return (f"Started {job['job_number']} at +{mins} min into the hour. "
            f"Log the first hour when ready.")


def h_ending_job(conn, s, text, user):
    jobs_found = parse_all_job_numbers(text)
    ending_no = jobs_found[0] if jobs_found else None
    target_no = jobs_found[1] if len(jobs_found) > 1 else None

    if ending_no:
        job, conf, alts = resolve_job(conn, ending_no)
        if not job:
            return _explain_no_job(conn, ending_no, conf, alts)
    elif s.get('active_job_id'):
        r = conn.execute("SELECT * FROM jobs WHERE id=?",
                         (s['active_job_id'],)).fetchone()
        job = dict(r) if r else None
        conf = 'exact'
    else:
        return "Which job is ending? Say: 'end WO-2026-001'."
    if not job:
        return "Job not found."

    # Variance gate: refuse to close without a reason outside tolerance.
    if not job.get('completion_variance_reason'):
        actual = conn.execute(
            "SELECT SUM(units_filled) FROM hourly_runs WHERE job_id=? "
            "AND (superseded IS NULL OR superseded=0)",
            (job['id'],)).fetchone()[0] or 0
        target = job['target_quantity'] or 0
        if target > 0:
            var_pct = (actual - target) / target
            tol_row = conn.execute(
                "SELECT value FROM settings WHERE key='job_variance_tolerance'").fetchone()
            tol = float(tol_row['value']) if tol_row else 0.05
            if abs(var_pct) > tol:
                s.set('state', 'awaiting_variance_reason')
                s.set('pending_job_id', job['id'])
                s.set('pending_target_job_id', None)
                s.save()
                return (f"Job {job['job_number']} is off target by "
                        f"{var_pct*100:+.1f}%. Please provide a reason to close.")

    line_id = db.derive_line(conn, job, s, user)
    cur = db.current_line_event(conn, line_id)
    if cur and cur['state'] != 'production':
        return (f"Line {line_id} is in {cur['state'].upper()}, not production. "
                f"End that state first.")

    target_id = None
    if target_no:
        tj, tconf, talts = resolve_job(conn, target_no)
        if not tj:
            return _explain_no_job(conn, target_no, tconf, talts)
        target_id = tj['id']

    s.set('pending_job_id', job['id'])
    s.set('pending_target_job_id', target_id)
    s.set('state', 'awaiting_end_minutes')
    s.save()

    note = _fuzzy_note(ending_no, conf, job)
    return (f"Ending {job['job_number']}{note}. Minutes into the current hour "
            f"so far? (say 0 if at the top)")


def cont_end_minutes(conn, s, text, user):
    mins = parse_int(text)
    if mins is None:
        return "Just a number, please. Minutes into the hour?"

    job_id = s.get('pending_job_id')
    target_id = s.get('pending_target_job_id')
    job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        s.set('state', 'idle')
        s.set('pending_job_id', None)
        s.set('pending_target_job_id', None)
        s.save()
        return "Job lost. Nothing was closed."

    job = dict(job)
    now = datetime.now()
    hour_start = now.replace(minute=0, second=0, microsecond=0)
    end_iso = (hour_start + timedelta(minutes=mins)).isoformat()

    conn.execute(
        "UPDATE jobs SET status='completed', actual_end=? WHERE id=?",
        (end_iso, job_id))
    conn.commit()

    line_id = db.derive_line(conn, job, s, user)
    db.transition_line(conn, line_id, 'idle',
                       user_id=user['id'] if user else None)

    s.set('pending_job_id', None)
    s.set('state', 'idle')
    s.save()

    base = f"{job['job_number']} ended at +{mins} min."
    if target_id:
        tj = conn.execute("SELECT job_number FROM jobs WHERE id=?",
                          (target_id,)).fetchone()
        if tj:
            return (f"{base} Next: say 'changeover job {job['job_number']} "
                    f"to {tj['job_number']}' to start the changeover.")
    return base + " Line now idle."


def h_pause_job(conn, s, text, user):
    job_no = parse_job_number(text)
    if job_no:
        job, conf, alts = resolve_job(conn, job_no)
        if not job:
            return _explain_no_job(conn, job_no, conf, alts)
    elif s.get('active_job_id'):
        r = conn.execute("SELECT * FROM jobs WHERE id=?",
                         (s['active_job_id'],)).fetchone()
        job = dict(r) if r else None
        conf = 'exact'
    else:
        return "Which job to pause?"
    if not job:
        return "Job not found."
    if job.get('status') != 'running':
        return f"{job['job_number']} is not running (status: {job.get('status') or 'unknown'})."

    conn.execute("UPDATE jobs SET status='paused' WHERE id=?", (job['id'],))
    conn.commit()

    line_id = db.derive_line(conn, job, s, user)
    db.transition_line(conn, line_id, 'idle',
                       reason=f"paused {job['job_number']}",
                       user_id=user['id'] if user else None)

    s.set('active_job_id', None)
    s.save()
    return (f"{job['job_number']} paused. Line {line_id} now IDLE. "
            f"Resume with 'resume {job['job_number']}'.")


def h_resume_job(conn, s, text, user):
    job_no = parse_job_number(text)
    job, conf, alts = resolve_job(conn, job_no)
    if not job:
        return _explain_no_job(conn, job_no or text, conf, alts)
    if job.get('status') not in ('paused', 'completed'):
        return (f"{job['job_number']} is not paused or completed "
                f"(status: {job.get('status') or 'unknown'}).")

    conn.execute("UPDATE jobs SET status='running', actual_end=NULL WHERE id=?",
                 (job['id'],))
    conn.commit()

    line_id = db.derive_line(conn, job, s, user)
    db.transition_line(conn, line_id, 'production', job_id=job['id'],
                       user_id=user['id'] if user else None)

    s.set('active_job_id', job['id'])
    s.set('shift', None)
    s.set('shift_hour', None)
    s.save()

    note = _fuzzy_note(job_no, conf, job)
    jh = next_job_hour(conn, job['id'])
    return f"{job['job_number']}{note} resumed. Job-hour continues at {jh:.1f}."


def cont_variance_reason(conn, s, text, user):
    reason = (text or '').strip()
    if not reason:
        return "Please provide a reason to close the job."

    job_id = s.get('pending_job_id')
    if not job_id:
        s.set('state', 'idle')
        s.save()
        return "Session lost track of the job. Please try 'end WO-...' again."

    conn.execute(
        "UPDATE jobs SET completion_variance_reason=?, completion_flagged=1 WHERE id=?",
        (reason, job_id))
    conn.commit()

    job_row = conn.execute("SELECT job_number FROM jobs WHERE id=?", (job_id,)).fetchone()
    job_no = job_row['job_number'] if job_row else None

    s.set('state', 'idle')
    s.set('pending_job_id', None)
    s.save()

    if not job_no:
        return "Job closed and flagged. Please run 'status line N' to confirm."
    return h_ending_job(conn, s, f"end {job_no}", user)
