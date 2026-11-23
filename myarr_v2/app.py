"""
Myarra Web Application
"""
from flask import Flask, render_template, request, redirect, url_for, Response, jsonify
from db import get_db_connection
from myarra_settings import check_llm
from onboarding import TEMPLATES, generate_csv, ingest_template, INGEST_ORDER
from recon import summary_for_window
from ask import ask as ask_question
from herbie import (get_job_summary, get_jobs_with_downtime_over,
                    get_unaccounted_minutes, get_changeover_summary,
                    get_line_summary, get_floor_context, narrate)
from datetime import datetime, timedelta
import json
import sqlite3

app = Flask(__name__)

from verify import verify_bp
app.register_blueprint(verify_bp)
from admin_ops import admin_ops_bp
app.register_blueprint(admin_ops_bp)
from views import ensure_views
_c = get_db_connection(); ensure_views(_c); _c.close()
_llm_ok, _llm_detail = check_llm()
print("Herbie LLM check: " + ("OK - " if _llm_ok else "FAIL - ") + _llm_detail, flush=True)

FISHBONE_CATEGORIES = ['Man', 'Machine', 'Method', 'Material', 'Measurement', 'Environment']
FISHBONE_MAX_PER_CATEGORY = 3

def _priority_total(e):
    return (
        (e.get("pri_time") or 0) * 10 +
        (e.get("pri_impact") or 0) * 30 +
        (e.get("pri_resources") or 0) * 30 +
        (e.get("pri_magnitude") or 0) * 30 +
        (e.get("pri_cost") or 0) * 50
    )

def _setting(conn, key, default):
    try:
        r = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r[0] if r else default
    except Exception:
        return default

def _unit_label(conn): return _setting(conn, 'unit_label', 'units')
def _case_label(conn): return _setting(conn, 'case_label', 'cases')

def _shift_start_hour(conn, shift_h):
    """First hour of a shift, taken from settings.

    Agreed 2026-11-20: shift_1_start through shift_3_start have been in the
    settings table all along and three routes hardcoded 07:00 with eight hour
    steps instead. Falls back to the old arithmetic so a plant that has set
    nothing sees no change.
    """
    try:
        r = conn.execute("SELECT value FROM settings WHERE key=?",
                         ("shift_%s_start" % shift_h,)).fetchone()
        if r and r[0]:
            return int(str(r[0]).split(":")[0])
    except Exception:
        pass
    return 7 + (shift_h - 1) * 8


def _shift_windows(conn):
    """Configured shifts as (number, start_hhmm, end_hhmm)."""
    out = []
    for i in range(1, 7):
        st = _setting(conn, "shift_%s_start" % i, None)
        en = _setting(conn, "shift_%s_end" % i, None)
        if st and en:
            out.append((i, st, en))
    return out


def _current_shift(conn, when=None):
    """Which configured shift covers this local time. Falls back to 1.

    Agreed 2026-11-20: /floor wrote shift='1' as a literal, so every tablet
    entry was attributed to shift one whatever time it was logged.
    """
    when = when or datetime.now()
    hhmm = when.strftime("%H:%M")
    for i, st, en in _shift_windows(conn):
        if st <= en:
            if st <= hhmm < en:
                return str(i)
        else:
            if hhmm >= st or hhmm < en:
                return str(i)
    return "1"


def _shift_hours(conn, shift_h):
    """Hours in a configured shift, from its start and end. Default 8.

    The report and board pages looped range(1, 9), so a ten or twelve hour
    shift produced periods that were never displayed.
    """
    st = _setting(conn, "shift_%s_start" % shift_h, None)
    en = _setting(conn, "shift_%s_end" % shift_h, None)
    if not st or not en:
        return 8
    try:
        sm = int(str(st).split(":")[0]) * 60 + int(str(st).split(":")[1])
        em = int(str(en).split(":")[0]) * 60 + int(str(en).split(":")[1])
    except (ValueError, IndexError):
        return 8
    span = (em - sm) % (24 * 60)
    if span <= 0:
        span = 24 * 60
    return max(1, span // 60)

def _load_fishbone(conn, exp_id):
    data = {cat: [] for cat in FISHBONE_CATEGORIES}
    for row in conn.execute(
        "SELECT category, cause_text FROM fishbone_causes WHERE experiment_id=? ORDER BY category, seq",
        (exp_id,)):
        if row['category'] in data and len(data[row['category']]) < FISHBONE_MAX_PER_CATEGORY:
            data[row['category']].append(row['cause_text'])
    return data

def _fishbone_text_block(fishbone):
    return {cat: '\n'.join(items) for cat, items in fishbone.items()}

def _compute_trend(conn, exp):
    baseline = None
    current = None
    events = []
    
    if exp.get('target_step_name'):
        baseline = conn.execute("""
            SELECT AVG(es.actual_min) FROM co_event_steps es
            JOIN co_steps_v2 s ON s.id = es.step_id
            JOIN co_events ev ON ev.id = es.event_id
            WHERE s.step_name = ? AND date(ev.started_at) < ?
        """, (exp['target_step_name'], exp['start_date'])).fetchone()[0]
        current = conn.execute("""
            SELECT AVG(es.actual_min) FROM co_event_steps es
            JOIN co_steps_v2 s ON s.id = es.step_id
            JOIN co_events ev ON ev.id = es.event_id
            WHERE s.step_name = ? AND date(ev.started_at) >= ?
        """, (exp['target_step_name'], exp['start_date'])).fetchone()[0]
        evs = conn.execute("""
            SELECT ev.started_at, es.actual_min, date(ev.started_at) as ev_date
            FROM co_event_steps es
            JOIN co_steps_v2 s ON s.id = es.step_id
            JOIN co_events ev ON ev.id = es.event_id
            WHERE s.step_name = ? ORDER BY ev.started_at ASC
        """, (exp['target_step_name'],)).fetchall()
        events = [{'date': e['ev_date'], 'value': e['actual_min']} for e in evs if e['actual_min'] is not None]
    else:
        baseline = conn.execute("""
            SELECT AVG(aggregate_actual_min) FROM co_events
            WHERE line_id = ? AND date(started_at) < ?
        """, (exp['line_id'], exp['start_date'])).fetchone()[0]
        current = conn.execute("""
            SELECT AVG(aggregate_actual_min) FROM co_events
            WHERE line_id = ? AND date(started_at) >= ?
        """, (exp['line_id'], exp['start_date'])).fetchone()[0]
        evs = conn.execute("""
            SELECT started_at, aggregate_actual_min as actual_min, date(started_at) as ev_date
            FROM co_events WHERE line_id = ? ORDER BY started_at ASC
        """, (exp['line_id'],)).fetchall()
        events = [{'date': e['ev_date'], 'value': e['actual_min']} for e in evs if e['actual_min'] is not None]
        
    return {'manual': False, 'baseline': baseline, 'current': current, 'target': exp.get('target_goal_min'), 'events': events}

@app.route("/")
def dashboard():
    conn = get_db_connection()
    lines = conn.execute("SELECT * FROM lines ORDER BY id").fetchall()
    cl = _case_label(conn)
    rows = []
    for line in lines:
        cur = conn.execute(
            "SELECT * FROM line_events WHERE line_id=? AND ended_at IS NULL ORDER BY started_at DESC LIMIT 1",
            (line['id'],)).fetchone()
        row = {'line_id': line['id'], 'line_name': line['name'],
               'state': 'unknown', 'details': {}, 'started_at': None, 'elapsed_min': 0,
               'hourly_data': []}

        runs = conn.execute("""
            SELECT r.period, r.units_filled, r.duration_min, s.case_pack, lsr.ideal_rate
            FROM hourly_runs r
            JOIN jobs j ON r.job_id = j.id
            JOIN skus s ON s.id = j.sku_id
            LEFT JOIN line_sku_rates lsr ON lsr.line_id = r.line_id AND lsr.sku_id = j.sku_id
            WHERE r.line_id = ? AND date(r.recorded_at) = date('now') AND (r.superseded IS NULL OR r.superseded=0)
            ORDER BY r.period
        """, (line['id'],)).fetchall()

        for run in runs:
            bpm = run['ideal_rate'] or 600.0
            target_units = bpm * run['duration_min'] / 60.0
            cp = run['case_pack'] or 1
            row['hourly_data'].append({
                'period': run['period'],
                'target_cases': int(target_units // cp),
                'actual_cases': int(run['units_filled'] // cp),
                'delta_cases': int((run['units_filled'] - target_units) // cp)
            })
        if cur:
            row['state'] = cur['state']
            try: started = datetime.fromisoformat(cur['started_at'])
            except Exception: started = datetime.now()
            row['started_at'] = started
            row['elapsed_min'] = (datetime.now() - started).total_seconds() / 60.0
            if cur['state'] == 'production' and cur['job_id']:
                job = conn.execute(
                    """SELECT j.*, s.case_pack, s.part_number, s.description
                       FROM jobs j LEFT JOIN skus s ON s.id=j.sku_id WHERE j.id=?""",
                    (cur['job_id'],)).fetchone()
                if job:
                    cp = job['case_pack'] or 1
                    units = conn.execute("SELECT SUM(units_filled) FROM hourly_runs WHERE job_id=?",
                                         (job['id'],)).fetchone()[0] or 0
                    tgt_units = job['target_quantity'] or 0
                    row['details'] = {
                        'job_number': job['job_number'],
                        'sku_description': job['description'] or '',
                        'cases': int(units // cp), 'tgt_cases': int(tgt_units // cp),
                        'pct': (units / tgt_units * 100) if tgt_units else 0}
            elif cur['state'] == 'changeover' and cur['co_event_id']:
                cev = conn.execute("SELECT * FROM co_events WHERE id=?", (cur['co_event_id'],)).fetchone()
                if cev:
                    std = None
                    if cev['procedure_id']:
                        pr = conn.execute("SELECT aggregate_standard_min FROM co_procedures_v2 WHERE id=?",
                                          (cev['procedure_id'],)).fetchone()
                        std = pr['aggregate_standard_min'] if pr else None
                    row['details'] = {'from_job': cev['from_job_number'],
                                      'to_job': cev['to_job_number'], 'std': std}
            elif cur['reason']:
                row['details'] = {'reason': cur['reason']}
        rows.append(row)
    conn.close()
    return render_template("dashboard.html", rows=rows, case_label=cl)

@app.route("/reconciliation")
def reconciliation():
    conn = get_db_connection()
    line_filter = request.args.get('line', type=int)
    days = request.args.get('days', default=7, type=int)
    summary = summary_for_window(conn, line_filter, days)
    sql = """
        SELECT j.id, j.job_number, j.line_id, l.name as line_name,
            s.part_number, s.description as sku_description, s.case_pack,
            j.target_quantity, j.status,
            MAX(date(r.recorded_at)) as last_date,
            MIN(r.shift) as shift_min, MAX(r.shift) as shift_max,
            SUM(r.units_filled) as units_filled,
            SUM(r.scrap_units) as scrap_units
        FROM jobs j
        LEFT JOIN lines l ON l.id = j.line_id
        LEFT JOIN skus s ON s.id = j.sku_id
        JOIN hourly_runs r ON r.job_id = j.id
        WHERE j.status = 'completed'
    """
    params = []
    if line_filter:
        sql += " AND j.line_id = ?"
        params.append(line_filter)
    sql += """ GROUP BY j.id
               HAVING MAX(date(r.recorded_at)) >= date('now', ?)
               ORDER BY last_date DESC, j.id DESC """
    params.append(f'-{days} days')
    raw = conn.execute(sql, params).fetchall()
    out = []
    for r in raw:
        r = dict(r)
        cp = r['case_pack'] or 1
        units = r['units_filled'] or 0
        tgt = r['target_quantity'] or 0
        r['cases'] = int(units // cp)
        r['tgt_cases'] = int(tgt // cp)
        r['variance'] = r['cases'] - r['tgt_cases']
        r['perf'] = (units / tgt * 100) if tgt else 0
        r['scrap_cases'] = int((r['scrap_units'] or 0) // cp)
        r['shift_display'] = (f"S{r['shift_min']}" if r['shift_min'] == r['shift_max']
                              else f"S{r['shift_min']}-S{r['shift_max']}")
        out.append(r)
    lines_list = conn.execute("SELECT * FROM lines ORDER BY id").fetchall()
    case_label = _case_label(conn)
    conn.close()
    return render_template("reconciliation.html", rows=out, summary=summary, lines=lines_list,
                           current_line=line_filter, days=days, case_label=case_label)

@app.route("/line/<int:line_id>/report")
def line_report(line_id):
    conn = get_db_connection()
    line = conn.execute("SELECT * FROM lines WHERE id=?", (line_id,)).fetchone()
    if not line:
        conn.close(); return "Line not found", 404

    latest = conn.execute("SELECT MAX(date(recorded_at)) as d FROM hourly_runs WHERE line_id=?", (line_id,)).fetchone()
    if not latest or not latest['d']:
        conn.close(); return "No data for this line", 404

    runs = conn.execute("""
        SELECT r.period, r.units_filled, r.duration_min, r.scrap_units, r.notes, j.sku_id, r.shift
        FROM hourly_runs r JOIN jobs j ON r.job_id = j.id
        WHERE r.line_id=? AND date(r.recorded_at)=? AND (r.superseded IS NULL OR r.superseded=0)
    """, (line_id, latest['d'])).fetchall()

    if not runs:
        conn.close(); return "No data for this line today", 404

    existing = {r['period']: dict(r) for r in runs}
    shift = runs[0]['shift'] or '1'
    shift_h = int(shift) if str(shift).isdigit() else 1
    shift_start = _shift_start_hour(conn, shift_h)

    sample_sku = runs[0]['sku_id']
    rate_row = conn.execute("SELECT ideal_rate FROM line_sku_rates WHERE line_id=? AND sku_id=?", (line_id, sample_sku)).fetchone()
    bpm = rate_row['ideal_rate'] if rate_row else 600.0
    target_per_hour = int(bpm)

    events = conn.execute("""
        SELECT state, started_at, ended_at
        FROM line_events
        WHERE line_id=? AND date(started_at)=? AND ended_at IS NOT NULL
        ORDER BY started_at
    """, (line_id, latest['d'])).fetchall()

    rows = []
    total_target = 0
    total_actual = 0
    total_scrap = 0
    target_acc = 0
    actual_acc = 0

    for pn in range(1, _shift_hours(conn, shift_h) + 1):
        period = f"H{pn}"
        duration = 60
        if period in existing and existing[period]['duration_min']:
            duration = existing[period]['duration_min']

        st = (shift_start + pn - 1) % 24
        en = (st + duration // 60) % 24
        enm = duration % 60
        label = f"{st:02d}:00 - {en:02d}:{enm:02d}"

        target = int(bpm * duration / 60.0)

        if period in existing:
            r = existing[period]
            actual = r['units_filled']
            scrap = r['scrap_units']
            comments = r['notes'] or '—'
            target_acc += target
            actual_acc += actual
            total_target += target
            total_actual += actual
            total_scrap += (scrap or 0)
            delta = actual - target
            has = True
        else:
            actual = None; scrap = None; comments = '— (pending)'
            delta = None; has = False

        rows.append({
            'hour_label': label, 'minutes': duration, 'target': target,
            'actual': actual,
            'target_acc': target_acc if has else None,
            'actual_acc': actual_acc if has else None,
            'delta': delta, 'scrap': scrap, 'comments': comments,
            'has_data': has,
        })

    conn.close()
    p2p = round((total_actual / total_target * 100), 1) if total_target else 0
    ftq = round(((total_actual - total_scrap) / total_actual * 100), 1) if total_actual else 0
    takt_time = round(3600.0 / target_per_hour, 2) if target_per_hour else 0

    return render_template("line_report.html", line=line, report_date=latest['d'],
                           shift=shift, rows=rows, total_target=total_target,
                           total_actual=total_actual, total_scrap=total_scrap, p2p=p2p, ftq=ftq,
                           takt_time=takt_time, target_per_hour=target_per_hour,
                           events=events)

@app.route("/job/<job_number>")
def job_detail(job_number):
    conn = get_db_connection()
    job = conn.execute("""
        SELECT j.*, s.part_number, s.description as sku_description, s.case_pack,
               l.name as line_name
        FROM jobs j LEFT JOIN skus s ON s.id = j.sku_id
        LEFT JOIN lines l ON l.id = j.line_id WHERE j.job_number = ?
    """, (job_number,)).fetchone()
    if not job:
        conn.close(); return "Job not found", 404
    job = dict(job)

    runs = conn.execute("""
        SELECT r.id, r.period, r.units_filled, r.scrap_units, r.duration_min, r.line_id,
               r.shift, r.recorded_at, j.sku_id, r.notes
        FROM hourly_runs r JOIN jobs j ON r.job_id = j.id
        WHERE r.job_id = ? ORDER BY r.recorded_at, r.period
    """, (job['id'],)).fetchall()
    existing = {r['period']: dict(r) for r in runs}
    
    if runs:
        shift = runs[0]['shift'] or '1'
        shift_h = int(shift) if str(shift).isdigit() else 1
        shift_start = _shift_start_hour(conn, shift_h)
        sample_sku = runs[0]['sku_id']
    else:
        shift_h = 1
        shift_start = 7
        sample_sku = job['sku_id']

    rate_row = conn.execute("SELECT ideal_rate FROM line_sku_rates WHERE line_id=? AND sku_id=?", (job['line_id'], sample_sku)).fetchone()
    bpm = rate_row['ideal_rate'] if rate_row else 600.0
    target_per_hour = int(bpm)
    takt_time = round(3600.0 / target_per_hour, 2) if target_per_hour else 0

    rows = []
    total_target = 0
    total_actual = 0
    total_scrap = 0
    total_gap = 0
    target_acc = 0
    actual_acc = 0

    for pn in range(1, _shift_hours(conn, shift_h) + 1):
        period = f"H{pn}"
        duration = 60
        if period in existing and existing[period]['duration_min']:
            duration = existing[period]['duration_min']

        st = (shift_start + pn - 1) % 24
        en = (st + duration // 60) % 24
        enm = duration % 60
        label = f"{st:02d}:00 - {en:02d}:{enm:02d}"

        target = int(bpm * duration / 60.0)

        if period in existing:
            r = existing[period]
            actual = r['units_filled']
            scrap = r['scrap_units'] or 0
            comments = r['notes'] or ''
            
            dts = conn.execute("SELECT station, reason, minutes FROM downtime_events WHERE run_id=?", (r['id'],)).fetchall()
            dt_str = ", ".join([f"{d['station']}: {d['reason']} ({round(d['minutes'],1)}m)" for d in dts])
            if dt_str:
                comments = (comments + " | " if comments else "") + dt_str

            target_acc += target
            actual_acc += actual
            total_target += target
            total_actual += actual
            total_scrap += scrap
            gap = round((target - actual) / (bpm / 60.0), 1) if bpm else 0.0
            total_gap += gap
            has = True
        else:
            actual = None; scrap = None; comments = '— (pending)'
            gap = None; has = False

        rows.append({
            'hour_label': label, 'minutes': duration, 'target': target,
            'actual': actual,
            'target_acc': target_acc if has else None,
            'actual_acc': actual_acc if has else None,
            'delta': (actual - target) if has else None, 
            'gap': gap, 'scrap': scrap, 'comments': comments,
            'has_data': has,
        })

    conn.close()
    p2p = round((total_actual / total_target * 100), 1) if total_target else 0
    ftq = round(((total_actual - total_scrap) / total_actual * 100), 1) if total_actual else 0
    cp = job['case_pack'] or 1

    return render_template("job_detail.html", job=job, rows=rows, total_target=total_target,
                           total_actual=total_actual, total_scrap=total_scrap, total_gap=total_gap,
                           p2p=p2p, ftq=ftq, takt_time=takt_time, target_per_hour=target_per_hour,
                           cases=int(total_actual // cp), tgt_cases=int(job['target_quantity'] // cp),
                           pct=(total_actual / job['target_quantity'] * 100) if job['target_quantity'] else 0)

@app.route("/changeover")
def changeover_list():
    conn = get_db_connection()
    line_filter = request.args.get('line', type=int)
    component_filter = request.args.get('component', type=int)
    days = request.args.get('days', default=30, type=int)
    sql = """
        SELECT e.id, e.line_id, l.name as line_name,
            e.from_job_number, e.to_job_number, e.started_at,
            e.aggregate_actual_min, p.aggregate_standard_min, p.name as procedure_name,
            (SELECT GROUP_CONCAT(ct.name, ', ')
             FROM co_event_changes cec
             JOIN component_types ct ON ct.id = cec.component_type_id
             WHERE cec.event_id = e.id) as components_changed
        FROM co_events e
        LEFT JOIN lines l ON l.id = e.line_id
        LEFT JOIN co_procedures_v2 p ON p.id = e.procedure_id
        WHERE e.started_at >= date('now', ?)
    """
    params = [f'-{days} days']
    if line_filter:
        sql += " AND e.line_id = ?"
        params.append(line_filter)
    if component_filter:
        sql += " AND e.id IN (SELECT event_id FROM co_event_changes WHERE component_type_id = ?)"
        params.append(component_filter)
    sql += " ORDER BY e.started_at DESC"
    raw = conn.execute(sql, params).fetchall()
    events = []
    for r in raw:
        r = dict(r)
        std = r['aggregate_standard_min']
        actual = r['aggregate_actual_min']
        r['variance'] = (actual - std) if (std is not None and actual is not None) else None
        events.append(r)
    components = conn.execute("""
        SELECT DISTINCT ct.id, ct.name
        FROM co_event_changes cec
        JOIN component_types ct ON ct.id = cec.component_type_id
        ORDER BY ct.name
    """).fetchall()
    lines_list = conn.execute("SELECT * FROM lines ORDER BY id").fetchall()
    conn.close()
    return render_template("changeover_list.html", events=events, components=components,
                           lines=lines_list, current_line=line_filter,
                           current_component=component_filter, days=days)

@app.route("/changeover/<int:event_id>")
def changeover_detail(event_id):
    conn = get_db_connection()
    ev = conn.execute("""
        SELECT e.id, p.name, p.aggregate_standard_min, e.aggregate_actual_min,
               e.started_at, e.notes, e.from_job_number, e.to_job_number, e.line_id
        FROM co_events e LEFT JOIN co_procedures_v2 p ON p.id = e.procedure_id
        WHERE e.id = ?
    """, (event_id,)).fetchone()
    if not ev:
        conn.close(); return "Changeover not found", 404
    steps = conn.execute("""
        SELECT s.step_name, s.station, s.standard_min, es.actual_min, es.note
        FROM co_event_steps es JOIN co_steps_v2 s ON s.id = es.step_id
        WHERE es.event_id = ? ORDER BY s.seq
    """, (event_id,)).fetchall()
    changes = conn.execute("""
        SELECT ct.name as component_name, cec.from_value, cec.to_value
        FROM co_event_changes cec
        JOIN component_types ct ON ct.id = cec.component_type_id
        WHERE cec.event_id = ? ORDER BY ct.name
    """, (event_id,)).fetchall()
    conn.close()
    return render_template("changeover.html", ev=ev, steps=steps, changes=changes)

@app.route("/pdca")
def pdca_view():
    conn = get_db_connection()
    exps = conn.execute("SELECT * FROM experiments WHERE status='active' ORDER BY department, line_id").fetchall()
    groups = {}
    for e in exps:
        e_dict = dict(e)
        trend = _compute_trend(conn, e_dict)
        e_dict['baseline_avg'] = trend['baseline']
        e_dict['current_avg'] = trend['current']
        e_dict['events'] = trend['events']
        e_dict['priority_total'] = _priority_total(e_dict)
        
        dept = e["department"] or "Production"
        if dept not in groups: groups[dept] = []
        groups[dept].append(e_dict)
        
    for dept in groups:
        groups[dept].sort(key=lambda x: x["priority_total"], reverse=True)
    conn.close()
    return render_template("pdca.html", groups=groups)

@app.route("/pdca/log")
def pdca_log():
    conn = get_db_connection()
    rows_raw = conn.execute("SELECT * FROM experiments").fetchall()
    conn.close()
    rows = []
    for e in rows_raw:
        d = dict(e); d["priority_total"] = _priority_total(d); rows.append(d)
    rows.sort(key=lambda r: (0 if (r.get("status") or "") == "active" else 1, -(r["priority_total"] or 0)))
    return render_template("pdca_log.html", rows=rows)

@app.route("/pdca/<int:exp_id>")
def pdca_detail(exp_id):
    conn = get_db_connection()
    ex = conn.execute("SELECT * FROM experiments WHERE id=?", (exp_id,)).fetchone()
    if not ex:
        conn.close(); return "Experiment not found", 404
    ex = dict(ex)
    actions = [dict(r) for r in conn.execute(
        "SELECT * FROM experiment_actions WHERE experiment_id=? ORDER BY seq", (exp_id,)).fetchall()]
    trend = _compute_trend(conn, ex)
    fishbone = _load_fishbone(conn, exp_id)
    conn.close()
    return render_template("a3.html", ex=ex, actions=actions,
                           priority_total=_priority_total(ex),
                           trend=trend, fishbone=fishbone,
                           fishbone_categories=FISHBONE_CATEGORIES,
                           fishbone_max=FISHBONE_MAX_PER_CATEGORY)

@app.route("/pdca/<int:exp_id>/edit", methods=["GET", "POST"])
def pdca_edit(exp_id):
    conn = get_db_connection()
    ex = conn.execute("SELECT * FROM experiments WHERE id=?", (exp_id,)).fetchone()
    if not ex:
        conn.close(); return "Experiment not found", 404
    ex = dict(ex)

    if request.method == "POST":
        f = request.form
        updates = {}
        text_fields = ['title', 'department', 'pdca_owner', 'management_sponsor',
                       'team_members', 'departments_involved', 'current_condition',
                       'target_condition', 'hypothesis', 'root_cause', 'fishbone_category',
                       'action_plan', 'action_owner', 'target_date', 'how_known_solved',
                       'new_problems_created', 'notes_on_back', 'target_step_name',
                       'affected_skus', 'measurement_type', 'measurement_config',
                       'status', 'close_reason']
        for k in text_fields:
            if k in f:
                updates[k] = f[k] if f[k] != '' else None
        int_fields = ['line_id', 'problem_severity', 'target_state_reached',
                      'pri_time', 'pri_impact', 'pri_resources', 'pri_magnitude', 'pri_cost']
        for k in int_fields:
            if k in f and f[k] != '':
                try: updates[k] = int(f[k])
                except ValueError: pass
        float_fields = ['standard_min', 'target_goal_min', 'baseline_value']
        for k in float_fields:
            if k in f and f[k] != '':
                try: updates[k] = float(f[k])
                except ValueError: pass
        if updates.get('status') == 'closed':
            updates['closed_at'] = datetime.now().isoformat()
        updates['updated_at'] = datetime.now().isoformat()
        set_clause = ', '.join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [exp_id]
        conn.execute(f"UPDATE experiments SET {set_clause} WHERE id=?", vals)

        conn.execute("DELETE FROM fishbone_causes WHERE experiment_id=?", (exp_id,))
        for cat in FISHBONE_CATEGORIES:
            field = f"fishbone_{cat}"
            if field in f:
                lines = [l.strip() for l in f[field].split('\n') if l.strip()][:FISHBONE_MAX_PER_CATEGORY]
                for seq, line in enumerate(lines):
                    conn.execute(
                        "INSERT INTO fishbone_causes (experiment_id, category, cause_text, seq, created_at) VALUES (?,?,?,?,?)",
                        (exp_id, cat, line, seq, datetime.now().isoformat()))
        conn.commit(); conn.close()
        return redirect(url_for('pdca_detail', exp_id=exp_id))

    lines_list = conn.execute("SELECT * FROM lines ORDER BY id").fetchall()
    fishbone = _load_fishbone(conn, exp_id)
    fishbone_text = _fishbone_text_block(fishbone)
    conn.close()
    return render_template("a3_edit.html", ex=ex,
                           priority_total=_priority_total(ex),
                           lines=lines_list, fishbone_text=fishbone_text,
                           fishbone_categories=FISHBONE_CATEGORIES,
                           fishbone_max=FISHBONE_MAX_PER_CATEGORY)

@app.route("/maintenance")
def maintenance_list():
    conn = get_db_connection()
    line_filter = request.args.get('line', type=int)
    station_filter = request.args.get('station')
    days = request.args.get('days', default=30, type=int)
    sql = """
        SELECT m.*, l.name as line_name, j.job_number
        FROM maintenance_events m
        LEFT JOIN lines l ON l.id = m.line_id
        LEFT JOIN jobs j ON j.id = m.job_id
        WHERE m.started_at >= date('now', ?)
    """
    params = [f'-{days} days']
    if line_filter:
        sql += " AND m.line_id = ?"
        params.append(line_filter)
    if station_filter:
        sql += " AND m.station = ?"
        params.append(station_filter)
    sql += " ORDER BY m.started_at DESC"
    events = [dict(r) for r in conn.execute(sql, params).fetchall()]
    stations = [r[0] for r in conn.execute(
        "SELECT DISTINCT station FROM maintenance_events WHERE station IS NOT NULL ORDER BY station"
    ).fetchall()]
    lines_list = conn.execute("SELECT * FROM lines ORDER BY id").fetchall()
    conn.close()
    return render_template("maintenance_list.html", events=events, stations=stations,
                           lines=lines_list, current_line=line_filter,
                           current_station=station_filter, days=days)

@app.route("/maintenance/<int:event_id>", methods=["GET", "POST"])
def maintenance_detail(event_id):
    conn = get_db_connection()
    ev = conn.execute("""
        SELECT m.*, l.name as line_name, j.job_number
        FROM maintenance_events m
        LEFT JOIN lines l ON l.id = m.line_id
        LEFT JOIN jobs j ON j.id = m.job_id
        WHERE m.id = ?
    """, (event_id,)).fetchone()
    if not ev:
        conn.close(); return "Maintenance event not found", 404
    if request.method == "POST":
        f = request.form
        upd = {}
        for k in ['symptom', 'resolution', 'parts_used', 'technician',
                  'called_by', 'reason_code', 'notes', 'category']:
            if k in f:
                upd[k] = f[k] or None
        if upd:
            set_clause = ', '.join(f"{k}=?" for k in upd)
            conn.execute(f"UPDATE maintenance_events SET {set_clause} WHERE id=?",
                         list(upd.values()) + [event_id])
            conn.commit()
        conn.close()
        return redirect(url_for('maintenance_detail', event_id=event_id))
    conn.close()
    return render_template("maintenance.html", ev=dict(ev))

@app.route("/setup", methods=["GET", "POST"])
def setup():
    msg = None
    reports = []
    if request.method == "POST":
        conn = get_db_connection()
        try:
            for tname in INGEST_ORDER:
                if tname not in request.files:
                    continue
                file = request.files[tname]
                if not file or not file.filename:
                    continue
                result = ingest_template(conn, tname, file, full_replace=(request.form.get('full_replace') == 'on'))
                result["template"] = tname
                reports.append(result)
        finally:
            conn.close()
        if reports:
            total_failed = sum(r["failed"] for r in reports)
            if total_failed == 0:
                msg = f"Upload complete. All rows succeeded across {len(reports)} template(s)."
            else:
                msg = f"Upload complete with errors. {total_failed} row(s) failed across {len(reports)} template(s). See report below."
        else:
            msg = "No files were selected."

    conn = get_db_connection()
    stats = {
        "lines": conn.execute("SELECT COUNT(*) FROM lines").fetchone()[0],
        "skus":  conn.execute("SELECT COUNT(*) FROM skus").fetchone()[0],
        "jobs":  conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
    }
    conn.close()
    return render_template("setup.html", stats=stats, msg=msg,
                           templates=TEMPLATES, reports=reports)

@app.route("/setup/download/<name>")
def setup_download(name):
    if name not in TEMPLATES:
        return "Template not found", 404
    csv_text = generate_csv(name)
    t = TEMPLATES[name]
    return Response(
        csv_text,
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{t["filename"]}"'}
    )

@app.route("/admin", methods=["GET", "POST"])
def admin_view():
    conn = get_db_connection(); msg = None
    if request.method == "POST":
        name = request.form.get("name"); role = request.form.get("role")
        line_id = request.form.get("line_id"); tg_id = request.form.get("telegram_id")
        if name and tg_id:
            try:
                conn.execute("INSERT INTO users (name, role, line_id, telegram_id) VALUES (?, ?, ?, ?)",
                             (name, role, line_id if line_id else None, tg_id))
                conn.commit()
                msg = f"User {name} added successfully."
            except Exception as e:
                msg = f"Error: {e}"
    users = conn.execute("SELECT * FROM users WHERE active=1").fetchall()
    conn.close()
    return render_template("admin.html", users=users, msg=msg)

@app.route("/shift/<run_date>/<shift>")
def shift_detail(run_date, shift):
    conn = get_db_connection(); unit = _unit_label(conn)
    runs = conn.execute("""
        SELECT r.id, r.period, r.units_filled, r.duration_min, r.line_id,
               j.job_number, j.sku_id
        FROM hourly_runs r JOIN jobs j ON r.job_id = j.id
        WHERE date(r.recorded_at) = ? AND r.shift = ? ORDER BY r.period
    """, (run_date, shift)).fetchall()
    details = []
    for r in runs:
        rate = conn.execute("SELECT ideal_rate FROM line_sku_rates WHERE line_id=? AND sku_id=?",
                            (r["line_id"], r["sku_id"])).fetchone()
        rpm = rate["ideal_rate"] if rate else 600.0
        expected = rpm * r["duration_min"] / 60.0
        gap = (expected - r["units_filled"]) / (rpm / 60.0) if rpm else 0.0
        dts = conn.execute("SELECT station, reason, minutes FROM downtime_events WHERE run_id=?",
                           (r["id"],)).fetchall()
        details.append({"period": r["period"], "job_number": r["job_number"],
                        "expected": expected, "actual": r["units_filled"], "gap": gap,
                        "downtime": [{"station": d["station"], "reason": d["reason"],
                                      "minutes": round(d["minutes"], 1)} for d in dts]})
    conn.close()
    return render_template("shift_detail.html", run_date=run_date, shift=shift,
                           details=details, unit=unit)

@app.route("/api/odoo/jobs", methods=["POST"])
def api_odoo_jobs():
    token = request.headers.get("X-Myarra-Token")
    if token != "MYARRA-ODOO-SECRET":
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    if not isinstance(data, list):
        return jsonify({"error": "Expected a JSON array of jobs"}), 400

    conn = get_db_connection()
    imported = 0
    errors = []

    for job in data:
        try:
            job_no = job.get("job_number")
            sku_part = job.get("part_number")
            line_name = job.get("line_name")
            target_qty = job.get("target_quantity", 0)

            if not job_no or not sku_part:
                errors.append(f"Missing job_number or part_number")
                continue

            sku = conn.execute("SELECT id FROM skus WHERE part_number=?", (sku_part,)).fetchone()
            if not sku:
                errors.append(f"SKU not found: {sku_part}")
                continue

            line = conn.execute("SELECT id FROM lines WHERE name=?", (line_name,)).fetchone()
            line_id = line['id'] if line else 1

            conn.execute("""
                INSERT INTO jobs (job_number, sku_id, line_id, target_quantity, scheduled_start, scheduled_end, status)
                VALUES (?, ?, ?, ?, ?, ?, 'scheduled')
                ON CONFLICT(job_number) DO UPDATE SET
                    target_quantity=excluded.target_quantity,
                    scheduled_start=excluded.scheduled_start,
                    scheduled_end=excluded.scheduled_end
            """, (job_no, sku['id'], line_id, target_qty, job.get("scheduled_start"), job.get("scheduled_end")))
            imported += 1
        except Exception as e:
            errors.append(f"Job {job.get('job_number', '?')}: {str(e)}")

    conn.commit()
    conn.close()
    return jsonify({"imported": imported, "errors": errors}), 200

@app.route("/board/<int:line_id>")
def board(line_id):
    conn = get_db_connection()
    line = conn.execute("SELECT * FROM lines WHERE id=?", (line_id,)).fetchone()
    if not line:
        conn.close(); return "Line not found", 404

    latest = conn.execute("SELECT MAX(date(recorded_at)) as d FROM hourly_runs WHERE line_id=?", (line_id,)).fetchone()
    if not latest or not latest['d']:
        conn.close()
        return render_template("board.html", line=line, rows=[], total_target=0, total_actual=0, p2p=0, ftq=0, takt_time=0, bpm=0, current_date=datetime.now().strftime('%Y-%m-%d'), active_job="No Active Job")

    runs = conn.execute("""
        SELECT r.period, r.units_filled, r.duration_min, r.scrap_units, r.notes, j.sku_id, r.shift, j.job_number, s.case_pack
        FROM hourly_runs r
        JOIN jobs j ON r.job_id = j.id
        JOIN skus s ON s.id = j.sku_id
        WHERE r.line_id=? AND date(r.recorded_at)=? AND (r.superseded IS NULL OR r.superseded=0)
    """, (line_id, latest['d'])).fetchall()

    if not runs:
        conn.close()
        return render_template("board.html", line=line, rows=[], total_target=0, total_actual=0, p2p=0, ftq=0, takt_time=0, bpm=0, current_date=datetime.now().strftime('%Y-%m-%d'), active_job="No Active Job")

    existing = {r['period']: dict(r) for r in runs}
    shift = runs[0]['shift'] or '1'
    shift_h = int(shift) if str(shift).isdigit() else 1
    shift_start = _shift_start_hour(conn, shift_h)

    sample_sku = runs[0]['sku_id']
    rate_row = conn.execute("SELECT ideal_rate FROM line_sku_rates WHERE line_id=? AND sku_id=?", (line_id, sample_sku)).fetchone()
    bpm = rate_row['ideal_rate'] if rate_row else 600.0
    takt_time = round(3600.0 / bpm, 2) if bpm else 0

    rows = []
    total_target = 0
    total_actual = 0
    total_scrap = 0
    target_acc = 0
    actual_acc = 0

    for pn in range(1, _shift_hours(conn, shift_h) + 1):
        period = f"H{pn}"
        duration = 60
        if period in existing and existing[period]['duration_min']:
            duration = existing[period]['duration_min']

        st = (shift_start + pn - 1) % 24
        en = (st + duration // 60) % 24
        enm = duration % 60
        label = f"{st:02d}:00 - {en:02d}:{enm:02d}"

        cp = runs[0]['case_pack'] or 1
        target_units = bpm * duration / 60.0
        target = int(target_units / cp)

        if period in existing:
            r = existing[period]
            actual = int(r['units_filled'] / cp)
            scrap = int((r['scrap_units'] or 0) / cp)
            comments = r['notes'] or ''
            target_acc += target
            actual_acc += actual
            total_target += target
            total_actual += actual
            total_scrap += scrap
            delta = actual - target
            has = True
        else:
            actual = None
            comments = '— (pending)'
            delta = None
            has = False

        rows.append({
            'period': label, 'target': target, 'actual': actual,
            'target_acc': target_acc if has else None,
            'actual_acc': actual_acc if has else None,
            'delta': delta, 'scrap': scrap if has else None, 'notes': comments, 'has_data': has,
        })

    active_job = runs[0]['job_number'] if runs else 'No Active Job'
    conn.close()
    p2p = round((total_actual / total_target * 100), 1) if total_target else 0
    ftq = round(((total_actual - total_scrap) / total_actual * 100), 1) if total_actual else 0

    return render_template("board.html", line=line, rows=rows, total_target=total_target, total_actual=total_actual, p2p=p2p, ftq=ftq, takt_time=takt_time, bpm=bpm, current_date=latest['d'], active_job=active_job)

@app.route("/ask", methods=["GET", "POST"])
def ask_view():
    result = None
    question = None
    if request.method == "POST":
        question = (request.form.get("question") or "").strip()
        if question:
            result = ask_question(question)
    return render_template("ask.html", question=question, result=result)

@app.route("/herbie", methods=["GET", "POST"])
def herbie_view():
    today = datetime.now().strftime("%Y-%m-%d")
    result = None
    if request.method == "POST":
        intent = request.form.get("intent")
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        try:
            if intent == "job":
                job_number = (request.form.get("job_number") or "").strip()
                stats = get_job_summary(conn, job_number)
                if "error" in stats:
                    result = {"narrative": stats["error"], "source": "error"}
                else:
                    result = narrate("job", stats, None, "Summarize job " + job_number + ".")
            elif intent == "jobs_over":
                threshold = int(request.form.get("threshold_min") or 20)
                days = int(request.form.get("jobs_over_days") or 7)
                stats = get_jobs_with_downtime_over(conn, threshold, days)
                result = narrate("jobs_over", stats, None, "Which jobs had more than " + str(threshold) + " minutes of downtime in the last " + str(days) + " days?")
            elif intent == "unaccounted":
                line_id = int(request.form.get("unaccounted_line_id") or 1)
                days = int(request.form.get("unaccounted_days") or 7)
                shift = request.form.get("shift") or None
                stats = get_unaccounted_minutes(conn, line_id, days, shift)
                result = narrate("unaccounted", stats, None, "How much unaccounted time on Line " + str(line_id) + " in the last " + str(days) + " days?")
            elif intent == "changeover":
                job_number = (request.form.get("changeover_job_number") or "").strip()
                stats = get_changeover_summary(conn, job_number)
                if "error" in stats:
                    result = {"narrative": stats["error"], "source": "error"}
                else:
                    result = narrate("changeover", stats, None, "How did the changeover to job " + job_number + " go?")
            elif intent == "line_day":
                line_id = int(request.form.get("line_day_line_id") or 1)
                date = request.form.get("date") or today
                stats = get_line_summary(conn, line_id, date)
                context = get_floor_context(conn, line_id, date)
                result = narrate("line_day", stats, context, "What happened on Line " + str(line_id) + " on " + date + "?")
        finally:
            conn.close()
        
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(result or {"narrative": "No result.", "source": "error"})
    
    conn2 = get_db_connection()
    recent = [r["job_number"] for r in conn2.execute(
        """SELECT DISTINCT j.job_number FROM jobs j
           JOIN hourly_runs r ON r.job_id = j.id
           WHERE (r.superseded IS NULL OR r.superseded = 0)
           ORDER BY j.id DESC LIMIT 30"""
    ).fetchall()]
    co_jobs = [r["to_job_number"] for r in conn2.execute(
        """SELECT DISTINCT to_job_number FROM co_events
           WHERE to_job_number IS NOT NULL
           ORDER BY started_at DESC LIMIT 20"""
    ).fetchall()]
    conn2.close()
    return render_template("herbie.html", today=today, result=result,
                           recent_jobs=recent, co_jobs=co_jobs)


def _floor_action(form):
    """Dispatcher for the floor tablet's buttons. Returns a redirect to /floor.

    The record form posts no action field, so it never arrives here and the
    hourly record path below is untouched. Start is the only action wired so
    far; end, lunch, maintenance and CIP join it in the same shape.

    bot is imported inside the function on purpose. A failure in the bot
    package must never stop the web app from booting on a running appliance.
    """
    from bot import jobs as bot_jobs

    action = (form.get("action") or "").strip()
    try:
        line_id = int(form.get("line_id") or 0)
    except (TypeError, ValueError):
        line_id = 0

    conn = get_db_connection()
    try:
        if action == "start":
            msg = _floor_start(conn, form, line_id, bot_jobs)
        elif action == "end":
            msg = _floor_end(conn, form, line_id, bot_jobs)
        elif action == "toggle":
            msg = _floor_toggle(conn, form, line_id, bot_jobs)
        else:
            msg = "Unknown action: " + action
    except Exception as e:
        msg = "Floor " + action + " failed: " + str(e)
    finally:
        conn.close()

    return redirect(url_for("floor_view", msg=msg, line=line_id or None))


def _floor_start(conn, form, line_id, bot_jobs):
    """Start one job on one line, through bot.jobs.start_job.

    start_job writes the job status and the line event in one transaction, so a
    crash cannot leave the job running with no event (A06) or the line closed
    and unopened (A47). The three refusals come from check_start, which this
    route and the bot both use; nothing is re-implemented here.
    """
    job_number = (form.get("job_number") or "").strip()
    operator_raw = (form.get("operator_id") or "").strip()
    reason = (form.get("reason") or "").strip() or None

    if not line_id:
        return "No line selected."
    if not job_number:
        return "Type or choose a job number."

    row = conn.execute(
        "SELECT * FROM jobs WHERE job_number = ? COLLATE NOCASE",
        (job_number,)).fetchone()
    if not row:
        return "Job " + job_number + " not found."
    # check_start calls job.get(), and a sqlite3.Row has no .get(): the failure
    # would arrive as "Error: 'sqlite3.Row' object has no attribute 'get'" in
    # the message bar with nothing in the log. Convert before it is called.
    job = dict(row)

    try:
        user_id = int(operator_raw) if operator_raw else None
    except (TypeError, ValueError):
        user_id = None

    refusal = bot_jobs.start_job(conn, job, line_id, user_id=user_id,
                                 source="floor", reason=reason)
    if refusal:
        return refusal

    moved = job.get("line_id") != line_id
    return ("Started " + job["job_number"] + " on Line " + str(line_id)
            + (" (moved from Line " + str(job.get("line_id")) + ")" if moved else "")
            + ".")

def _floor_end(conn, form, line_id, bot_jobs):
    """End the job running on a line, through bot.jobs.end_job.

    The reason is optional and always available, so a lead who already knows
    the job missed can say why before pressing rather than being sent back for
    it. end_job decides whether the reason was needed, and only a reason that
    was needed flags the job.
    """
    job_number = (form.get("job_number") or "").strip()
    operator_raw = (form.get("operator_id") or "").strip()
    reason = (form.get("reason") or "").strip() or None

    if not line_id:
        return "No line selected."
    if not job_number:
        return "No job on that line."

    row = conn.execute(
        "SELECT * FROM jobs WHERE job_number = ? COLLATE NOCASE",
        (job_number,)).fetchone()
    if not row:
        return "Job " + job_number + " not found."
    job = dict(row)

    try:
        user_id = int(operator_raw) if operator_raw else None
    except (TypeError, ValueError):
        user_id = None

    refusal = bot_jobs.end_job(conn, job, line_id, user_id=user_id,
                               source="floor", reason=reason)
    if refusal:
        return refusal
    return "Ended " + job["job_number"] + " on Line " + str(line_id) + "."

def _floor_toggle(conn, form, line_id, bot_jobs):
    """Throw lunch, maintenance or CIP, or throw it back.

    One form with three submit buttons, so the pressed button supplies the
    state and a single operator picker serves all three. toggle_line_state
    returns a sentence either way and it goes straight to the message bar.
    """
    state = (form.get("state") or "").strip().lower()
    operator_raw = (form.get("operator_id") or "").strip()

    if not line_id:
        return "No line selected."
    try:
        user_id = int(operator_raw) if operator_raw else None
    except (TypeError, ValueError):
        user_id = None

    return bot_jobs.toggle_line_state(conn, line_id, state, user_id=user_id,
                                      source="floor")


def _floor_today_jobs(conn, line_id):
    """Jobs worth offering in the start dropdown for one line.

    The day's work orders first, then anything else still open, because a
    second job in the queue not being ready and the third being run is normal
    and needs no permission (FLOOR-MODEL, Choosing the job). Completed jobs are
    left out: check_start refuses them, so offering one is a tap that cannot
    work.
    """
    return conn.execute("""
        SELECT j.job_number, j.status, j.scheduled_start,
               s.part_number, s.description
        FROM jobs j LEFT JOIN skus s ON s.id = j.sku_id
        WHERE j.line_id = ?
          AND (j.status IS NULL OR lower(j.status) != 'completed')
        ORDER BY CASE WHEN date(j.scheduled_start) = date('now') THEN 0
                      WHEN j.scheduled_start IS NULL THEN 2 ELSE 1 END,
                 j.scheduled_start, j.id
        LIMIT 25
    """, (line_id,)).fetchall()

@app.route("/floor", methods=["GET", "POST"])
def floor_view():
    if request.method == "POST" and (request.form.get("action") or "").strip():
        return _floor_action(request.form)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    msg = None
    selected_line = None
    if request.method == "POST":
        try:
            line_id = int(request.form.get("line_id") or 0)
            job_number = (request.form.get("job_number") or "").strip()
            period = (request.form.get("period") or "").strip()
            units_raw = (request.form.get("units_filled") or "").strip()
            scrap_raw = (request.form.get("scrap_units") or "").strip()
            minutes_raw = (request.form.get("duration_min") or "").strip()
            operator_raw = (request.form.get("operator_id") or "").strip()
            notes = (request.form.get("notes") or "").strip()

            if not units_raw:
                msg = "Units filled is required. Enter 0 if the line was down."
            elif not (line_id and job_number and period):
                msg = "Missing required fields."
            else:
                units = int(units_raw)
                scrap = int(scrap_raw) if scrap_raw else 0
                minutes = int(minutes_raw) if minutes_raw else 60
                try:
                    operator_id = int(operator_raw) if operator_raw else None
                except ValueError:
                    operator_id = None
                job = conn.execute(
                    "SELECT id, sku_id, line_id FROM jobs WHERE job_number = ? COLLATE NOCASE",
                    (job_number,)
                ).fetchone()
                if not job:
                    msg = f"Job {job_number} not found."
                else:
                    now = datetime.now()
                    conn.execute("""
                        INSERT INTO hourly_runs
                        (job_id, line_id, sku_id, shift, period, recorded_at,
                         units_filled, scrap_units, duration_min, notes,
                         source, user_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'floor', ?)
                    """, (job["id"], line_id, job["sku_id"],
                          _current_shift(conn, now), period, now.isoformat(),
                          units, scrap, minutes, notes, operator_id))
                    conn.commit()
                    who = ""
                    if operator_id:
                        u = conn.execute("SELECT name FROM users WHERE id=?",
                                         (operator_id,)).fetchone()
                        if u:
                            who = " by " + u[0]
                    msg = (f"Logged {period} for {job_number}: {units:,} units, "
                           f"{scrap} scrap, {minutes} min{who}.")
                    selected_line = line_id
        except Exception as e:
            msg = f"Error: {e}"

    lines = conn.execute("SELECT * FROM lines ORDER BY id").fetchall()
    cards = []
    for line in lines:
        cur = conn.execute(
            "SELECT * FROM line_events WHERE line_id=? AND ended_at IS NULL ORDER BY started_at DESC LIMIT 1",
            (line["id"],)
        ).fetchone()
        card = {
            "line_id": line["id"],
            "line_name": line["name"],
            "state": "idle",
            "job_number": None,
            "next_period": "H1",
            "sku_description": None,
            "state_since": None,
        }
        if cur and cur["state"] == "production" and cur["job_id"]:
            job = conn.execute(
                "SELECT j.*, s.description as sku_description FROM jobs j LEFT JOIN skus s ON s.id = j.sku_id WHERE j.id = ?",
                (cur["job_id"],)
            ).fetchone()
            if job:
                card["state"] = "production"
                card["job_number"] = job["job_number"]
                card["sku_description"] = job["sku_description"]
                last = conn.execute(
                    "SELECT MAX(period) as p FROM hourly_runs WHERE job_id = ? AND date(recorded_at) = date('now')",
                    (job["id"],)
                ).fetchone()
                if last and last["p"] and last["p"].startswith("H"):
                    try:
                        n = int(last["p"][1:]) + 1
                        card["next_period"] = f"H{n}"
                    except ValueError:
                        pass
        elif cur and cur["state"] in ("lunch", "maintenance", "cip"):
            # A line in lunch is not an idle line. Without this it renders as
            # idle, offers a Start panel, and check_start then refuses with a
            # sentence about a job the operator was never shown.
            card["state"] = cur["state"]
            card["state_since"] = cur["started_at"]
            if cur["job_id"]:
                off_job = conn.execute(
                    "SELECT job_number FROM jobs WHERE id = ?",
                    (cur["job_id"],)).fetchone()
                if off_job:
                    card["job_number"] = off_job["job_number"]
        cards.append(card)
    operators = {}
    for u in conn.execute("SELECT id, name, line_id FROM users WHERE active=1 "
                          "ORDER BY name").fetchall():
        operators.setdefault(u["line_id"], []).append({"id": u["id"], "name": u["name"]})
    jobs_by_line = {c["line_id"]: _floor_today_jobs(conn, c["line_id"])
                    for c in cards if c["state"] != "production"}
    conn.close()
    return render_template("floor.html", cards=cards, msg=msg, operators=operators,
                           today=datetime.now().strftime("%Y-%m-%d"),
                           selected_line=selected_line, jobs_by_line=jobs_by_line)


@app.route("/favicon.ico")
def favicon():
    from flask import send_from_directory
    return send_from_directory(app.static_folder, "favicon.png", mimetype="image/png")

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=5002)