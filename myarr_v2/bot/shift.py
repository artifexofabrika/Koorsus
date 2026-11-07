"""bot/shift.py — Shift reconciliation (start shift / end shift).

Agreed 2026-11-07: production-based accounting, no tolerance threshold,
prompt once at shift end for residual explanation, save to
shift_reconciliations. Wall-clock time is used only for ordering events,
never for duration.

RESIDUAL MATH
  usable_min       = shift length - lunch (from line_events if present)
  production_time  = (actual - scrap) / rate * 60   (rate in units/hour)
  scrap_time       = scrap / rate * 60
  downtime_min     = sum of downtime_events + unplanned maintenance
  residual_min     = usable - production_time - scrap_time - downtime

If |residual| < 0.5, treat as balanced. Otherwise prompt once.
"""
import json
from datetime import datetime, timedelta

from . import db


SHIFTS = {
    'S1': (7, 15),
    'S2': (15, 23),
    'S3': (23, 7),
}
RESIDUAL_EPSILON = 0.5


def current_shift_code(now=None):
    now = now or datetime.now()
    h = now.hour
    if 7 <= h < 15:
        return 'S1'
    if 15 <= h < 23:
        return 'S2'
    return 'S3'


def shift_window(shift_code, day):
    d = datetime.fromisoformat(day + 'T00:00:00')
    sh, eh = SHIFTS.get(shift_code, (7, 15))
    start = d.replace(hour=sh, minute=0, second=0, microsecond=0)
    if eh > sh:
        end = d.replace(hour=eh, minute=0, second=0, microsecond=0)
    else:
        end = d.replace(hour=eh, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return start, end


def _format_minutes(m):
    if m is None:
        return '—'
    neg = m < 0
    m = abs(m)
    h = int(m // 60)
    r = int(round(m % 60))
    if h == 0:
        s = f"{r} min"
    elif r == 0:
        s = f"{h}h"
    else:
        s = f"{h}h {r}m"
    return f"-{s}" if neg else s


def compute_reconciliation(conn, line_id, shift_code, day):
    start, end = shift_window(shift_code, day)

    runs = conn.execute("""
        SELECT r.units_filled, r.scrap_units, r.duration_min, j.sku_id
        FROM hourly_runs r
        JOIN jobs j ON r.job_id = j.id
        WHERE r.line_id=?
          AND r.recorded_at >= ? AND r.recorded_at < ?
          AND (r.superseded IS NULL OR r.superseded=0)
    """, (line_id, start.isoformat(), end.isoformat())).fetchall()

    actual = 0
    scrap = 0
    rate = None
    for r in runs:
        actual += (r['units_filled'] or 0)
        scrap += (r['scrap_units'] or 0)
        if rate is None:
            rate = db.ideal_rate(conn, line_id, r['sku_id'])
    if not rate or rate <= 0:
        rate = 600.0

    good = actual - scrap

    dt = conn.execute("""
        SELECT SUM(d.minutes) AS m FROM downtime_events d
        JOIN hourly_runs r ON d.run_id = r.id
        WHERE r.line_id=? AND r.recorded_at >= ? AND r.recorded_at < ?
    """, (line_id, start.isoformat(), end.isoformat())).fetchone()
    dt_events = (dt['m'] or 0) if dt else 0

    mt = conn.execute("""
        SELECT SUM(aggregate_actual_min) AS m FROM maintenance_events
        WHERE line_id=? AND started_at >= ? AND started_at < ?
          AND category='unplanned'
    """, (line_id, start.isoformat(), end.isoformat())).fetchone()
    dt_maint = (mt['m'] or 0) if mt else 0
    downtime = dt_events + dt_maint

    lunch = 0.0
    for le in conn.execute("""
        SELECT started_at, ended_at FROM line_events
        WHERE line_id=? AND state='lunch'
          AND started_at >= ? AND started_at < ?
          AND ended_at IS NOT NULL
    """, (line_id, start.isoformat(), end.isoformat())).fetchall():
        try:
            lunch += (datetime.fromisoformat(le['ended_at'])
                      - datetime.fromisoformat(le['started_at'])
                      ).total_seconds() / 60.0
        except Exception:
            pass

    shift_len = (end - start).total_seconds() / 60.0
    usable = shift_len - lunch

    production_time = (good / rate) * 60.0 if rate else 0.0
    scrap_time = (scrap / rate) * 60.0 if rate else 0.0
    residual = usable - production_time - scrap_time - downtime
    ftq_pct = (good / actual * 100.0) if actual else 0.0

    return {
        'line_id': line_id, 'shift_date': day, 'shift_code': shift_code,
        'usable_min': usable, 'actual_units': actual, 'scrap_units': scrap,
        'good_units': good, 'downtime_min': downtime,
        'production_time_min': production_time, 'scrap_time_min': scrap_time,
        'residual_min': residual, 'rate': rate, 'ftq_pct': ftq_pct,
        'run_count': len(runs),
    }


def _save(conn, rec, explanation):
    conn.execute("""
        INSERT INTO shift_reconciliations
        (line_id, shift_date, shift_code, usable_min, actual_units, scrap_units,
         downtime_min, production_time_min, scrap_time_min, residual_min,
         explanation, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        rec['line_id'], rec['shift_date'], rec['shift_code'], rec['usable_min'],
        rec['actual_units'], rec['scrap_units'], rec['downtime_min'],
        rec['production_time_min'], rec['scrap_time_min'], rec['residual_min'],
        explanation, datetime.now().isoformat()))
    conn.commit()


def _report(rec, line_name):
    lines = [
        f"Line {rec['line_id']} ({line_name}) — {rec['shift_code']} reconciliation",
        "",
        f"Usable:      {_format_minutes(rec['usable_min'])}",
        f"Actual:      {rec['actual_units']:,} units",
        f"Scrap:       {rec['scrap_units']:,} units",
        f"Good:        {rec['good_units']:,} units (FTQ {rec['ftq_pct']:.1f}%)",
        "",
        f"Production:  {_format_minutes(rec['production_time_min'])}",
        f"Downtime:    {_format_minutes(rec['downtime_min'])}",
    ]
    if abs(rec['residual_min']) < RESIDUAL_EPSILON:
        lines.append("Residual:    balanced")
    else:
        lines.append(f"Residual:    {rec['residual_min']:+.1f} min unaccounted")
    return "\n".join(lines)


def h_start_shift(conn, s, text, user):
    line_id = db.derive_line(conn, None, s, user)
    shift_code = current_shift_code()
    s.set('shift', shift_code)
    s.set('shift_hour', 1)
    s.set('line_id', line_id)
    s.save()
    line = conn.execute("SELECT name FROM lines WHERE id=?", (line_id,)).fetchone()
    name = line['name'] if line else f"Line {line_id}"
    return f"Shift {shift_code} started on Line {line_id} ({name}). Hour counter reset to 1."


def h_end_shift(conn, s, text, user):
    line_id = db.derive_line(conn, None, s, user)
    shift_code = s.get('shift') or current_shift_code()
    day = datetime.now().strftime('%Y-%m-%d')

    rec = compute_reconciliation(conn, line_id, shift_code, day)
    if rec['run_count'] == 0:
        return f"No production logged for Line {line_id} on {shift_code} today."

    line = conn.execute("SELECT name FROM lines WHERE id=?", (line_id,)).fetchone()
    name = line['name'] if line else f"Line {line_id}"
    report = _report(rec, name)

    if abs(rec['residual_min']) < RESIDUAL_EPSILON:
        _save(conn, rec, 'Balanced.')
        s.set('shift', None)
        s.set('shift_hour', 1)
        s.save()
        return report + "\n\nShift closed. Balanced."

    s.set('state', 'awaiting_shift_reason')
    s.set('pending_text', json.dumps({'rec': rec, 'line_name': name}))
    s.save()
    return report + f"\n\nYou are unaccounted for {rec['residual_min']:+.1f} minutes. What happened?"


def cont_shift_reason(conn, s, text, user):
    reason = (text or '').strip()
    if not reason:
        return "Please provide a reason, or say 'unknown'."
    try:
        payload = json.loads(s.get('pending_text') or '{}')
        rec = payload.get('rec', {})
        line_name = payload.get('line_name', '')
    except Exception:
        return "Session lost. Please run 'end shift' again."
    if not rec:
        return "Session lost. Please run 'end shift' again."

    _save(conn, rec, reason)
    report = _report(rec, line_name)
    s.set('state', 'idle')
    s.set('pending_text', None)
    s.set('shift', None)
    s.set('shift_hour', 1)
    s.save()
    return report + f"\n\nReason recorded: {reason}\n\nShift closed."
