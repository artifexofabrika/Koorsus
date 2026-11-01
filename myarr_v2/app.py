"""
Myarra Web Application
"""
from flask import Flask, render_template, request
from db import get_db_connection, ingest_csv

app = Flask(__name__)


def _priority_total(e):
    """Priority = time*10 + impact*30 + resources*30 + magnitude*30 + cost*50."""
    return (
        (e.get("pri_time") or 0) * 10 +
        (e.get("pri_impact") or 0) * 30 +
        (e.get("pri_resources") or 0) * 30 +
        (e.get("pri_magnitude") or 0) * 30 +
        (e.get("pri_cost") or 0) * 50
    )


def _unit_label(conn):
    try:
        r = conn.execute("SELECT value FROM settings WHERE key='unit_label'").fetchone()
        return r[0] if r else "units"
    except Exception:
        return "units"


@app.route("/")
def dashboard():
    """Shift reconciliation grouped by date and shift."""
    conn = get_db_connection()
    unit = _unit_label(conn)
    out = []

    shifts = conn.execute("""
        SELECT shift, date(recorded_at) as run_date
        FROM hourly_runs
        GROUP BY run_date, shift
        ORDER BY run_date DESC, shift DESC
        LIMIT 20
    """).fetchall()

    for sh in shifts:
        shift_val = sh["shift"]
        run_date = sh["run_date"]

        runs = conn.execute("""
            SELECT r.id, r.units_filled, r.duration_min, r.line_id,
                   j.sku_id, j.id AS job_id
            FROM hourly_runs r
            JOIN jobs j ON r.job_id = j.id
            WHERE r.shift=? AND date(r.recorded_at) = ?
        """, (shift_val, run_date)).fetchall()

        if not runs:
            continue

        filled = sum(r["units_filled"] for r in runs)

        expected = 0
        for r in runs:
            rate = conn.execute(
                "SELECT ideal_rate FROM line_sku_rates WHERE line_id=? AND sku_id=?",
                (r["line_id"], r["sku_id"])).fetchone()
            rpm = rate["ideal_rate"] if rate else 600.0
            expected += (rpm * r["duration_min"] / 60.0)

        total_minutes = sum(r["duration_min"] for r in runs)
        avg_rpm = (expected / total_minutes) if total_minutes else 600.0
        gap = (expected - filled) / avg_rpm if avg_rpm else 0.0

        run_ids = ",".join(str(r["id"]) for r in runs)
        logged = conn.execute(
            f"SELECT COALESCE(SUM(minutes),0) FROM downtime_events WHERE run_id IN ({run_ids})"
        ).fetchone()[0]

        out.append({
            "shift": f"{run_date} - S{shift_val}",
            "raw_date": run_date,
            "raw_shift": shift_val,
            "jobs": len(set(r["job_id"] for r in runs)),
            "filled": filled,
            "expected": expected,
            "gap": gap,
            "logged": logged,
            "unacc": gap - logged,
            "perf": (filled / expected) * 100.0 if expected else 0.0
        })
    conn.close()
    return render_template("dashboard.html", rows=out, unit=unit)


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
        conn.close()
        return "No changeover data found."

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
        SELECT * FROM experiments
        WHERE status='active'
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
            WHERE s.step_name = ?
            ORDER BY ev.started_at ASC
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
    """Flat register: all PDCAs, active first, then sorted by priority."""
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
        conn.close()
        return "Experiment not found", 404
    ex = dict(ex)
    actions = [dict(r) for r in conn.execute(
        "SELECT * FROM experiment_actions WHERE experiment_id=? ORDER BY seq",
        (exp_id,)).fetchall()]
    conn.close()
    return render_template("a3.html", ex=ex, actions=actions,
                           priority_total=_priority_total(ex))


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
    stats = {
        "lines": conn.execute("SELECT COUNT(*) FROM lines").fetchone()[0],
        "skus": conn.execute("SELECT COUNT(*) FROM skus").fetchone()[0],
        "jobs": conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    }
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
        FROM hourly_runs r
        JOIN jobs j ON r.job_id = j.id
        WHERE date(r.recorded_at) = ? AND r.shift = ?
        ORDER BY r.period
    """, (run_date, shift)).fetchall()

    details = []
    for r in runs:
        rate = conn.execute(
            "SELECT ideal_rate FROM line_sku_rates WHERE line_id=? AND sku_id=?",
            (r["line_id"], r["sku_id"])).fetchone()
        rpm = rate["ideal_rate"] if rate else 600.0
        expected = rpm * r["duration_min"] / 60.0
        gap = (expected - r["units_filled"]) / (rpm / 60.0) if rpm else 0.0

        dts = conn.execute(
            "SELECT station, reason, minutes FROM downtime_events WHERE run_id=?",
            (r["id"],)).fetchall()

        details.append({
            "period": r["period"],
            "job_number": r["job_number"],
            "expected": expected,
            "actual": r["units_filled"],
            "gap": gap,
            "downtime": [
                {"station": d["station"], "reason": d["reason"],
                 "minutes": round(d["minutes"], 1)}
                for d in dts
            ]
        })
    conn.close()
    return render_template("shift_detail.html", run_date=run_date, shift=shift,
                           details=details, unit=unit)


if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=5002)
