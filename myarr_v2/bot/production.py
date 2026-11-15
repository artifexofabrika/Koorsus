"""bot/production.py - Hourly production logging with scrap capture.

Whole-file rewrite 2026-11-15. Moves the plausibility check to units entry
and adds a retry state so a corrected number returns to the flow.

Agreed 2026-11-07: "600 parts, 20 scrap" means 600 total, 20 bad, 580 good.
    units_filled = total produced
    scrap_units = the bad subset
    FTQ = (units_filled - scrap_units) / units_filled * 100

Agreed 2026-11-13: conversational record flow.
    record H5 -> prompts for minutes, units, scrap, and (if gap > 1 min)
    downtime. Each prompt accepts skip where the philosophy permits.
    One-shot form still works: record H5, 60 min, 9048 units, 72 scrap.

Agreed 2026-11-15: plausibility fires at units entry, not after scrap.
    Awaiting_record_plausibility accepts a corrected number or the word
    confirm. The pending state carries everything so the flow resumes
    without losing the operator's work.

PENDING FIELDS (bot_sessions.pending_text, JSON):
    job_number     str   resolved job
    hour           int   1-12
    minutes        float 1-60
    units          int   total produced
    scrap          int   bad subset
    dts            list  parsed downtime events (may be empty)
    downtime_text  str   raw text of a downtime answer
    downtime_asked bool  we already asked for downtime this flow
    confirmed      bool  operator confirmed an implausible number
"""
import json
import re

from . import db
from .shift import current_shift_code
from parsers import parse_job_number, parse_hour, parse_bottles, parse_downtime

PLAUSIBILITY_LOW = 0.50
PLAUSIBILITY_HIGH = 1.10

WORD_NUMBERS = {
    'zero': 0, 'one': 1, 'two': 2, 'to': 2, 'too': 2, 'three': 3,
    'four': 4, 'for': 4, 'five': 5, 'six': 6, 'seven': 7,
    'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12,
}


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
            f"({pct}%). Re-say the full number, or say 'confirm' to accept."
        )
    return True, None


def _resolve_job(conn, job_no):
    if not job_no:
        return None
    r = conn.execute("SELECT * FROM jobs WHERE job_number=?", (job_no,)).fetchone()
    return dict(r) if r else None


def _resolve_from_spine(conn, s, user, text=''):
    line_id = None
    try:
        from parsers import parse_line_number as _pln
        line_id = _pln(text or '')
    except Exception:
        line_id = None
    if line_id is None:
        line_id = s.get('line_id') or (user.get('line_id') if user else None)
    if not line_id:
        return None
    if not s.get('line_id'):
        s.set('line_id', line_id)
    cur = db.current_line_event(conn, line_id)
    if not cur:
        return None
    if cur['state'] == 'production' and cur['job_id']:
        jr = conn.execute("SELECT job_number FROM jobs WHERE id=?", (cur['job_id'],)).fetchone()
        return _resolve_job(conn, jr['job_number']) if jr else None
    return None


def _next_job_hour(conn, job_id):
    r = conn.execute(
        "SELECT COALESCE(MAX(job_hour_end), "
        "(SELECT SUM(duration_min) FROM hourly_runs WHERE job_id=?)/60.0, 0.0) AS m "
        "FROM hourly_runs WHERE job_id=?",
        (job_id, job_id)).fetchone()
    return float(r['m']) if r and r['m'] is not None else 0.0


def _load_pending(s):
    raw = s.get('pending_text')
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _save_pending(s, d):
    s.set('pending_text', json.dumps(d))


def _safe_int(t):
    m = re.search(r'(\d+)', t or '')
    return int(m.group(1)) if m else None


def _parse_small_number(text):
    t = (text or '').strip().lower()
    m = re.search(r'(\d+)', t)
    if m:
        return int(m.group(1))
    for tok in re.findall(r'[a-z]+', t):
        if tok in WORD_NUMBERS:
            return WORD_NUMBERS[tok]
    return None


def _summarize(conn, job, hour, units, scrap, duration, jh_start, jh_end, gap,
               user=None, dts=None, rate=None):
    if rate is None:
        rate = db.ideal_rate(conn, job['line_id'], job['sku_id'])
    if dts is None:
        dts = []
    cp = db.case_pack(conn, job['sku_id'])
    cases = db.case_count(units, cp)
    ul = db.unit_label(conn)
    cl = db.case_label(conn)
    scrap_bit = f", {scrap:,} scrap" if scrap else ""
    expected_units = rate * duration / 60.0
    gap_units = expected_units - units
    downtime_min = sum((d or {}).get('minutes', 0) for d in dts)
    downtime_units = downtime_min * rate / 60.0
    unaccounted_units = max(0.0, gap_units - downtime_units)
    unaccounted_min = unaccounted_units / (rate / 60.0) if rate else 0.0
    ftq = ((units - scrap) / units * 100) if units else 0.0
    parts = [
        f"Recorded: {job['job_number']} H{hour}, {cases:,} {cl} "
        f"({units:,} {ul}{scrap_bit}), {duration:.0f} min.",
        f"Expected {expected_units:,.0f} at {rate:,.0f}/hr. "
        f"Gap: {gap_units:,.0f} units ({gap:.1f} min).",
    ]
    if downtime_min > 0:
        parts.append(f"Downtime: {downtime_min:.1f} min ({downtime_units:,.0f} units).")
    if unaccounted_units > 0:
        parts.append(f"Unaccounted: {unaccounted_units:,.0f} units "
                     f"({unaccounted_min:.1f} min).")
    parts.append(f"Job-hours {jh_start:.1f}-{jh_end:.1f}. FTQ {ftq:.1f}%.")
    reply = ' '.join(parts)
    if user and user.get('line_id') and user['line_id'] != job['line_id']:
        reply += (f" (Logged against Line {job['line_id']}; "
                  f"you are assigned to Line {user['line_id']}.)")
    return reply


def _write_record(conn, s, job, hour, mins, units, scrap, dts, gap_min, user, raw_text):
    if job.get('status') != 'running':
        conn.execute("UPDATE jobs SET status='running' WHERE id=?", (job['id'],))
        conn.commit()
    line_id = db.derive_line(conn, job, s, user)
    db.transition_line(conn, line_id, 'production', job_id=job['id'],
                       user_id=user['id'] if user else None)
    jh_start = _next_job_hour(conn, job['id'])
    jh_end = jh_start + mins / 60.0
    shift = s.get('shift') or current_shift_code()
    rate = db.ideal_rate(conn, job['line_id'], job['sku_id'])
    db.write_hour(conn, job, shift, "H" + str(hour), units, mins,
                  user['id'] if user else None, raw_text, jh_start, jh_end,
                  gap_min, dts, scrap_units=scrap,
                  override_reason=s.get('override_reason'))
    s.set('active_job_id', job['id'])
    s.set('shift', shift)
    s.set('shift_hour', hour + 1)
    s.set('pending_text', None)
    s.set('state', 'idle')
    s.save()
    return _summarize(conn, job, hour, units, scrap, mins, jh_start, jh_end,
                      gap_min, user=user, dts=dts, rate=rate)


def h_running_job(conn, s, text, user, force=False):
    """One-shot command: 'running WO-X, hour N, units [, downtime]'."""
    job_no = parse_job_number(text)
    job = _resolve_job(conn, job_no)
    if not job and s.get('active_job_id'):
        _r = conn.execute("SELECT job_number FROM jobs WHERE id=?",
                          (s['active_job_id'],)).fetchone()
        job = _resolve_job(conn, _r['job_number']) if _r else None
    if not job:
        job = _resolve_from_spine(conn, s, user, text)
    if not job:
        return f"No job found for '{job_no or text}'."

    _status = (job.get('status') or '').lower()
    if _status == 'completed':
        return job['job_number'] + ' is completed. It cannot receive new production.'
    if _status == 'paused':
        return (job['job_number'] + ' is paused. Say resume '
                + job['job_number'] + ' before logging production.')

    active_line = conn.execute(
        "SELECT j.job_number, le.state FROM jobs j "
        "JOIN line_events le ON le.job_id = j.id "
        "WHERE j.line_id = ? AND le.ended_at IS NULL AND j.id != ?",
        (job['line_id'], job['id'])).fetchone()
    if active_line:
        return (f"Line {job['line_id']} is currently running "
                f"{active_line['job_number']} ({active_line['state']}). "
                f"You must complete a changeover before starting {job['job_number']}.")

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
        _save_pending(s, {
            'job_number': job['job_number'],
            'hour': hour,
            'minutes': duration,
            'units': units,
            'scrap': scrap,
            'dts': dts,
        })
        s.set('state', 'awaiting_record_plausibility')
        s.save()
        return reason

    gap_min = (expected - units) / (rate / 60.0) if rate else 0.0
    return _write_record(conn, s, job, hour, duration, units, scrap, dts,
                         gap_min, user, text)


def h_record_hour(conn, s, text, user, force=False, _is_continuation=False):
    """Conversational record flow. Accepts 'record H5' and prompts for the rest."""
    pending = _load_pending(s) if _is_continuation else {}
    if _is_continuation and not pending:
        s.set('state', 'idle')
        s.set('pending_text', None)
        s.save()
        return "Record session lost. Start over with record H5 ..."
    force = force or pending.get('confirmed', False)

    # 1. Resolve job
    job_no = parse_job_number(text)
    if job_no:
        job = _resolve_job(conn, job_no)
        if not job:
            return "No job found for " + repr(job_no)
        pending['job_number'] = job['job_number']
    elif pending.get('job_number'):
        job = _resolve_job(conn, pending['job_number'])
    elif s.get('active_job_id'):
        r = conn.execute("SELECT job_number FROM jobs WHERE id=?",
                         (s['active_job_id'],)).fetchone()
        job = _resolve_job(conn, r['job_number']) if r else None
        if job:
            pending['job_number'] = job['job_number']
    else:
        job = _resolve_from_spine(conn, s, user, text)
        if job:
            pending['job_number'] = job['job_number']
    if not job:
        return "Which job? Say: record WO-XXXX-XXX H5, 60 minutes, 7000 units, 20 scrap."

    _status = (job.get('status') or '').lower()
    if _status == 'completed':
        return job['job_number'] + ' is completed. It cannot receive new production.'
    if _status == 'paused':
        return (job['job_number'] + ' is paused. Say resume '
                + job['job_number'] + ' before logging production.')

    # 2. Resolve hour
    hour = parse_hour(text)
    if hour is None:
        hour = pending.get('hour')
    if hour is None:
        s.set('state', 'awaiting_record_hour')
        _save_pending(s, pending)
        s.save()
        return "Which hour? (e.g. H5 or hour 5)"
    pending['hour'] = hour

    # 3. Resolve minutes
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:min|minutes?)', text, re.IGNORECASE)
    mins = float(m.group(1)) if m else pending.get('minutes')
    if mins is None:
        s.set('state', 'awaiting_record_minutes')
        _save_pending(s, pending)
        s.save()
        return "Hour " + str(hour) + ": how many minutes?"
    if mins < 1 or mins > 60:
        return "Minutes must be between 1 and 60 for one hourly record. Try again."
    pending['minutes'] = mins

    # 4. Resolve units
    units = parse_bottles(text)
    if units is None:
        units = pending.get('units')
    if units is None:
        s.set('state', 'awaiting_record_units')
        _save_pending(s, pending)
        s.save()
        return f"Hour {hour} ({int(mins)} min): how many units produced?"
    pending['units'] = units

    # 5. Plausibility check AT UNITS ENTRY
    rate = db.ideal_rate(conn, job['line_id'], job['sku_id'])
    expected = rate * mins / 60.0
    ok, reason = check_plausibility(units, expected, force=force)
    if not ok:
        if 'dts' not in pending:
            pending['dts'] = parse_downtime(text)
        s.set('state', 'awaiting_record_plausibility')
        _save_pending(s, pending)
        s.save()
        return reason
    gap_min = (expected - units) / (rate / 60.0) if rate else 0.0

    # 6. Resolve scrap
    has_scrap_word = bool(re.search(r'\b(scrap|rework|reject|bad)\b', text, re.IGNORECASE))
    if has_scrap_word:
        scrap = db.parse_scrap(text)
    else:
        scrap = pending.get('scrap')
    if scrap is None:
        s.set('state', 'awaiting_record_scrap')
        _save_pending(s, pending)
        s.save()
        return (f"Hour {hour} ({int(mins)} min, {units} units): "
                f"scrap or rework? (say skip for none)")
    pending['scrap'] = scrap

    # 7. Resolve downtime
    dts = parse_downtime(text)
    if not dts and pending.get('dts'):
        dts = pending['dts']
    if not dts and pending.get('downtime_text'):
        dts = parse_downtime(pending['downtime_text'])
    if not dts and gap_min > 1.0 and not pending.get('downtime_asked'):
        pending['downtime_asked'] = True
        s.set('state', 'awaiting_record_downtime')
        _save_pending(s, pending)
        s.save()
        return (f"Hour {hour}: gap is {round(gap_min, 1)} min. "
                f"Any downtime to record? (e.g. 2 min filler jam, or skip)")

    # 8. Write
    return _write_record(conn, s, job, hour, mins, units, scrap, dts, gap_min,
                         user, text)


def _cont_record_hour(conn, s, text, user):
    pending = _load_pending(s)
    hour = parse_hour('hour ' + text) or _safe_int(text)
    if hour is None or hour < 1 or hour > 12:
        return "Just a number please (e.g. 5)."
    pending['hour'] = hour
    _save_pending(s, pending)
    s.set('state', 'idle')
    s.save()
    return h_record_hour(conn, s, '', user, _is_continuation=True)


def _cont_record_minutes(conn, s, text, user):
    pending = _load_pending(s)
    m = re.search(r'(\d+(?:\.\d+)?)', text or '')
    if not m:
        return "Just a number please (minutes)."
    _mins = float(m.group(1))
    if _mins < 1 or _mins > 60:
        return "Minutes must be between 1 and 60 for one hourly record. Try again."
    pending['minutes'] = _mins
    _save_pending(s, pending)
    s.set('state', 'idle')
    s.save()
    return h_record_hour(conn, s, '', user, _is_continuation=True)


def _cont_record_units(conn, s, text, user):
    pending = _load_pending(s)
    m = re.search(r'(\d[\d, ]*\d|\d)', text or '')
    if not m:
        return "How many units produced?"
    units = int(re.sub(r'[ ,]', '', m.group(1)))
    pending['units'] = units
    _save_pending(s, pending)
    s.set('state', 'idle')
    s.save()
    return h_record_hour(conn, s, '', user, _is_continuation=True)


def _cont_record_plausibility(conn, s, text, user):
    pending = _load_pending(s)
    low = (text or '').strip().lower()
    if low in ('confirm', 'confrim', 'conferm', 'confim', 'comfirm',
               'yes', 'y', 'yeah', 'yep', 'ok', 'okay'):
        pending['confirmed'] = True
        _save_pending(s, pending)
        s.set('state', 'idle')
        s.save()
        return h_record_hour(conn, s, '', user, force=True, _is_continuation=True)
    m = re.search(r'(\d[\d, ]*\d|\d)', text or '')
    if m:
        new_units = int(re.sub(r'[ ,]', '', m.group(1)))
        pending['units'] = new_units
        pending.pop('confirmed', None)
        _save_pending(s, pending)
        s.set('state', 'idle')
        s.save()
        return h_record_hour(conn, s, '', user, _is_continuation=True)
    return "Re-say the full number, or say 'confirm' to accept."


def _cont_record_scrap(conn, s, text, user):
    pending = _load_pending(s)
    low = (text or '').strip().lower()
    if low in ('skip', 'none', 'no', ''):
        pending['scrap'] = 0
    else:
        n = _parse_small_number(text)
        if n is None:
            return "Just a number please, or say skip."
        pending['scrap'] = n
    _save_pending(s, pending)
    s.set('state', 'idle')
    s.save()
    return h_record_hour(conn, s, '', user, _is_continuation=True)


def _cont_record_downtime(conn, s, text, user):
    pending = _load_pending(s)
    low = (text or '').strip().lower()
    if low in ('skip', 'none', ''):
        pending['downtime_text'] = ''
    else:
        pending['downtime_text'] = text
    pending['downtime_asked'] = True
    _save_pending(s, pending)
    s.set('state', 'idle')
    s.save()
    return h_record_hour(conn, s, '', user, _is_continuation=True)


def h_record_confirm(conn, s, text, user):
    pending = _load_pending(s)
    if not pending or not pending.get('job_number'):
        s.set('state', 'idle')
        s.set('pending_text', None)
        s.save()
        return 'Nothing to confirm. Say the full record.'
    pending['confirmed'] = True
    _save_pending(s, pending)
    s.set('state', 'idle')
    s.save()
    return h_record_hour(conn, s, '', user, force=True, _is_continuation=True)
