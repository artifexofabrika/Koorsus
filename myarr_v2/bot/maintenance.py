"""bot/maintenance.py — Maintenance capture with operator-stated duration."""
import re
from datetime import datetime
from . import db
from parsers import parse_float

MAINT_FIELDS = ['resolution', 'parts_used', 'technician']

def _known_stations(conn):
    rows = conn.execute(
        "SELECT DISTINCT station FROM co_steps_v2 WHERE station IS NOT NULL "
        "UNION SELECT DISTINCT station FROM downtime_events WHERE station IS NOT NULL"
    ).fetchall()
    return {r['station'].lower() for r in rows}

def _set_line_state(conn, s, user, new_state, reason=None):
    line_id = db.derive_line(conn, None, s, user)
    db.transition_line(conn, line_id, new_state, reason=reason, user_id=user['id'] if user else None)
    return line_id

def h_start_maintenance(conn, s, text, user):
    raw = re.sub(r'^(start\s+)?maintenance\s*', '', text, flags=re.IGNORECASE).strip() or 'unspecified'
    station = None
    symptom = raw
    first, _, rest = raw.partition(' ')
    if rest and first.lower() in _known_stations(conn):
        station = first
        symptom = rest.strip() or 'unspecified'

    lid = _set_line_state(conn, s, user, 'maintenance', reason=raw)
    cur = db.current_line_event(conn, lid)
    job_id = cur['job_id'] if cur else None
    now = datetime.now().isoformat()
    
    c = conn.execute(
        "INSERT INTO maintenance_events (line_id, job_id, station, started_at, "
        "category, symptom, source, user_id, raw_text, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (lid, job_id, station, now, 'unplanned', symptom, 'telegram', user['id'] if user else None, text, now))
    ev_id = c.lastrowid
    if cur:
        conn.execute("UPDATE line_events SET maintenance_event_id=? WHERE id=?", (ev_id, cur['id']))
    conn.commit()
    s.set('state', 'idle')
    s.save()
    where = f" at {station}" if station else ""
    return f"Line {lid} now in MAINTENANCE{where}. Symptom: {symptom}\nWhen resolved, say 'end maintenance'."

def h_end_maintenance(conn, s, text, user):
    lid = s.get('line_id') or (user.get('line_id') if user else None) or 1
    cur = db.current_line_event(conn, lid)
    if not cur or cur['state'] != 'maintenance':
        state = cur['state'] if cur else 'none'
        return f"Line {lid} is not in maintenance (state: {state})."
    ev_id = cur['maintenance_event_id']
    if not ev_id:
        db.close_line_event(conn, cur['id'])
        s.set('state', 'idle')
        s.save()
        return "Maintenance event had no record. Line returned to idle."
    s.set('state', 'awaiting_maint_minutes')
    s.set('pending_job_id', ev_id)
    s.set('line_id', lid)
    s.save()
    return "How many minutes was the line down? (Just the number.)"

def cont_maint_minutes(conn, s, text, user):
    mins = parse_float(text)
    if mins is None or mins < 0:
        return "Just a positive number, please. Minutes?"
    ev_id = s.get('pending_job_id')
    if not ev_id:
        s.set('state', 'idle')
        s.save()
        return "Maintenance event lost. Nothing was saved."
    now = datetime.now().isoformat()
    conn.execute("UPDATE maintenance_events SET ended_at=?, aggregate_actual_min=? WHERE id=?", (now, float(mins), ev_id))
    conn.commit()
    ev = conn.execute("SELECT * FROM maintenance_events WHERE id=?", (ev_id,)).fetchone()
    lid = ev['line_id'] if ev else (s.get('line_id') or 1)
    job_id = ev['job_id'] if ev else None
    if job_id:
        db.transition_line(conn, lid, 'production', job_id=job_id, user_id=user['id'] if user else None)
    else:
        db.transition_line(conn, lid, 'idle', user_id=user['id'] if user else None)
    s.set('state', 'maint_prompt')
    s.set('pending_step_idx', 0)
    s.set('pending_job_id', ev_id)
    s.save()
    return f"Recorded {mins:.0f} min down. What did you do to fix it?"

def handle_maint_prompt(conn, s, text, user):
    step = s.get('pending_step_idx') or 0
    ev_id = s.get('pending_job_id')
    txt = (text or '').strip()
    low = txt.lower()
    if low in ('cancel', 'stop', 'quit'):
        s.set('state', 'idle')
        s.set('pending_step_idx', None)
        s.set('pending_job_id', None)
        s.save()
        return "Maintenance notes cancelled. Event still on record."
    val = None if low in ('skip', '', 'none') else txt
    if step == 2 and low == 'me':
        val = (user or {}).get('name') or 'unknown'
    if step < 3 and val is not None:
        conn.execute(f"UPDATE maintenance_events SET {MAINT_FIELDS[step]}=? WHERE id=?", (val, ev_id))
        conn.commit()
    step += 1
    s.set('pending_step_idx', step)
    s.save()
    if step == 1: return "Parts used? (say 'none' or 'skip')"
    if step == 2: return "Technician? (say 'me' for yourself, or 'skip')"
    s.set('state', 'idle')
    s.set('pending_step_idx', None)
    s.set('pending_job_id', None)
    s.save()
    return "Notes saved. Maintenance event complete."

def h_idle(conn, s, text, user):
    reason = re.sub(r'^idle\s*', '', text, flags=re.IGNORECASE).strip() or 'unspecified'
    lid = _set_line_state(conn, s, user, 'idle', reason=reason)
    s.set('state', 'idle')
    s.save()
    return f"Line {lid} now IDLE. Reason: {reason}"

def h_unscheduled(conn, s, text, user):
    reason = re.sub(r'^unscheduled\s*', '', text, flags=re.IGNORECASE).strip() or 'unspecified'
    lid = _set_line_state(conn, s, user, 'unscheduled', reason=reason)
    s.set('state', 'idle')
    s.save()
    return f"Line {lid} now UNSCHEDULED. Reason: {reason}"
