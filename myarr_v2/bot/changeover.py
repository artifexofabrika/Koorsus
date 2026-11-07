"""bot/changeover.py — Changeover capture and per-step timing.

Agreed 2026-11-07: modular rewrite. Changeover is one concern.
Steps captured per station; aggregate actual is operator-stated wall clock,
never the sum of steps (steps overlap in packaging).

Commands:
    changeover job WO-A to WO-B     (start)
    end changeover                  (begin the duration prompt)
    <N>                             (total minutes)
    <N>                             (each step, in order)
"""
from datetime import datetime

from . import db
from parsers import parse_all_job_numbers, parse_float

VARIANCE_THRESHOLD = 5.0


def _resolve_job(conn, job_no):
    r = conn.execute("SELECT * FROM jobs WHERE job_number=?", (job_no,)).fetchone()
    return dict(r) if r else None


def _log_bom_changes(conn, co_id, from_sku, to_sku):
    """Insert a co_event_changes row for every component whose value differs."""
    from_bom = {r['component_type_id']: r['component_value']
                for r in conn.execute(
                    "SELECT component_type_id, component_value FROM sku_bom WHERE sku_id=?",
                    (from_sku,)).fetchall()}
    to_bom = {r['component_type_id']: r['component_value']
              for r in conn.execute(
                  "SELECT component_type_id, component_value FROM sku_bom WHERE sku_id=?",
                  (to_sku,)).fetchall()}
    for ct_id, from_val in from_bom.items():
        to_val = to_bom.get(ct_id)
        if to_val != from_val:
            conn.execute(
                "INSERT INTO co_event_changes (event_id, component_type_id, from_value, to_value) "
                "VALUES (?,?,?,?)",
                (co_id, ct_id, from_val, to_val))
    conn.commit()


def h_changeover_start(conn, s, text, user):
    jobs = parse_all_job_numbers(text)
    if len(jobs) < 2:
        return "Changeover needs two jobs. Say: 'changeover job WO-2026-001 to WO-2026-002'."
    fj = _resolve_job(conn, jobs[0])
    if not fj:
        return f"No job found for '{jobs[0]}'."
    tj = _resolve_job(conn, jobs[1])
    if not tj:
        return f"No job found for '{jobs[1]}'."

    proc = conn.execute(
        "SELECT * FROM co_procedures_v2 WHERE line_id=? AND from_sku_id=? AND to_sku_id=?",
        (fj['line_id'], fj['sku_id'], tj['sku_id'])).fetchone()
    proc_id = proc['id'] if proc else None
    now = datetime.now()

    cur = conn.execute(
        "INSERT INTO co_events (procedure_id, line_id, started_at, from_job_number, "
        "to_job_number, from_job_id, to_job_id, source) VALUES (?,?,?,?,?,?,?,?)",
        (proc_id, fj['line_id'], now.isoformat(), fj['job_number'],
         tj['job_number'], fj['id'], tj['id'], 'telegram'))
    conn.commit()
    co_id = cur.lastrowid

    _log_bom_changes(conn, co_id, fj['sku_id'], tj['sku_id'])
    db.transition_line(conn, fj['line_id'], 'changeover', co_event_id=co_id,
                       user_id=user['id'] if user else None)

    s.set('active_changeover_id', co_id)
    s.set('active_job_id', None)
    s.set('pending_job_id', None)
    s.set('pending_target_job_id', tj['id'])
    s.set('line_id', fj['line_id'])
    s.set('state', 'idle')
    s.save()

    t = now.strftime('%H:%M')
    if proc:
        return f"Changeover started at {t}: {fj['job_number']} -> {tj['job_number']}. Say 'end changeover' when done."
    return (f"Changeover started at {t}: {fj['job_number']} -> {tj['job_number']}. "
            f"No procedure on file — will record actual time only.")


def h_end_changeover(conn, s, text, user):
    if not s.get('active_changeover_id'):
        return "No active changeover. Start one first."
    s.set('state', 'awaiting_co_minutes')
    s.save()
    return "Total minutes for the changeover?"


def cont_co_minutes(conn, s, text, user):
    mins = parse_float(text)
    if mins is None:
        return "Just a number, please. Total minutes?"
    s.set('co_total_min', float(mins))
    ev = conn.execute("SELECT * FROM co_events WHERE id=?",
                      (s.get('active_changeover_id'),)).fetchone()
    if not ev or not ev['procedure_id']:
        return finish_co(conn, s)
    s.set('pending_step_idx', 0)
    s.set('state', 'awaiting_co_step')
    s.save()
    return ask_next_co_step(conn, s)


def ask_next_co_step(conn, s):
    ev = conn.execute("SELECT * FROM co_events WHERE id=?",
                      (s.get('active_changeover_id'),)).fetchone()
    if not ev:
        s.clear()
        return "Changeover lost. Start over."
    steps = conn.execute(
        "SELECT id, step_name, station FROM co_steps_v2 WHERE procedure_id=? ORDER BY seq",
        (ev['procedure_id'],)).fetchall()
    idx = s.get('pending_step_idx') or 0
    if idx >= len(steps):
        return finish_co(conn, s)
    st = dict(steps[idx])
    return f"Minutes for {st['step_name']} ({st['station']})? [{idx+1}/{len(steps)}]"


def cont_co_step(conn, s, text, user):
    mins = parse_float(text)
    if mins is None:
        return "Just a number, please. Minutes for this step?"
    ev_id = s.get('active_changeover_id')
    ev = conn.execute("SELECT * FROM co_events WHERE id=?", (ev_id,)).fetchone()
    if not ev:
        s.clear()
        return "Changeover lost. Start over."
    steps = conn.execute(
        "SELECT id FROM co_steps_v2 WHERE procedure_id=? ORDER BY seq",
        (ev['procedure_id'],)).fetchall()
    idx = s.get('pending_step_idx') or 0
    if idx < len(steps):
        conn.execute(
            "INSERT INTO co_event_steps (event_id, step_id, actual_min) VALUES (?,?,?)",
            (ev_id, steps[idx]['id'], mins))
        conn.commit()
    s.set('pending_step_idx', idx + 1)
    s.save()
    return ask_next_co_step(conn, s)


def finish_co(conn, s):
    ev_id = s.get('active_changeover_id')
    wall_clock = s.get('co_total_min')
    if wall_clock is None:
        wall_clock = conn.execute(
            "SELECT SUM(actual_min) FROM co_event_steps WHERE event_id=?",
            (ev_id,)).fetchone()[0] or 0.0
    now = datetime.now()
    conn.execute(
        "UPDATE co_events SET aggregate_actual_min=?, ended_at=? WHERE id=?",
        (wall_clock, now.isoformat(), ev_id))
    conn.commit()

    ev = conn.execute(
        "SELECT e.*, p.aggregate_standard_min FROM co_events e "
        "LEFT JOIN co_procedures_v2 p ON p.id=e.procedure_id WHERE e.id=?",
        (ev_id,)).fetchone()
    std = ev['aggregate_standard_min'] if ev else None
    steps = conn.execute(
        "SELECT st.step_name, st.standard_min, es.actual_min "
        "FROM co_event_steps es JOIN co_steps_v2 st ON st.id=es.step_id "
        "WHERE es.event_id=?", (ev_id,)).fetchall()
    deltas = [(r['step_name'], r['actual_min'] - r['standard_min'])
              for r in steps if r['standard_min'] is not None and r['actual_min'] is not None]
    best = min(deltas, key=lambda x: x[1]) if deltas else None
    worst = max(deltas, key=lambda x: x[1]) if deltas else None

    s.set('pending_step_idx', None)
    s.set('co_total_min', None)
    s.set('active_changeover_id', None)
    s.set('state', 'idle')
    s.save()

    if std is None:
        msg = f"Changeover saved. Actual: {wall_clock:.0f} min. No standard on file."
    else:
        var = wall_clock - std
        flag = 'FLAG' if var > VARIANCE_THRESHOLD else 'OK'
        msg = f"Changeover saved. Total {wall_clock:.0f}m vs {std:.0f}m std ({var:+.0f}m) [{flag}]."
        if best and worst and best[0] != worst[0] and (best[1] < 0 or worst[1] > 0):
            msg += f" Best: {best[0]} {best[1]:+.0f}m. Worst: {worst[0]} {worst[1]:+.0f}m."

    line_id = ev['line_id'] if ev else (s.get('line_id') or 1)
    target_job_id = ev['to_job_id'] if ev else None
    if target_job_id:
        tj = conn.execute("SELECT job_number FROM jobs WHERE id=?", (target_job_id,)).fetchone()
        if tj:
            msg += f"\nStart the target job with: 'start {tj['job_number']}'."
    db.transition_line(conn, line_id, 'idle',
                       user_id=None)
    return msg
