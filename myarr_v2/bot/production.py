"""bot/production.py — Hourly production logging with scrap capture.

Agreed 2026-11-07: "600 parts, 20 scrap" means 600 total, 20 bad, 580 good.
    units_filled = total produced
    scrap_units = the bad subset
    FTQ = (units_filled - scrap_units) / units_filled * 100

Both entry paths pass scrap_units to db.write_hour.
"""
import re

from . import db
from .shift import current_shift_code
from parsers import parse_job_number, parse_hour, parse_bottles, parse_downtime

PLAUSIBILITY_LOW = 0.50
PLAUSIBILITY_HIGH = 1.10


def check_plausibility(units, expected, force=False):
    if force:
        return True, None
    if expected <= 0:
        return True, None
    ratio = units / expected
    if ratio < PLAUSIBILITY_LOW or ratio > PLAUSIBILITY_HIGH:
        pct = int(ratio * 100)
        verb = 'below' if ratio < 1 else 'above'
        return False, (
            f"{units:,} is far {verb} the ~{int(expected):,} expected "
            f"({pct}%). Re-say the full number, or prefix with 'confirm' to accept."
        )
    return True, None


def _resolve_job(conn, job_no):
    if not job_no:
        return None
    r = conn.execute("SELECT * FROM jobs WHERE job_number=?", (job_no,)).fetchone()
    return dict(r) if r else None


def _next_job_hour(conn, job_id):
    r = conn.execute(
        "SELECT MAX(job_hour_end) AS m FROM hourly_runs WHERE job_id=?",
        (job_id,)).fetchone()
    return (r['m'] or 0.0) if r else 0.0


def _summarize(conn, job, hour, units, scrap, duration, jh_start, jh_end, gap):
    cp = db.case_pack(conn, job['sku_id'])
    cases = db.case_count(units, cp)
    ul = db.unit_label(conn)
    cl = db.case_label(conn)
    scrap_bit = f", {scrap:,} scrap" if scrap else ""
    return (
        f"Logged: {job['job_number']} H{hour}, {cases:,} {cl} "
        f"({units:,} {ul}{scrap_bit}), {duration:.0f} min. "
        f"Job-hours {jh_start:.1f}-{jh_end:.1f}. Gap {gap:.2f}m."
    )


def h_running_job(conn, s, text, user, force=False):
    job_no = parse_job_number(text)
    job = _resolve_job(conn, job_no)
    if not job:
        return f"No job found for '{job_no or text}'."

    if s.get('active_job_id') and s['active_job_id'] != job['id']:
        active = conn.execute(
            "SELECT job_number FROM jobs WHERE id=?", (s['active_job_id'],)).fetchone()
        if active:
            return f"You have {active['job_number']} active. End or pause it first."

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

    hour = parse_hour(text)
    if hour is None:
        s.set('state', 'awaiting_hour')
        s.set('pending_text', text)
        s.save()
        return "Which hour? Say just the number (for example: 5)."

    units = parse_bottles(text)
    if units is None:
        return "How many units?"

    scrap = db.parse_scrap(text)
    dts = parse_downtime(text)
    duration = 60.0 - (s.get('start_offset') or 0.0)

    rate = db.ideal_rate(conn, job['line_id'], job['sku_id'])
    expected = rate * duration / 60.0
    ok, reason = check_plausibility(units, expected, force=force)
    if not ok:
        return reason

    if job.get('status') != 'running':
        conn.execute("UPDATE jobs SET status='running' WHERE id=?", (job['id'],))
        conn.commit()

    line_id = db.derive_line(conn, job, s, user)
    db.transition_line(conn, line_id, 'production', job_id=job['id'],
                       user_id=user['id'] if user else None)

    jh_start = _next_job_hour(conn, job['id'])
    jh_end = jh_start + duration / 60.0
    gap = (expected - units) / (rate / 60.0) if rate else 0.0
    shift = s.get('shift') or current_shift_code()

    db.write_hour(
        conn, job, shift, f"H{hour}", units, duration,
        user['id'] if user else None, text, jh_start, jh_end, gap, dts,
        scrap_units=scrap, override_reason=s.get('override_reason'),
    )

    s.set('active_job_id', job['id'])
    s.set('shift', shift)
    s.set('shift_hour', hour + 1)
    s.save()

    return _summarize(conn, job, hour, units, scrap, duration, jh_start, jh_end, gap)


def h_record_hour(conn, s, text, user, force=False):
    job_no = parse_job_number(text)
    if job_no:
        job = _resolve_job(conn, job_no)
        if not job:
            return f"No job found for '{job_no}'."
    elif s.get('active_job_id'):
        r = conn.execute(
            "SELECT job_number FROM jobs WHERE id=?", (s['active_job_id'],)).fetchone()
        job = _resolve_job(conn, r['job_number']) if r else None
    else:
        return "Which job? Say: 'record production hour 5, 60 minutes, 7000 units for WO-2026-001'."
    if not job:
        return "Job not found."

    hour = parse_hour(text)
    if hour is None:
        return "Which hour?"

    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:min|minutes?)', text, re.IGNORECASE)
    if not m:
        return "How many minutes?"
    mins = float(m.group(1))

    units = parse_bottles(text)
    if units is None:
        return "How many units?"

    scrap = db.parse_scrap(text)

    rate = db.ideal_rate(conn, job['line_id'], job['sku_id'])
    expected = rate * mins / 60.0
    ok, reason = check_plausibility(units, expected, force=force)
    if not ok:
        return reason

    if job.get('status') != 'running':
        conn.execute("UPDATE jobs SET status='running' WHERE id=?", (job['id'],))
        conn.commit()

    line_id = db.derive_line(conn, job, s, user)
    db.transition_line(conn, line_id, 'production', job_id=job['id'],
                       user_id=user['id'] if user else None)

    jh_start = _next_job_hour(conn, job['id'])
    jh_end = jh_start + mins / 60.0
    gap = (expected - units) / (rate / 60.0) if rate else 0.0
    shift = s.get('shift') or current_shift_code()

    db.write_hour(
        conn, job, shift, f"H{hour}", units, mins,
        user['id'] if user else None, text, jh_start, jh_end, gap, [],
        scrap_units=scrap, override_reason=s.get('override_reason'),
    )

    s.set('active_job_id', job['id'])
    s.set('shift', shift)
    s.set('shift_hour', hour + 1)
    s.save()

    return _summarize(conn, job, hour, units, scrap, mins, jh_start, jh_end, gap)
