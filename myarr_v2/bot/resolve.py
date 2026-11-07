"""bot/resolve.py — Job resolution, fuzzy matching, and job-hour calculation.

Extracted from bot_v2.py on 2026-11-07 as part of the modular rewrite.
These functions handle the messy work of matching voice-to-text job numbers
to real jobs, explaining failures to the operator, and computing the next
job-hour counter.
"""
import re
from datetime import datetime, timedelta
from parsers import (parse_job_number, parse_all_job_numbers, parse_hour,
                     parse_line_number, parse_bottles, parse_downtime,
                     parse_int, parse_float)

def resolve_job(conn, job_number):
    if not job_number:
        return None, 'none', _active_jobs(conn)
    r = conn.execute("SELECT * FROM jobs WHERE job_number=?", (job_number,)).fetchone()
    if r:
        return dict(r), 'exact', []
    m = re.search(r'(\d{3})$', job_number)
    if not m:
        return None, 'none', _active_jobs(conn)
    last3 = m.group(1)
    candidates = conn.execute(
        "SELECT * FROM jobs WHERE job_number LIKE ?", (f'%{last3}',)
    ).fetchall()
    if not candidates:
        return None, 'none', _active_jobs(conn)
    if len(candidates) == 1:
        return dict(candidates[0]), 'fuzzy', []
    scored = sorted(
        [(difflib.SequenceMatcher(None, job_number, c['job_number']).ratio(), c) for c in candidates],
        key=lambda x: -x[0]
    )
    if scored[0][0] >= FUZZY_THRESHOLD:
        return dict(scored[0][1]), 'fuzzy', []
    return None, 'ambiguous', [dict(c) for _, c in scored[:3]]


def _explain_no_job(conn, input_str, status, alts):
    if status == 'ambiguous':
        lines = [f"No exact match for '{input_str}'."]
        lines.append("Did you mean one of these?")
        for a in alts:
            lines.append(f"  {a['job_number']} ({a.get('status', 'unknown')})")
        return "\n".join(lines)
    if not alts:
        alts = _active_jobs(conn)
    if not alts:
        return f"No job found for '{input_str}'. No jobs are active."
    lines = [f"No job found for '{input_str}'. Active jobs:"]
    for a in alts:
        lines.append(f"  {a['job_number']} ({a.get('status', 'unknown')})")
    return "\n".join(lines)


def _fuzzy_note(job_no, conf, job):
    if conf == 'fuzzy' and job_no and job_no != job['job_number']:
        return f" (interpreting '{job_no}' as {job['job_number']})"
    return ""


def next_job_hour(conn, job_id):
    r = conn.execute("SELECT MAX(job_hour_end) AS m FROM hourly_runs WHERE job_id=?", (job_id,)).fetchone()
    return r['m'] if r and r['m'] is not None else 0.0


def ideal_rate(conn, line_id, sku_id):
    r = conn.execute("SELECT ideal_rate FROM line_sku_rates WHERE line_id=? AND sku_id=?",
                     (line_id, sku_id)).fetchone()
    return r['ideal_rate'] if r else 600.0


def check_plausibility(units, expected, force=False):
    if force: return True, ""
    if expected <= 0: return True, ""
    if units < expected * PLAUSIBILITY_LOW:
        return False, (f"{units:,} is far below the ~{expected:,.0f} expected. "
                       f"Re-say the full number, or prefix with 'confirm' to accept.")
    if units > expected * PLAUSIBILITY_HIGH:
        return False, (f"{units:,} exceeds the ~{expected:,.0f} line capacity. "
                       f"Re-say the full number, or prefix with 'confirm' to accept.")
    return True, ""


