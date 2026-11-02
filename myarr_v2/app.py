"""
Myarra Web Application
"""
from flask import Flask, render_template, request, redirect, url_for
from db import get_db_connection, ingest_csv
from datetime import datetime, timedelta
import json

app = Flask(__name__)


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


def _compute_trend(conn, exp):
    """Return baseline, current, target, event trajectory for the experiment.
    Handles changeover_sku_pair only. Others return manual values."""
    mt = exp.get('measurement_type') or 'manual'
    if mt == 'manual':
        return {'manual': True,
                'baseline': exp.get('baseline_value'),
                'current': None,
                'target': exp.get('target_goal_min'),
                'events': []}
    if mt != 'changeover_sku_pair':
        return {'manual': True,
                'baseline': exp.get('baseline_value'),
                'current': None,
                'target': exp.get('target_goal_min'),
                'events': [],
                'note': f"Trend not yet auto-computed for {mt}"}

    try:
        cfg = json.loads(exp.get('measurement_config') or '{}')
    except Exception:
        cfg = {}
    line_id = cfg.get('line_id')
    from_sku = cfg.get('from_sku')
    to_sku = cfg.get('to_sku')
    if not (line_id and from_sku and to_sku):
        return {'manual': True, 'baseline': None, 'current': None,
                'target': exp.get('target_goal_min'), 'events': [],
                'note': 'measurement_config incomplete'}
    proc = conn.execute(
        "SELECT id, aggregate_standard_min FROM co_procedures_v2 WHERE line_id=? AND from_sku_id=? AND to_sku_id=?",
        (line_id, from_sku, to_sku)).fetchone()
    if not proc:
        return {'manual': True, 'baseline': None, 'current': None,
                'target': exp.get('target_goal_min'), 'events': [],
                'note': 'No procedure matches this SKU pair'}
    start = exp.get('start_date') or '1900-01-01'

    baseline_row = conn.execute(
        "SELECT AVG(aggregate_actual_min), COUNT(*) FROM co_events WHERE procedure_id=? AND date(started_at) < ?",
        (proc['id'], start)).fetchone()
    baseline = baseline_row[0] if baseline_row and baseline_row[0] else None
    baseline_count = baseline_row[1] if baseline_row else 0

    events = conn.execute(
        "SELECT date(started_at) as d, aggregate_actual_min as v FROM co_events "
        "WHERE procedure_id=? AND date(started_at) >= ? ORDER BY started_at",
        (proc['id'], start)).fetchall()
    current = None
    if events:
        current = sum(e['v'] for e in events) / len(events)

    return {
        'manual': False,
        'baseline': baseline,
        'baseline_count': baseline_count,
        'current': current,
        'target': exp.get('target_goal_min'),
        'std': proc['aggregate_standard_min'],
        'events': [{'date': e['d'], 'value': e['v']} for e in events],
    }


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
               'state': 'unknown', 'details': {}, 'started_at': None, 'elapsed_min': 0}
        if cur:
            row['state'] = cur['state']
            try: started = datetime.fromisoformat(cur['started_at'])
            except Exception: started = datetime.now()
            row['started_at'] = started
            row['elapsed_min'] = (datetime.now() - started).total_seconds() / 60.0
            if cur['state'] == 'production' and cur['job_id']:
                job = conn.execute(
                    """SELECT j.*, s.case_pack, s.part_number, s.description
                       FROM jobs j LEFT JOIN skus s ON s.id=j.sku_id
                       WHERE j.id=?""", (cur['job_id'],)).fetchone()
                if job:
                    cp = job['case_pack'] or 1
                    units = conn.execute(
                        "SELECT SUM(units_filled) FROM hourly_runs WHERE job_id=?",
                        (job['id'],)).fetchone()[0] or 0
                    tgt_units = job['target_quantity'] or 0
                    row['details'] = {
                        'job_number': job['job_number'],
                        'sku_description': job['description'] or '',
                        'cases': int(units // cp),
                        'tgt_cases': int(tgt_units // cp),
                        'pct': (units / tgt_units * 100) if tgt_units else 0,
                    }
            elif cur['state'] == 'changeover' and cur['co_event_id']:
                cev = conn.execute("SELECT * FROM co_events WHERE id=?", (cur['co_event_id'],)).fetchone()
                if cev:
                    std = None
                    if cev['procedure_id']:
                        pr = conn.execute(
                            "SELECT aggregate_standard_min FROM co_procedures_v2 WHERE id=?",
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
    days = request.args.get('days', default=3, type=int)
    sql = """
        SELECT j.id, j.job_number, j.line_id, l.name as line_name,
            s.part_number, s.description as sku_description, s.case_pack,
            j.target_quantity, j.status,
            MAX(date(r.recorded_at)) as last_date,
            MIN(r.shift) as shift_min, MAX(r.shift) as shift_max,
            SUM(r.units_filled) as units_filled
        FROM jobs j
        LEFT JOIN lines l ON l.id = j.line_id
        LEFT JOIN skus s ON s.id = j.sku_id
        JOIN hourly_runs r ON r.job_id = j.id
        WHERE j.status IN ('running', 'completed', 'paused')
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
        r['shift_display'] = (f"S{r['shift_min']}" if r['shift_min'] == r['shift_max']
                              else f"S{r['shift_min']}-S{r['shift_max']}")
        out.append(r)
    lines_list = conn.execute("SELECT * FROM lines ORDER BY id").fetchall()
    case_label = _case_label(conn)
    conn.close()
    return render_template("reconciliation.html", rows=out, lines=lines_list,
                           current_line=line_filter, days=days, case_label=case_label)


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
        SELECT r.id, r.period, r.units_filled, r.duration_min, r.line_id,
               r.shift, r.recorded_at, j.sku_id
        FROM hourly_runs r JOIN jobs j ON r.job_id = j.id
        WHERE r.job_id = ? ORDER BY r.recorded_at, r.period
    """, (job['id'],)).fetchall()
    details = []
    for r in runs:
        rate = conn.execute(
            "SELECT ideal_rate FROM line_sku_rates WHERE line_id=? AND sku_id=?",
            (r["line_id"], r["sku_id"])).fetchone()
        rpm = rate["ideal_rate"] if rate else 600.0
        expected = rpm * r["duration_min"] / 60.0
        gap = (expected - r["units_filled"]) / (rpm / 60.0) if rpm else 0.0
        dts = conn.execute("SELECT station, reason, minutes FROM downtime_events WHERE run_id=?",
                           (r["id"],)).fetchall()
        details.append({"period": r["period"], "shift": r["shift"],
                        "date": (r["recorded_at"] or "")[:10],
                        "expected": expected, "actual": r["units_filled"], "gap": gap,
                        "downtime": [{"station": d["station"], "reason": d["reason"],
                                      "minutes": round(d["minutes"], 1)} for d in dts]})
    cp = job['case_pack'] or 1
    total_units = sum(d["actual"] for d in details)
    tgt_units = job['target_quantity'] or 0
    conn.close()
    return render_template("job_detail.html", job=job, details=details,
                           cases=int(total_units // cp), tgt_cases=int(tgt_units // cp),
                           pct=(total_units / tgt_units * 100) if tgt_units else 0,
                           unit_label=_unit_label(conn) if False else 'units',
                           case_label=_case_label(conn) if False else 'cases')


@app.route("/changeover")
def changeover_view():
    conn = get_db_connection()
    ev = conn.execute("""
        SELECT e.id, p.name, p.aggregate_standard_min, e.aggregate_actual_min,
               e.started_at, e.notes, e.from_job_number, e.to_job_number
        FROM co_events e JOIN co_procedures_v2 p ON p.id = e.procedure_id
        ORDER BY e.started_at DESC LIMIT 1
    """).fetchone()
    if not ev:
        conn.close(); return "No changeover data found."
    steps = conn.execute("""
        SELECT s.step_name, s.station, s.standard_min, es.actual_min, es.note
        FROM co_event_steps es JOIN co_steps_v2 s ON s.id = es.step_id
        WHERE es.event_id = ? ORDER BY s.seq
    """, (ev["id"],)).fetchall()
    conn.close()
    return render_template("changeover.html", ev=ev, steps=steps)


@app.route("/pdca")
def pdca_view():
    conn = get_db_connection()
    exps = conn.execute("""
        SELECT * FROM experiments WHERE status='active'
        ORDER BY department, line_id
    """).fetchall()
    groups = {}
    for e in exps:
        e_dict = dict(e)
        baseline_avg = conn.execute("""
            SELECT AVG(es.actual_min) FROM co_event_steps es
            JOIN co_steps_v2 s ON s.id = es.step_id
            JOIN co_events ev ON ev.id = es.event_id
            WHERE s.step_name = ? AND date(ev.started_at) < ?
        """, (e["target_step_name"], e["start_date"])).fetchone()[0]
        exp_avg = conn.execute("""
            SELECT AVG(es.actual_min) FROM co_event_steps es
            JOIN co_steps_v2 s ON s.id = es.step_id
            JOIN co_events ev ON ev.id = es.event_id
            WHERE s.step_name = ? AND date(ev.started_at) >= ?
        """, (e["target_step_name"], e["start_date"])).fetchone()[0]
        events = conn.execute("""
            SELECT ev.started_at, es.actual_min, date(ev.started_at) as ev_date
            FROM co_event_steps es
            JOIN co_steps_v2 s ON s.id = es.step_id
            JOIN co_events ev ON ev.id = es.event_id
            WHERE s.step_name = ? ORDER BY ev.started_at ASC
        """, (e["target_step_name"],)).fetchall()
        e_dict["baseline_avg"] = baseline_avg
        e_dict["current_avg"] = exp_avg
        e_dict["events"] = [dict(ev) for ev in events]
        e_dict["priority_total"] = _priority_total(e_dict)
        dept = e["department"] or "Production"
        if dept not in groups:
            groups[dept] = []
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
        d = dict(e)
        d["priority_total"] = _priority_total(d)
        rows.append(d)
    rows.sort(key=lambda r: (0 if (r.get("status") or "") == "active" else 1,
                             -(r["priority_total"] or 0)))
    return render_template("pdca_log.html", rows=rows)


@app.route("/pdca/<int:exp_id>")
def pdca_detail(exp_id):
    conn = get_db_connection()
    ex = conn.execute("SELECT * FROM experiments WHERE id=?", (exp_id,)).fetchone()
    if not ex:
        conn.close(); return "Experiment not found", 404
    ex = dict(ex)
    actions = [dict(r) for r in conn.execute(
        "SELECT * FROM experiment_actions WHERE experiment_id=? ORDER BY seq",
        (exp_id,)).fetchall()]
    trend = _compute_trend(conn, ex)
    conn.close()
    return render_template("a3.html", ex=ex, actions=actions,
                           priority_total=_priority_total(ex), trend=trend)


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

        # If closing, set closed_at
        if updates.get('status') == 'closed':
            updates['closed_at'] = datetime.now().isoformat()
        updates['updated_at'] = datetime.now().isoformat()

        set_clause = ', '.join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [exp_id]
        conn.execute(f"UPDATE experiments SET {set_clause} WHERE id=?", vals)
        conn.commit()
        conn.close()
        return redirect(url_for('pdca_detail', exp_id=exp_id))

    lines_list = conn.execute("SELECT * FROM lines ORDER BY id").fetchall()
    conn.close()
    return render_template("a3_edit.html", ex=ex,
                           priority_total=_priority_total(ex),
                           lines=lines_list)


@app.route("/setup", methods=["GET", "POST"])
def setup():
    msg = None
    if request.method == "POST":
        results = []
        file_map = {"assets": "lines", "skus": "skus", "jobs": "jobs"}
        for field_name, table_name in file_map.items():
            if field_name in request.files:
                file = request.files[field_name]
                if file.filename != '':
                    count = ingest_csv(file, table_name)
                    results.append(f"{table_name}: {count} rows inserted")
        msg = "Upload complete. " + " | ".join(results) if results else "No files were selected."
    conn = get_db_connection()
    stats = {"lines": conn.execute("SELECT COUNT(*) FROM lines").fetchone()[0],
             "skus": conn.execute("SELECT COUNT(*) FROM skus").fetchone()[0],
             "jobs": conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]}
    conn.close()
    return render_template("setup.html", stats=stats, msg=msg)


@app.route("/admin", methods=["GET", "POST"])
def admin_view():
    conn = get_db_connection()
    msg = None
    if request.method == "POST":
        name = request.form.get("name")
        role = request.form.get("role")
        line_id = request.form.get("line_id")
        tg_id = request.form.get("telegram_id")
        if name and tg_id:
            try:
                conn.execute(
                    "INSERT INTO users (name, role, line_id, telegram_id) VALUES (?, ?, ?, ?)",
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
    conn = get_db_connection()
    unit = _unit_label(conn)
    runs = conn.execute("""
        SELECT r.id, r.period, r.units_filled, r.duration_min, r.line_id,
               j.job_number, j.sku_id
        FROM hourly_runs r JOIN jobs j ON r.job_id = j.id
        WHERE date(r.recorded_at) = ? AND r.shift = ? ORDER BY r.period
    """, (run_date, shift)).fetchall()
    details = []
    for r in runs:
        rate = conn.execute(
            "SELECT ideal_rate FROM line_sku_rates WHERE line_id=? AND sku_id=?",
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


@app.route("/favicon.ico")
def favicon():
    from flask import send_from_directory
    return send_from_directory(app.root_path, "favicon.png", mimetype="image/png")


if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=5002)
