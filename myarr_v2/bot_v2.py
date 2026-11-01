"""Myarra Telegram Bot v2 - timeline-based with line_events spine."""
import sqlite3, re, argparse, os
from datetime import datetime, timedelta
from parsers import (parse_job_number, parse_all_job_numbers, parse_hour,
                     parse_line_number, parse_bottles, parse_downtime,
                     parse_int, parse_float)

DB_PATH = os.environ.get("MYARRA_DB", "/mnt/lake/myarra.db")
UNACC_THRESHOLD = 5.0
VARIANCE_THRESHOLD = 5.0
PLAUSIBILITY_LOW = 0.50
PLAUSIBILITY_HIGH = 1.10
DEFERRED_WARN_MIN = 3.0
SHIFT_TOLERANCE_MIN = 5.0
SESSION_FIELDS = ['state','active_job_id','active_changeover_id',
                  'pending_job_id','pending_target_job_id',
                  'start_offset','pending_step_idx',
                  'shift','shift_hour','pending_text','co_total_min','line_id']


def get_conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def _setting(conn, key, default):
    try:
        r = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r['value'] if r else default
    except Exception:
        return default

def unit_label(conn):  return _setting(conn, 'unit_label', 'units')
def case_label(conn):  return _setting(conn, 'case_label', 'cases')

def _case_pack(conn, sku_id):
    r = conn.execute("SELECT case_pack FROM skus WHERE id=?", (sku_id,)).fetchone()
    return (r['case_pack'] or 1) if r else 1

def _cases(units, case_pack):
    return int(units // case_pack) if case_pack else units

def current_shift():
    h = datetime.now().hour
    return '1' if 6 <= h < 14 else ('2' if 14 <= h < 22 else '3')

def current_hour_in_shift():
    h = datetime.now().hour
    if 6 <= h < 14: return h - 6 + 1
    if 14 <= h < 22: return h - 14 + 1
    return (h + 2) % 8 + 1

def _shift_window(dt=None):
    """Return (start, end) of the shift containing dt."""
    dt = dt or datetime.now()
    h = dt.hour
    base = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if 6 <= h < 14:
        return base.replace(hour=6), base.replace(hour=14)
    if 14 <= h < 22:
        return base.replace(hour=14), base.replace(hour=22)
    # S3: 22:00 to 06:00 next day
    if h >= 22:
        return base.replace(hour=22), base + timedelta(hours=30)
    return base - timedelta(hours=2), base.replace(hour=6)

def ensure_schema(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(bot_sessions)").fetchall()]
    for col, typ in [('shift_hour','INTEGER'), ('pending_text','TEXT'),
                     ('co_total_min','REAL'), ('pending_target_job_id','INTEGER'),
                     ('line_id','INTEGER')]:
        if col not in cols:
            conn.execute(f"ALTER TABLE bot_sessions ADD COLUMN {col} {typ}")
            conn.commit()

class Session:
    def __init__(self, conn, chat_id):
        self.conn = conn
        self.chat_id = str(chat_id)
        self.data = {f: None for f in SESSION_FIELDS}
        self.data['state'] = 'idle'
        row = conn.execute("SELECT * FROM bot_sessions WHERE chat_id=?", (self.chat_id,)).fetchone()
        if row:
            d = dict(row)
            for f in SESSION_FIELDS:
                if d.get(f) is not None:
                    self.data[f] = d[f]
    def get(self, k): return self.data.get(k)
    def set(self, k, v): self.data[k] = v
    def save(self):
        vals = [self.data[f] for f in SESSION_FIELDS]
        exists = self.conn.execute("SELECT 1 FROM bot_sessions WHERE chat_id=?", (self.chat_id,)).fetchone()
        if exists:
            sets = ', '.join(f"{f}=?" for f in SESSION_FIELDS)
            self.conn.execute(f"UPDATE bot_sessions SET {sets}, updated_at=? WHERE chat_id=?",
                              vals + [datetime.now().isoformat(), self.chat_id])
        else:
            cols = ['chat_id'] + SESSION_FIELDS + ['updated_at']
            self.conn.execute(f"INSERT INTO bot_sessions ({','.join(cols)}) VALUES ({','.join('?'*len(cols))})",
                              [self.chat_id] + vals + [datetime.now().isoformat()])
        self.conn.commit()
    def clear(self):
        self.conn.execute("DELETE FROM bot_sessions WHERE chat_id=?", (self.chat_id,))
        self.conn.commit()
        self.data = {f: None for f in SESSION_FIELDS}
        self.data['state'] = 'idle'

def get_user(conn, user_id):
    row = conn.execute("SELECT * FROM users WHERE id=? AND active=1", (user_id,)).fetchone()
    return dict(row) if row else None

def get_user_by_tg(conn, tg_id):
    row = conn.execute("SELECT * FROM users WHERE telegram_id=? AND active=1", (str(tg_id),)).fetchone()
    return dict(row) if row else None

# ---------- Timeline helpers ----------

def _current_line_event(conn, line_id):
    return conn.execute(
        "SELECT * FROM line_events WHERE line_id=? AND ended_at IS NULL ORDER BY started_at DESC LIMIT 1",
        (line_id,)).fetchone()

def _close_line_event(conn, event_id, end_iso=None):
    conn.execute("UPDATE line_events SET ended_at=? WHERE id=?",
                 (end_iso or datetime.now().isoformat(), event_id))
    conn.commit()

def _transition_line(conn, line_id, new_state, job_id=None, co_event_id=None,
                     reason=None, user_id=None, source='telegram', end_at=None):
    """Ensure line is in new_state. If already matching, no-op. Otherwise close prior, open new."""
    cur = _current_line_event(conn, line_id)
    if cur and cur['state'] == new_state:
        if new_state == 'production' and cur['job_id'] == job_id:
            return cur['id']
        if new_state == 'changeover' and cur['co_event_id'] == co_event_id:
            return cur['id']
        if new_state in ('lunch','cip','maintenance','idle','unscheduled'):
            # Already in this 'other' state; leave it
            return cur['id']
    if cur:
        _close_line_event(conn, cur['id'], end_iso=end_at)
    start = end_at or datetime.now().isoformat()
    ins = conn.execute("""
        INSERT INTO line_events
        (line_id, state, started_at, ended_at, job_id, co_event_id, reason, user_id, source)
        VALUES (?,?,?,NULL,?,?,?,?,?)
    """, (line_id, new_state, start, job_id, co_event_id, reason, user_id, source))
    conn.commit()
    return ins.lastrowid

def _derive_line(conn, job, sess, user):
    if job and job.get('line_id'):
        sess.set('line_id', job['line_id'])
        return job['line_id']
    if sess.get('line_id'):
        return sess['line_id']
    if user and user.get('line_id'):
        sess.set('line_id', user['line_id'])
        return user['line_id']
    sess.set('line_id', 1)
    return 1

# ---------- Job / rate helpers ----------

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

def write_hour(conn, job, shift, period, units, duration, user_id, raw_text,
               jh_start, jh_end, unacc, dts):
    cur = conn.execute("""
        INSERT INTO hourly_runs
        (job_id, line_id, shift, period, recorded_at, units_filled, raw_text,
         duration_min, phase, job_hour_start, job_hour_end, user_id, flagged, source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (job['id'], job['line_id'], shift, period, datetime.now().isoformat(),
          units, raw_text, duration, 'run', jh_start, jh_end,
          user_id, 1 if unacc > UNACC_THRESHOLD else 0, 'telegram'))
    for d in dts:
        conn.execute("INSERT INTO downtime_events (run_id, station, reason, minutes) VALUES (?,?,?,?)",
                     (cur.lastrowid, d['station'], d['reason'], d['minutes']))
    conn.commit()
    return cur.lastrowid

def find_job(conn, job_number):
    if not job_number: return None
    r = conn.execute("SELECT * FROM jobs WHERE job_number=?", (job_number,)).fetchone()
    return dict(r) if r else None

# ---------- Changeover helper ----------

def _start_changeover_to(conn, s, from_job_id, to_job_id, user):
    fj = dict(conn.execute("SELECT * FROM jobs WHERE id=?", (from_job_id,)).fetchone())
    tj = dict(conn.execute("SELECT * FROM jobs WHERE id=?", (to_job_id,)).fetchone())
    proc = conn.execute(
        "SELECT * FROM co_procedures_v2 WHERE line_id=? AND from_sku_id=? AND to_sku_id=?",
        (fj['line_id'], fj['sku_id'], tj['sku_id'])).fetchone()
    proc_id = proc['id'] if proc else None
    now = datetime.now()
    cur = conn.execute(
        "INSERT INTO co_events (procedure_id, line_id, started_at, from_job_number, to_job_number, from_job_id, to_job_id, source) VALUES (?,?,?,?,?,?,?,?)",
        (proc_id, fj['line_id'], now.isoformat(), fj['job_number'], tj['job_number'],
         fj['id'], tj['id'], 'telegram'))
    conn.commit()
    co_id = cur.lastrowid
    _transition_line(conn, fj['line_id'], 'changeover', co_event_id=co_id,
                     user_id=user['id'] if user else None)
    s.set('active_changeover_id', co_id)
    s.set('active_job_id', None)
    s.set('pending_job_id', None)
    s.set('pending_target_job_id', None)
    s.set('line_id', fj['line_id'])
    s.set('state', 'idle'); s.save()
    time_str = now.strftime('%H:%M')
    if proc:
        return f"Changeover started at {time_str}: {fj['job_number']} -> {tj['job_number']}. Say 'end changeover' when done."
    return (f"Changeover started at {time_str}: {fj['job_number']} -> {tj['job_number']}. "
            f"No procedure on file — will record actual time only.")

# ---------- Handlers ----------

def h_running_job(conn, s, text, user, force=False):
    job = find_job(conn, parse_job_number(text))
    if not job: return "Job not found. Say: 'running job WO-2026-001, hour 5, 7000 units'."
    hour = parse_hour(text)
    if hour is None:
        s.set('state', 'awaiting_hour'); s.set('pending_text', text); s.save()
        return "Which hour? Say just the number (for example: 5)."
    units = parse_bottles(text)
    if units is None: return "How many units?"
    dts = parse_downtime(text)
    duration = 60.0 - (s.get('start_offset') or 0.0)
    bpm = ideal_rate(conn, job['line_id'], job['sku_id'])
    expected = bpm * duration / 60.0
    ok, reason = check_plausibility(units, expected, force=force)
    if not ok: return reason
    if job.get('status') != 'running':
        conn.execute("UPDATE jobs SET status='running' WHERE id=?", (job['id'],)); conn.commit()
    line_id = _derive_line(conn, job, s, user)
    _transition_line(conn, line_id, 'production', job_id=job['id'],
                     user_id=user['id'] if user else None)
    jh_start = next_job_hour(conn, job['id']); jh_end = jh_start + duration/60.0
    gap = (expected - units) / (bpm / 60.0) if bpm else 0.0
    unacc = gap - sum(d['minutes'] for d in dts)
    shift = s.get('shift') or current_shift()
    write_hour(conn, job, shift, f"H{hour}", units, duration,
               user['id'] if user else None, text, jh_start, jh_end, unacc, dts)
    s.set('active_job_id', job['id']); s.set('start_offset', None)
    s.set('shift', shift); s.set('shift_hour', hour + 1); s.save()
    flag = 'FLAG' if unacc > UNACC_THRESHOLD else 'OK'
    dt_txt = ""
    if dts:
        d = dts[0]
        dt_txt = f" Downtime: {d['minutes']:g}m at {d['station']} ({d['reason']})."
    cp = _case_pack(conn, job['sku_id']); cases = _cases(units, cp)
    cl = case_label(conn); ul = unit_label(conn)
    return (f"Logged: {job['job_number']} H{hour}, {cases:,} {cl} ({units:,} {ul}), {duration:.0f} min."
            f" Job-hours {jh_start:.1f}-{jh_end:.1f}. Gap {gap:.2f}m, unaccounted {unacc:.2f}m.{dt_txt} [{flag}]")

def h_record_hour(conn, s, text, user, force=False):
    job = find_job(conn, parse_job_number(text))
    if not job and s.get('active_job_id'):
        job = dict(conn.execute("SELECT * FROM jobs WHERE id=?", (s['active_job_id'],)).fetchone())
    if not job: return "Which job? Say: 'record production hour 5, 60 minutes, 7000 units for WO-2026-001'."
    hour = parse_hour(text)
    if hour is None: return "Which hour?"
    mm = re.search(r'(\d+(?:\.\d+)?)\s*(?:min|minutes?)', text, re.IGNORECASE)
    if not mm: return "How many minutes?"
    mins = float(mm.group(1))
    units = parse_bottles(text)
    if units is None: return "How many units?"
    bpm = ideal_rate(conn, job['line_id'], job['sku_id'])
    expected = bpm * mins / 60.0
    ok, reason = check_plausibility(units, expected, force=force)
    if not ok: return reason
    if job.get('status') != 'running':
        conn.execute("UPDATE jobs SET status='running' WHERE id=?", (job['id'],)); conn.commit()
    line_id = _derive_line(conn, job, s, user)
    _transition_line(conn, line_id, 'production', job_id=job['id'],
                     user_id=user['id'] if user else None)
    jh_start = next_job_hour(conn, job['id']); jh_end = jh_start + mins/60.0
    gap = (expected - units) / (bpm / 60.0) if bpm else 0.0
    shift = s.get('shift') or current_shift()
    write_hour(conn, job, shift, f"H{hour}", units, mins,
               user['id'] if user else None, text, jh_start, jh_end, gap, [])
    s.set('active_job_id', job['id']); s.set('shift', shift)
    s.set('shift_hour', hour + 1); s.save()
    flag = 'FLAG' if gap > UNACC_THRESHOLD else 'OK'
    cp = _case_pack(conn, job['sku_id']); cases = _cases(units, cp)
    cl = case_label(conn); ul = unit_label(conn)
    return (f"Logged (catch-up): {job['job_number']} H{hour}, {cases:,} {cl} ({units:,} {ul}), {mins:.0f} min."
            f" Job-hours {jh_start:.1f}-{jh_end:.1f}. Gap {gap:.2f}m [{flag}]")

def h_ending_job(conn, s, text, user):
    jobs_found = parse_all_job_numbers(text)
    ending_no = jobs_found[0] if jobs_found else None
    target_no = jobs_found[1] if len(jobs_found) > 1 else None
    if ending_no:
        job = find_job(conn, ending_no)
    elif s.get('active_job_id'):
        job = dict(conn.execute("SELECT * FROM jobs WHERE id=?", (s['active_job_id'],)).fetchone())
    else:
        return "Which job is ending? Say: 'end WO-2026-001'."
    if not job: return f"Job {ending_no} not found."
    # Verify current line state is production on this job
    line_id = _derive_line(conn, job, s, user)
    cur = _current_line_event(conn, line_id)
    if cur and cur['state'] != 'production':
        return f"Line {line_id} is in {cur['state'].upper()}, not production. End that state first."
    target_id = None
    if target_no:
        tj = find_job(conn, target_no)
        if not tj: return f"Target job {target_no} not found."
        target_id = tj['id']
    s.set('pending_job_id', job['id'])
    s.set('pending_target_job_id', target_id)
    s.set('state', 'awaiting_end_minutes'); s.save()
    return f"Ending {job['job_number']}. Minutes into the current hour so far? (say 0 if at the top)"

def _job_ended_at(conn, s):
    """Return ISO timestamp when job stopped, based on mins_into_hour from session."""
    mins = s.get('start_offset') or 0
    now = datetime.now()
    hour_start = now.replace(minute=0, second=0, microsecond=0)
    return (hour_start + timedelta(minutes=mins)).isoformat()

def cont_end_minutes(conn, s, text, user):
    mins = parse_int(text)
    if mins is None: return "Just a number, please. Minutes into the hour?"
    job_id = s.get('pending_job_id')
    job = dict(conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())
    line_id = _derive_line(conn, job, s, user)
    end_at = _job_ended_at(conn, s) if mins else datetime.now().isoformat()
    if mins == 0:
        end_at = datetime.now().replace(minute=0, second=0, microsecond=0).isoformat()
    s.set('start_offset', float(mins) if mins > 0 else 0.0)
    s.set('state', 'awaiting_end_units' if mins > 0 else 'closing')
    s.save()
    if mins == 0:
        # close production at top of hour
        cur = _current_line_event(conn, line_id)
        if cur: _close_line_event(conn, cur['id'], end_iso=end_at)
        conn.execute("UPDATE jobs SET status='completed', actual_end=? WHERE id=?",
                     (end_at, job_id)); conn.commit()
        return _after_ending(conn, s, user, closed_at=end_at)
    return "How many units produced in those minutes?"

def cont_end_units(conn, s, text, user):
    units = parse_int(text)
    if units is None: return "Just a number, please. How many units?"
    mins = s.get('start_offset'); job_id = s.get('pending_job_id')
    job = dict(conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())
    line_id = _derive_line(conn, job, s, user)
    end_at = _job_ended_at(conn, s)
    jh_start = next_job_hour(conn, job_id); jh_end = jh_start + mins/60.0
    bpm = ideal_rate(conn, job['line_id'], job['sku_id'])
    expected = bpm * mins / 60.0
    gap = (expected - units) / (bpm / 60.0) if bpm else 0.0
    shift = s.get('shift') or current_shift()
    hour = s.get('shift_hour') or current_hour_in_shift()
    write_hour(conn, job, shift, f"H{hour}", units, mins,
               user['id'] if user else None, text + ' (ending job)', jh_start, jh_end, gap, [])
    cur = _current_line_event(conn, line_id)
    if cur: _close_line_event(conn, cur['id'], end_iso=end_at)
    conn.execute("UPDATE jobs SET status='completed', actual_end=? WHERE id=?",
                 (end_at, job_id)); conn.commit()
    cp = _case_pack(conn, job['sku_id']); cases = _cases(units, cp)
    cl = case_label(conn)
    partial = f"Partial hour: {cases:,} {cl} in {mins:.0f} min. "
    return partial + _after_ending(conn, s, user, closed_at=end_at)

def _after_ending(conn, s, user, closed_at=None):
    job_id = s.get('pending_job_id')
    job = dict(conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()) if job_id else None
    summary = ""
    if job:
        agg = conn.execute("SELECT SUM(units_filled) b FROM hourly_runs WHERE job_id=?", (job['id'],)).fetchone()
        units = agg['b'] or 0
        cp = _case_pack(conn, job['sku_id']); cases = _cases(units, cp)
        tgt = job.get('target_quantity') or 0; tgt_cases = _cases(tgt, cp)
        pct = (units / tgt * 100) if tgt else 0
        summary = f"{job['job_number']} ended at {cases:,} of {tgt_cases:,} cases ({pct:.0f}%). "
    target_id = s.get('pending_target_job_id')
    if target_id:
        return summary + _start_changeover_to(conn, s, job_id, target_id, user)
    s.set('state', 'awaiting_changeover_decision'); s.save()
    return summary + "Start a changeover? (yes/no)"

def cont_changeover_decision(conn, s, text, user):
    low = text.lower().strip()
    if low in ('yes','y','yeah','yep','sure'):
        s.set('state', 'awaiting_changeover_target'); s.save()
        return "To which job? Say the full work order number."
    if low in ('no','n','nope','nah'):
        line_id = s.get('line_id') or 1
        _transition_line(conn, line_id, 'unscheduled', reason=None,
                         user_id=user['id'] if user else None, end_at=datetime.now().isoformat())
        s.set('active_job_id', None); s.set('state', 'idle'); s.save()
        return f"Line {line_id} now UNSCHEDULED. Say 'lunch', 'cip', 'maintenance <reason>', 'idle <reason>', or 'start WO-X' when ready."
    return "Please answer yes or no."

def cont_changeover_target(conn, s, text, user):
    job_no = parse_job_number(text)
    if not job_no: return "Say the full work order number, e.g. 'WO-2026-002'."
    tj = find_job(conn, job_no)
    if not tj: return f"Job {job_no} not found."
    job_id = s.get('pending_job_id')
    if not job_id: return "Session lost. Please start over."
    return _start_changeover_to(conn, s, job_id, tj['id'], user)

def h_changeover_start(conn, s, text, user):
    jobs_found = parse_all_job_numbers(text)
    if len(jobs_found) < 2:
        return "Changeover needs two jobs. Say: 'changeover job WO-2026-001 to WO-2026-002'."
    fj = find_job(conn, jobs_found[0]); tj = find_job(conn, jobs_found[1])
    if not fj or not tj: return f"Job {jobs_found[0] if not fj else jobs_found[1]} not found."
    return _start_changeover_to(conn, s, fj['id'], tj['id'], user)

def h_end_changeover(conn, s, text, user):
    if not s.get('active_changeover_id'): return "No active changeover. Start one first."
    s.set('state', 'awaiting_co_minutes'); s.save()
    return "Total minutes for the changeover?"

def cont_co_minutes(conn, s, text, user):
    mins = parse_float(text)
    if mins is None: return "Just a number, please. Total minutes?"
    s.set('co_total_min', float(mins))
    ev = conn.execute("SELECT * FROM co_events WHERE id=?", (s.get('active_changeover_id'),)).fetchone()
    if not ev or not ev['procedure_id']:
        return finish_co(conn, s)
    s.set('pending_step_idx', 0); s.set('state', 'awaiting_co_step'); s.save()
    return ask_next_co_step(conn, s)

def ask_next_co_step(conn, s):
    ev = conn.execute("SELECT * FROM co_events WHERE id=?", (s.get('active_changeover_id'),)).fetchone()
    if not ev: s.clear(); return "Changeover lost. Start over."
    steps = conn.execute("SELECT id, step_name, station FROM co_steps_v2 WHERE procedure_id=? ORDER BY seq",
                         (ev['procedure_id'],)).fetchall()
    idx = s.get('pending_step_idx')
    if idx >= len(steps): return finish_co(conn, s)
    st = dict(steps[idx])
    return f"Minutes for {st['step_name']} ({st['station']})? [{idx+1}/{len(steps)}]"

def cont_co_step(conn, s, text, user):
    mins = parse_float(text)
    if mins is None: return "Just a number, please. Minutes?"
    ev = conn.execute("SELECT * FROM co_events WHERE id=?", (s.get('active_changeover_id'),)).fetchone()
    steps = conn.execute("SELECT id FROM co_steps_v2 WHERE procedure_id=? ORDER BY seq",
                         (ev['procedure_id'],)).fetchall()
    idx = s.get('pending_step_idx')
    if idx >= len(steps): return finish_co(conn, s)
    conn.execute("INSERT INTO co_event_steps (event_id, step_id, actual_min) VALUES (?,?,?)",
                 (ev['id'], steps[idx]['id'], mins))
    conn.commit()
    s.set('pending_step_idx', idx + 1); s.save()
    return ask_next_co_step(conn, s)

def finish_co(conn, s):
    ev_id = s.get('active_changeover_id')
    wall_clock = s.get('co_total_min')
    if wall_clock is None:
        wall_clock = conn.execute("SELECT SUM(actual_min) FROM co_event_steps WHERE event_id=?",
                                  (ev_id,)).fetchone()[0] or 0.0
    now = datetime.now()
    conn.execute("UPDATE co_events SET aggregate_actual_min=?, ended_at=? WHERE id=?",
                 (wall_clock, now.isoformat(), ev_id))
    conn.commit()
    ev = conn.execute("""SELECT e.*, p.aggregate_standard_min FROM co_events e
                         LEFT JOIN co_procedures_v2 p ON p.id=e.procedure_id WHERE e.id=?""",
                      (ev_id,)).fetchone()
    std = ev['aggregate_standard_min'] if ev else None
    steps = conn.execute("""SELECT st.step_name, st.standard_min, es.actual_min
                            FROM co_event_steps es JOIN co_steps_v2 st ON st.id=es.step_id
                            WHERE es.event_id=?""", (ev_id,)).fetchall()
    deltas = [(r['step_name'], r['actual_min'] - r['standard_min'])
              for r in steps if r['standard_min'] is not None and r['actual_min'] is not None]
    best = min(deltas, key=lambda x: x[1]) if deltas else None
    worst = max(deltas, key=lambda x: x[1]) if deltas else None
    s.set('pending_step_idx', None); s.set('co_total_min', None)

    if std is None:
        msg = f"Changeover saved. Actual: {wall_clock:.0f} min. No standard on file — recorded for history."
    else:
        var = wall_clock - std
        flag = 'FLAG' if var > VARIANCE_THRESHOLD else 'OK'
        msg = f"Changeover saved. Total {wall_clock:.0f}m vs {std:.0f}m std ({var:+.0f}m) [{flag}]."
        if best and worst and best[0] != worst[0] and (best[1] < 0 or worst[1] > 0):
            msg += f" Best: {best[0]} {best[1]:+.0f}m. Worst: {worst[0]} {worst[1]:+.0f}m."

    # Close the changeover line event; the next state will be opened by the auto-prompt flow
    line_id = ev['line_id'] if ev else (s.get('line_id') or 1)
    cur = _current_line_event(conn, line_id)
    if cur and cur['state'] == 'changeover':
        _close_line_event(conn, cur['id'], end_iso=now.isoformat())

    to_job_id = ev['to_job_id'] if ev else None
    if to_job_id:
        tj = conn.execute("SELECT job_number FROM jobs WHERE id=?", (to_job_id,)).fetchone()
        label = tj['job_number'] if tj else 'the next job'
        s.set('pending_job_id', to_job_id)
        s.set('active_changeover_id', ev_id)  # keep for gap check
        s.set('state', 'awaiting_new_job_confirm'); s.save()
        return msg + f"\nStart {label} now? (yes/no)"

    s.set('active_changeover_id', None)
    s.set('state', 'idle'); s.save()
    return msg

def cont_new_job_confirm(conn, s, text, user):
    low = text.lower().strip()
    if low in ('yes','y','yeah','yep','sure','start','starting','go'):
        gap_note = ""
        ev_id = s.get('active_changeover_id')
        if ev_id:
            ev = conn.execute("SELECT ended_at, notes FROM co_events WHERE id=?", (ev_id,)).fetchone()
            if ev and ev['ended_at']:
                try:
                    ended = datetime.fromisoformat(ev['ended_at'])
                    gap = (datetime.now() - ended).total_seconds() / 60.0
                    if gap > DEFERRED_WARN_MIN:
                        gap_note = f" (Started {gap:.0f} min after changeover end — noted)"
                        existing = ev['notes'] or ''
                        conn.execute("UPDATE co_events SET notes=? WHERE id=?",
                                     (existing + f" | start deferred {gap:.0f} min", ev_id))
                        conn.commit()
                except Exception:
                    pass
        # Open idle to fill the gap until start_minutes
        line_id = s.get('line_id') or 1
        _transition_line(conn, line_id, 'idle', reason='post-changeover wait',
                         user_id=user['id'] if user else None)
        s.set('active_changeover_id', None)
        s.set('state', 'awaiting_start_minutes'); s.save()
        return f"Minutes into the current hour when production started?{gap_note}"
    if low in ('no','n','nope','nah','not yet','wait','later'):
        job_id = s.get('pending_job_id')
        jn = conn.execute("SELECT job_number FROM jobs WHERE id=?", (job_id,)).fetchone() if job_id else None
        label = jn['job_number'] if jn else 'the job'
        line_id = s.get('line_id') or 1
        _transition_line(conn, line_id, 'idle', reason=f'waiting to start {label}',
                         user_id=user['id'] if user else None)
        s.set('pending_job_id', None)
        s.set('active_changeover_id', None)
        s.set('state', 'idle'); s.save()
        return f"OK. Line {line_id} is IDLE, waiting to start {label}."
    return "Please answer yes or no."

def h_start_job(conn, s, text, user):
    job = find_job(conn, parse_job_number(text))
    if not job: return "Say: 'start WO-2026-002'."
    if job.get('status') == 'running':
        return f"{job['job_number']} is already running."
    s.set('pending_job_id', job['id'])
    s.set('line_id', job['line_id'])
    s.set('state', 'awaiting_start_minutes'); s.save()
    return f"Starting {job['job_number']}. Minutes into the current hour when it started?"

def cont_start_minutes(conn, s, text, user):
    mins = parse_int(text)
    if mins is None: return "Just a number, please. Minutes into hour?"
    job_id = s.get('pending_job_id')
    job = dict(conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())
    conn.execute("UPDATE jobs SET status='running', actual_end=NULL, actual_start=COALESCE(actual_start, ?) WHERE id=?",
                 (datetime.now().isoformat(), job_id))
    conn.commit()
    line_id = _derive_line(conn, job, s, user)
    _transition_line(conn, line_id, 'production', job_id=job_id,
                     user_id=user['id'] if user else None)
    s.set('active_job_id', job_id); s.set('pending_job_id', None)
    s.set('start_offset', float(mins)); s.set('shift_hour', current_hour_in_shift())
    s.set('state', 'idle'); s.save()
    return f"Job {job['job_number']} started {mins} min into the hour. Ready to log."

def h_pause_job(conn, s, text, user):
    job_no = parse_job_number(text)
    if job_no: job = find_job(conn, job_no)
    elif s.get('active_job_id'):
        job = dict(conn.execute("SELECT * FROM jobs WHERE id=?", (s['active_job_id'],)).fetchone())
    else: return "Which job to pause?"
    if not job: return f"Job {job_no} not found."
    if job.get('status') != 'running':
        return f"{job['job_number']} is not running (status: {job.get('status') or 'unknown'})."
    conn.execute("UPDATE jobs SET status='paused' WHERE id=?", (job['id'],)); conn.commit()
    line_id = _derive_line(conn, job, s, user)
    _transition_line(conn, line_id, 'idle', reason=f'paused {job["job_number"]}',
                     user_id=user['id'] if user else None)
    s.set('active_job_id', None); s.save()
    return f"{job['job_number']} paused."

def h_resume_job(conn, s, text, user):
    job_no = parse_job_number(text)
    if not job_no: return "Say: 'resume WO-2026-001'."
    job = find_job(conn, job_no)
    if not job: return f"Job {job_no} not found."
    if job.get('status') not in ('paused', 'completed'):
        return f"{job['job_number']} is not paused or completed (status: {job.get('status') or 'unknown'})."
    conn.execute("UPDATE jobs SET status='running', actual_end=NULL WHERE id=?", (job['id'],)); conn.commit()
    line_id = _derive_line(conn, job, s, user)
    _transition_line(conn, line_id, 'production', job_id=job['id'],
                     user_id=user['id'] if user else None)
    s.set('active_job_id', job['id']); s.set('shift', None); s.set('shift_hour', None); s.save()
    return f"{job['job_number']} resumed. Job-hour continues at {next_job_hour(conn, job['id']):.1f}."

# ---------- Line-state commands (lunch / cip / maintenance / idle / unscheduled) ----------

def _set_line_state(conn, s, user, state, reason=None):
    line_id = s.get('line_id')
    if not line_id:
        line_id = (user or {}).get('line_id') or 1
        s.set('line_id', line_id)
    _transition_line(conn, line_id, state, reason=reason,
                     user_id=user['id'] if user else None)
    return line_id

def h_start_lunch(conn, s, text, user):
    lid = _set_line_state(conn, s, user, 'lunch')
    s.set('state', 'idle'); s.save()
    return f"Line {lid} now in LUNCH."

def h_end_lunch(conn, s, text, user):
    lid = s.get('line_id') or 1
    cur = _current_line_event(conn, lid)
    if not cur or cur['state'] != 'lunch':
        return f"Line {lid} is not in lunch (state: {cur['state'] if cur else 'none'})."
    # If there's an active job, resume production; else idle
    if s.get('active_job_id'):
        job = conn.execute("SELECT * FROM jobs WHERE id=?", (s['active_job_id'],)).fetchone()
        _transition_line(conn, lid, 'production', job_id=job['id'],
                         user_id=user['id'] if user else None)
        return f"Lunch ended. Back to production on {job['job_number']}."
    _transition_line(conn, lid, 'idle', reason='post-lunch',
                     user_id=user['id'] if user else None)
    return f"Lunch ended. Line {lid} IDLE."

def h_start_cip(conn, s, text, user):
    lid = _set_line_state(conn, s, user, 'cip')
    s.set('state', 'idle'); s.save()
    return f"Line {lid} now in CIP."

def h_end_cip(conn, s, text, user):
    lid = s.get('line_id') or 1
    cur = _current_line_event(conn, lid)
    if not cur or cur['state'] != 'cip':
        return f"Line {lid} is not in CIP (state: {cur['state'] if cur else 'none'})."
    if s.get('active_job_id'):
        job = conn.execute("SELECT * FROM jobs WHERE id=?", (s['active_job_id'],)).fetchone()
        _transition_line(conn, lid, 'production', job_id=job['id'],
                         user_id=user['id'] if user else None)
        return f"CIP ended. Back to production on {job['job_number']}."
    _transition_line(conn, lid, 'idle', reason='post-cip',
                     user_id=user['id'] if user else None)
    return f"CIP ended. Line {lid} IDLE."

def h_start_maintenance(conn, s, text, user):
    reason = re.sub(r'^(start\s+)?maintenance\s*', '', text, flags=re.IGNORECASE).strip() or 'unspecified'
    lid = _set_line_state(conn, s, user, 'maintenance', reason=reason)
    s.set('state', 'idle'); s.save()
    return f"Line {lid} now in MAINTENANCE. Reason: {reason}"

def h_end_maintenance(conn, s, text, user):
    lid = s.get('line_id') or 1
    cur = _current_line_event(conn, lid)
    if not cur or cur['state'] != 'maintenance':
        return f"Line {lid} is not in maintenance (state: {cur['state'] if cur else 'none'})."
    if s.get('active_job_id'):
        job = conn.execute("SELECT * FROM jobs WHERE id=?", (s['active_job_id'],)).fetchone()
        _transition_line(conn, lid, 'production', job_id=job['id'],
                         user_id=user['id'] if user else None)
        return f"Maintenance ended. Back to production on {job['job_number']}."
    _transition_line(conn, lid, 'idle', reason='post-maintenance',
                     user_id=user['id'] if user else None)
    return f"Maintenance ended. Line {lid} IDLE."

def h_idle(conn, s, text, user):
    reason = re.sub(r'^idle\s*', '', text, flags=re.IGNORECASE).strip() or 'unspecified'
    lid = _set_line_state(conn, s, user, 'idle', reason=reason)
    s.set('state', 'idle'); s.save()
    return f"Line {lid} now IDLE. Reason: {reason}"

def h_unscheduled(conn, s, text, user):
    reason = re.sub(r'^unscheduled\s*', '', text, flags=re.IGNORECASE).strip() or 'none'
    lid = _set_line_state(conn, s, user, 'unscheduled', reason=reason)
    s.set('state', 'idle'); s.save()
    return f"Line {lid} now UNSCHEDULED. Reason: {reason}"

# ---------- Status ----------

def _format_minutes(m):
    if m < 60: return f"{m:.0f} min"
    return f"{int(m//60)}h {int(m%60)}m"

def h_status_job(conn, s, text, user):
    job_no = parse_job_number(text)
    if not job_no: return "Say: 'status WO-2026-001'."
    job = conn.execute("""SELECT j.*, s.case_pack AS sku_case_pack, s.part_number, s.description,
                                 l.name AS line_name
                          FROM jobs j
                          LEFT JOIN skus s ON s.id = j.sku_id
                          LEFT JOIN lines l ON l.id = j.line_id
                          WHERE j.job_number=?""", (job_no,)).fetchone()
    if not job: return f"Job {job_no} not found."
    job = dict(job)
    cp = job['sku_case_pack'] or 1
    tgt_units = job['target_quantity'] or 0
    tgt_cases = _cases(tgt_units, cp)
    agg = conn.execute("SELECT SUM(units_filled) b FROM hourly_runs WHERE job_id=?", (job['id'],)).fetchone()
    units = agg['b'] or 0
    cases = _cases(units, cp)
    pct = (units / tgt_units * 100) if tgt_units else 0
    cl = case_label(conn)
    status = job.get('status') or 'scheduled'

    header = f"{job['job_number']}: {status.upper()}"
    if status == 'completed' and job.get('actual_end'):
        header += f" {job['actual_end'][:16].replace('T', ' ')}"
    elif status == 'paused':
        header += " (will resume)"
    lines = [header]
    if job.get('description'):
        lines.append(f"{job['part_number']} {job['description']}")
    if status == 'scheduled':
        if job.get('line_name'):
            lines.append(f"Assigned to Line {job['line_id']} ({job['line_name']}). Target {tgt_cases:,} {cl}.")
        else:
            lines.append(f"No line assigned. Target {tgt_cases:,} {cl}.")
        lines.append("No production logged yet.")
    else:
        if job.get('line_name'):
            lines.append(f"Line {job['line_id']} ({job['line_name']})")
        lines.append(f"{cases:,} of {tgt_cases:,} {cl} ({pct:.1f}%)")
    return "\n".join(lines)

def h_status_line(conn, s, text, user):
    lid = parse_line_number(text)
    if lid is None: return "Say: 'status line 1'."
    line = conn.execute("SELECT * FROM lines WHERE id=?", (lid,)).fetchone()
    if not line:
        avail = conn.execute("SELECT id, name FROM lines ORDER BY id").fetchall()
        return f"Line {lid} not configured. Available: " + ", ".join(f"Line {r['id']} ({r['name']})" for r in avail)
    cl = case_label(conn); ul = unit_label(conn)
    rate_row = conn.execute("SELECT MAX(ideal_rate) v FROM line_sku_rates WHERE line_id=?", (lid,)).fetchone()
    rate = rate_row['v'] if rate_row else 600
    cur = _current_line_event(conn, lid)
    header = f"Line {lid} ({line['name']})"
    if not cur:
        return f"{header}: no active state."
    state = cur['state'].upper()
    try:
        started = datetime.fromisoformat(cur['started_at'])
    except Exception:
        started = datetime.now()
    elapsed = (datetime.now() - started).total_seconds() / 60.0
    lines = [f"{header} — {state}"]
    if cur['state'] == 'production':
        job = conn.execute("""SELECT j.*, s.case_pack AS sku_case_pack, s.part_number, s.description
                              FROM jobs j LEFT JOIN skus s ON s.id=j.sku_id WHERE j.id=?""",
                           (cur['job_id'],)).fetchone()
        if job:
            cp = job['sku_case_pack'] or 1
            tgt_units = job['target_quantity'] or 0; tgt_cases = _cases(tgt_units, cp)
            agg = conn.execute("SELECT SUM(units_filled) b FROM hourly_runs WHERE job_id=?", (job['id'],)).fetchone()
            units = agg['b'] or 0; cases = _cases(units, cp)
            pct = (units / tgt_units * 100) if tgt_units else 0
            lines.append(f"Running: {job['job_number']} {job['description'] or ''}".rstrip())
            lines.append(f"{cases:,} of {tgt_cases:,} {cl} ({pct:.1f}%)")
            lines.append(f"Started {started.strftime('%H:%M')} — {_format_minutes(elapsed)} elapsed")
    elif cur['state'] == 'changeover':
        std = None
        if cur['co_event_id']:
            cev = conn.execute("SELECT * FROM co_events WHERE id=?", (cur['co_event_id'],)).fetchone()
            if cev:
                lines.append(f"{cev['from_job_number']} -> {cev['to_job_number']}")
                if cev['procedure_id']:
                    pr = conn.execute("SELECT aggregate_standard_min FROM co_procedures_v2 WHERE id=?",
                                      (cev['procedure_id'],)).fetchone()
                    std = pr['aggregate_standard_min'] if pr else None
        if std:
            remaining = std - elapsed
            label = f"{remaining:.0f} min remaining" if remaining >= 0 else f"over by {-remaining:.0f}"
            lines.append(f"Started {started.strftime('%H:%M')} — {elapsed:.0f} of {std:.0f} min ({label})")
        else:
            lines.append(f"Started {started.strftime('%H:%M')} — {elapsed:.0f} min elapsed (no standard)")
    elif cur['state'] in ('lunch','cip','maintenance','idle','unscheduled'):
        if cur['reason']:
            lines.append(f"Reason: {cur['reason']}")
        lines.append(f"Since {started.strftime('%H:%M')} — {_format_minutes(elapsed)}")
        # Add last job context if session has it
        if s.get('active_job_id'):
            j = conn.execute("SELECT job_number FROM jobs WHERE id=?", (s['active_job_id'],)).fetchone()
            if j:
                lines.append(f"Will resume: {j['job_number']}")
    return "\n".join(lines)

def h_end_shift(conn, s, text, user):
    """Reconcile current shift for current line."""
    lid = s.get('line_id') or (user.get('line_id') if user else None) or 1
    line = conn.execute("SELECT name FROM lines WHERE id=?", (lid,)).fetchone()
    name = line['name'] if line else f'Line {lid}'
    start, end = _shift_window()
    now = datetime.now()
    reconcile_end = min(now, end)
    rows = conn.execute("""
        SELECT started_at, ended_at, state FROM line_events
        WHERE line_id=? AND ended_at IS NOT NULL
        AND started_at < ? AND ended_at > ?
        ORDER BY started_at
    """, (lid, reconcile_end.isoformat(), start.isoformat())).fetchall()
    total = 0; by_state = {}
    for r in rows:
        s_dt = max(datetime.fromisoformat(r['started_at']), start)
        t_dt = min(datetime.fromisoformat(r['ended_at']), reconcile_end)
        if t_dt > s_dt:
            mins = (t_dt - s_dt).total_seconds() / 60.0
            total += mins
            by_state[r['state']] = by_state.get(r['state'], 0) + mins
    shift_len = (reconcile_end - start).total_seconds() / 60.0
    gap = shift_len - total
    lines = [f"Line {lid} ({name}) — Shift {current_shift()} reconciliation"]
    lines.append(f"Shift so far: {_format_minutes(shift_len)} (to {reconcile_end.strftime('%H:%M')})")
    lines.append(f"Accounted: {_format_minutes(total)}")
    for st in ['production','changeover','lunch','cip','maintenance','idle','unscheduled']:
        if st in by_state:
            lines.append(f"  {st:12s} {_format_minutes(by_state[st])}")
    if abs(gap) <= SHIFT_TOLERANCE_MIN:
        lines.append(f"Gap: {gap:+.1f} min — WITHIN TOLERANCE")
    else:
        lines.append(f"Gap: {gap:+.1f} min — OUTSIDE TOLERANCE (should be within ±{SHIFT_TOLERANCE_MIN:.0f})")
    return "\n".join(lines)

# ---------- SOP, handover, takeover ----------

def h_sop(conn, s, text, user):
    q = re.sub(r'^(sop|ask|question)[,:\s]+', '', text, flags=re.IGNORECASE).strip()
    if not q: return "What is your question?"
    try:
        import requests
        r = requests.post("http://127.0.0.1:5000/ask", json={'question': q}, timeout=60)
        if r.status_code == 200:
            d = r.json()
            return d.get('answer') or d.get('response') or str(d)
        return f"Document service returned {r.status_code}."
    except Exception as e:
        return f"Document service unavailable: {e}"

def h_handover(conn, s, text, user):
    job = find_job(conn, parse_job_number(text))
    if not job and s.get('active_job_id'):
        job = dict(conn.execute("SELECT * FROM jobs WHERE id=?", (s['active_job_id'],)).fetchone())
    if not job: return "Which job?"
    agg = conn.execute("SELECT SUM(units_filled) b, SUM(duration_min) m FROM hourly_runs WHERE job_id=?",
                       (job['id'],)).fetchone()
    jh = next_job_hour(conn, job['id'])
    s.set('pending_job_id', job['id']); s.set('state', 'awaiting_handover_notes'); s.save()
    cp = _case_pack(conn, job['sku_id']); cases = _cases(agg['b'] or 0, cp)
    tgt_cases = _cases(job['target_quantity'] or 0, cp); cl = case_label(conn)
    return (f"Handover summary for {job['job_number']}:\n"
            f"Hours logged: {agg['m'] or 0:.0f} min (job-hour {jh:.1f})\n"
            f"Produced: {cases:,} / {tgt_cases:,} {cl}\n"
            f"Notes: {job.get('handover_notes') or 'none'}\n"
            f"Any notes for the incoming shift?")

def cont_handover_notes(conn, s, text, user):
    conn.execute("UPDATE jobs SET handover_notes=? WHERE id=?", (text, s.get('pending_job_id')))
    conn.commit()
    s.set('pending_job_id', None); s.set('state', 'idle'); s.save()
    return "Handover notes saved."

def h_takeover(conn, s, text, user):
    job = find_job(conn, parse_job_number(text))
    if not job: return "Say: 'taking over job WO-2026-001'."
    agg = conn.execute("SELECT SUM(units_filled) b FROM hourly_runs WHERE job_id=?", (job['id'],)).fetchone()
    jh = next_job_hour(conn, job['id'])
    s.set('active_job_id', job['id']); s.set('pending_job_id', None)
    s.set('start_offset', None); s.set('shift', None); s.set('shift_hour', None)
    s.set('line_id', job['line_id'])
    s.set('state', 'idle'); s.save()
    cp = _case_pack(conn, job['sku_id']); cases = _cases(agg['b'] or 0, cp)
    tgt_cases = _cases(job['target_quantity'] or 0, cp); cl = case_label(conn)
    return (f"Taking over {job['job_number']}.\n"
            f"Job-hours completed: {jh:.1f}. Produced: {cases:,} / {tgt_cases:,} {cl}.\n"
            f"Handover notes: {job.get('handover_notes') or 'none'}\n"
            f"Ready to log: 'running job {job['job_number']}, hour 1, N {cl}'.")

def cont_awaiting_hour(conn, s, text, user):
    hour = parse_hour("hour " + text) or parse_int(text)
    if hour is None or hour < 1 or hour > 12:
        return "Just a number, please (for example: 5)."
    pending = s.get('pending_text') or ''
    s.set('pending_text', None); s.set('state', 'idle'); s.save()
    cleaned = re.sub(r'\bhour\s+\w+\b', '', pending, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return h_running_job(conn, s, f"{cleaned} hour {hour}", user)

HELP = """I understand:
  running job WO-XXXX-XXX, hour N, UNITS [N min down STATION reason]
  record production hour N, M minutes, UNITS
  start WO-XXXX-XXX | start job WO-XXXX-XXX
  end WO-XXXX-XXX [changeover to WO-XXXX-XXX]
  end changeover
  pause WO-XXXX-XXX | resume WO-XXXX-XXX
  lunch | end lunch
  cip | end cip
  maintenance <reason> | end maintenance
  idle <reason> | unscheduled <reason>
  status WO-XXXX-XXX | status line N
  end shift
  handover job WO-XXXX-XXX | taking over job WO-XXXX-XXX
  sop, your question
  cancel"""

def h_unknown(conn, s, text, user):
    s.set('state', 'idle'); s.save()
    return "I did not understand.\n" + HELP

def dispatch(conn, s, text, user):
    text = text.strip()
    if not text: return None

    # State machine (multi-step flows)
    state = s.get('state')
    if state == 'awaiting_end_minutes':     return cont_end_minutes(conn, s, text, user)
    if state == 'awaiting_end_units':       return cont_end_units(conn, s, text, user)
    if state == 'awaiting_changeover_decision': return cont_changeover_decision(conn, s, text, user)
    if state == 'awaiting_changeover_target':   return cont_changeover_target(conn, s, text, user)
    if state == 'awaiting_new_job_confirm': return cont_new_job_confirm(conn, s, text, user)
    if state == 'awaiting_co_minutes':      return cont_co_minutes(conn, s, text, user)
    if state == 'awaiting_co_step':         return cont_co_step(conn, s, text, user)
    if state == 'awaiting_start_minutes':   return cont_start_minutes(conn, s, text, user)
    if state == 'awaiting_handover_notes':  return cont_handover_notes(conn, s, text, user)
    if state == 'awaiting_hour':            return cont_awaiting_hour(conn, s, text, user)

    # confirm / cancel
    force = False
    if re.match(r'^confirm[\s,]+', text, re.IGNORECASE):
        force = True
        text = re.sub(r'^confirm[\s,]+', '', text, count=1, flags=re.IGNORECASE).strip()
        if not text: return "Say the full command after 'confirm', please."

    low = text.lower().strip()
    if low in ('cancel','stop','quit','exit'):
        s.clear(); return "Cancelled."

    # Line-state commands (before job commands, so 'start lunch' does not try to find a job named 'lunch')
    if re.match(r'^(start\s+lunch|lunch)\b', low):
        return h_start_lunch(conn, s, text, user)
    if re.match(r'^end\s+lunch\b', low):
        return h_end_lunch(conn, s, text, user)
    if re.match(r'^(start\s+cip|cip)\b', low):
        return h_start_cip(conn, s, text, user)
    if re.match(r'^end\s+cip\b', low):
        return h_end_cip(conn, s, text, user)
    if re.match(r'^(start\s+)?maintenance\b', low):
        if low.startswith('end '):
            return h_end_maintenance(conn, s, text, user)
        return h_start_maintenance(conn, s, text, user)
    if re.match(r'^idle\b', low):
        return h_idle(conn, s, text, user)
    if re.match(r'^unscheduled\b', low):
        return h_unscheduled(conn, s, text, user)
    if re.match(r'^end\s+shift\b', low) or low == 'end shift':
        return h_end_shift(conn, s, text, user)

    # Structured triggers
    if re.match(r'^(running|run)\b', low):
        return h_running_job(conn, s, text, user, force=force)
    if re.match(r'^record\b', low) and 'production hour' in low:
        return h_record_hour(conn, s, text, user, force=force)
    if re.match(r'^(end(ing)?|finish(ing)?|clos\w*)\b', low):
        has_job = bool(parse_job_number(text))
        if 'change' in low and not has_job:
            return h_end_changeover(conn, s, text, user)
        return h_ending_job(conn, s, text, user)
    if re.match(r'^change[\s-]*over\b', low):
        return h_changeover_start(conn, s, text, user)
    if re.match(r'^(start|starting|begin|beginning)\b', low):
        return h_start_job(conn, s, text, user)
    if re.match(r'^(pause|pausing|suspend|suspending|hold|holding)\b', low):
        return h_pause_job(conn, s, text, user)
    if re.match(r'^(resume|resuming|restart|restarting|unpause|continue|continuing)\b', low) or re.match(r'^back\s+to\b', low):
        return h_resume_job(conn, s, text, user)
    if re.match(r'^status\b', low):
        if 'line' in low:
            return h_status_line(conn, s, text, user)
        if parse_job_number(text):
            return h_status_job(conn, s, text, user)
        return "Say: 'status line N' or 'status WO-XXXX-XXX'."
    if re.match(r'^(sop|ask|question)\b', low):
        return h_sop(conn, s, text, user)
    if re.match(r'^handover\b', low):
        return h_handover(conn, s, text, user)
    if re.match(r'^(taking\s+over|take\s+over|took\s+over)\b', low):
        return h_takeover(conn, s, text, user)

    return h_unknown(conn, s, text, user)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--chat-id', default='dryrun')
    ap.add_argument('--user-id', type=int, default=1)
    args = ap.parse_args()
    conn = get_conn(); ensure_schema(conn)
    user = get_user(conn, args.user_id)
    if not user:
        print(f"ERROR: user {args.user_id} not found"); return
    if not args.dry_run:
        print("Live mode not in v2. Use --dry-run."); conn.close(); return
    print(f"=== DRY RUN as {user['name']} (id {user['id']}) — 'quit' to exit ===")
    while True:
        try: text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt): break
        if text.lower() in ('quit', 'exit'): break
        s = Session(conn, args.chat_id)
        print(f"Bot: {dispatch(conn, s, text, user)}\n")
    conn.close()

if __name__ == '__main__':
    main()
