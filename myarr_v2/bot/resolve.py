# bot/resolve.py
# Job resolution, fuzzy matching, and job-hour calculation.
# Agreed 2026-11-13: restored from bot_v2.py at commit ec65562^.
# The 2026-11-07 modular extraction dropped difflib, FUZZY_THRESHOLD,
# PLAUSIBILITY_LOW, PLAUSIBILITY_HIGH, and _active_jobs. Any non-exact
# job number raised NameError in four lifecycle commands.
import difflib
import re

FUZZY_THRESHOLD = 0.90
PLAUSIBILITY_LOW = 0.50
PLAUSIBILITY_HIGH = 1.10

def _active_jobs(conn):
    rows = conn.execute(
        'SELECT job_number, status FROM jobs '
        "WHERE status IN ('running', 'scheduled') ORDER BY id DESC LIMIT 5"
    ).fetchall()
    return [dict(r) for r in rows]

def resolve_job(conn, job_number):
    if not job_number:
        return None, 'none', _active_jobs(conn)
    r = conn.execute('SELECT * FROM jobs WHERE job_number=?', (job_number,)).fetchone()
    if r:
        return dict(r), 'exact', []
    m = re.search(r'(\d{3})$', job_number)
    if not m:
        return None, 'none', _active_jobs(conn)
    last3 = m.group(1)
    candidates = conn.execute(
        'SELECT * FROM jobs WHERE job_number LIKE ?', ('%' + last3,)
    ).fetchall()
    if not candidates:
        return None, 'none', _active_jobs(conn)
    if len(candidates) == 1:
        return dict(candidates[0]), 'fuzzy', []
    scored = sorted(
        [(difflib.SequenceMatcher(None, job_number, c['job_number']).ratio(), c)
         for c in candidates],
        key=lambda x: -x[0])
    if scored[0][0] >= FUZZY_THRESHOLD:
        return dict(scored[0][1]), 'fuzzy', []
    return None, 'ambiguous', [dict(c) for _, c in scored[:3]]

def _explain_no_job(conn, input_str, status, alts):
    if status == 'ambiguous':
        lines = ['No exact match for ' + repr(input_str) + '.']
        lines.append('Did you mean one of these?')
        for a in alts:
            lines.append('  ' + a['job_number'] + ' (' + str(a.get('status', 'unknown')) + ')')
        return chr(10).join(lines)
    if not alts:
        alts = _active_jobs(conn)
    if not alts:
        return 'No job found for ' + repr(input_str) + '. No jobs are active.'
    lines = ['No job found for ' + repr(input_str) + '. Active jobs:']
    for a in alts:
        lines.append('  ' + a['job_number'] + ' (' + str(a.get('status', 'unknown')) + ')')
    return chr(10).join(lines)

def _fuzzy_note(job_no, conf, job):
    if conf == 'fuzzy' and job_no and job_no != job['job_number']:
        return ' (interpreting ' + repr(job_no) + ' as ' + job['job_number'] + ')'
    return ''

def next_job_hour(conn, job_id):
    r = conn.execute('SELECT MAX(job_hour_end) AS m FROM hourly_runs WHERE job_id=?',
                     (job_id,)).fetchone()
    return r['m'] if r and r['m'] is not None else 0.0

def ideal_rate(conn, line_id, sku_id):
    r = conn.execute('SELECT ideal_rate FROM line_sku_rates WHERE line_id=? AND sku_id=?',
                     (line_id, sku_id)).fetchone()
    return r['ideal_rate'] if r else 600.0

def check_plausibility(units, expected, force=False):
    if force:
        return True, ''
    if expected <= 0:
        return True, ''
    if units < expected * PLAUSIBILITY_LOW:
        return False, (str(units) + ' is far below the ~' + str(int(expected))
                       + ' expected. Re-say the full number, or prefix with confirm to accept.')
    if units > expected * PLAUSIBILITY_HIGH:
        return False, (str(units) + ' exceeds the ~' + str(int(expected))
                       + ' line capacity. Re-say the full number, or prefix with confirm to accept.')
    return True, ''
