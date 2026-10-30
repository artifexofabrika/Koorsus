"""
Myarra Web Application
Clean modular Flask server using Jinja2 templates.
"""
from flask import Flask, render_template, request
from db import get_db_connection, ingest_csv

app = Flask(__name__)

@app.route("/")
def dashboard():
    """Shift reconciliation view."""
    conn = get_db_connection()
    out = []
    shifts = conn.execute("SELECT DISTINCT shift FROM hourly_runs ORDER BY shift").fetchall()
    
    for sh in shifts:
        shift_val = sh["shift"]
        runs = conn.execute("SELECT id, bottles_filled FROM hourly_runs WHERE shift=?", (shift_val,)).fetchall()
        if not runs:
            continue
            
        filled = sum(r["bottles_filled"] for r in runs)
        expected = len(runs) * 36000 
        gap = (expected - filled) / 600.0
        
        run_ids = ",".join(str(r["id"]) for r in runs)
        logged = conn.execute(f"SELECT COALESCE(SUM(minutes),0) FROM downtime_events WHERE run_id IN ({run_ids})").fetchone()[0]
        
        out.append({
            "shift": shift_val, "jobs": 1, "filled": filled, "expected": expected,
            "gap": gap, "logged": logged, "unacc": gap - logged,
            "perf": (filled / expected) * 100.0
        })
    conn.close()
    return render_template("dashboard.html", rows=out)

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
        if results:
            msg = "Upload complete. " + " | ".join(results)
        else:
            msg = "No files were selected."

    conn = get_db_connection()
    stats = {
        "lines": conn.execute("SELECT COUNT(*) FROM lines").fetchone()[0],
        "skus": conn.execute("SELECT COUNT(*) FROM skus").fetchone()[0],
        "jobs": conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    }
    conn.close()
    return render_template("setup.html", stats=stats, msg=msg)

@app.route("/changeover")
def changeover_view():
    conn = get_db_connection()
    ev = conn.execute("""
        SELECT e.id, p.name, p.aggregate_standard_min, e.aggregate_actual_min, e.started_at, e.raw_text, e.from_job_number, e.to_job_number
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
    exps = conn.execute("SELECT * FROM experiments WHERE status='active' ORDER BY department, line_id").fetchall()
    groups = {}
    for e in exps:
        if e["line_id"]:
            avg = conn.execute("""
                SELECT AVG(es.actual_min) FROM co_event_steps es
                JOIN co_steps_v2 s ON s.id = es.step_id
                JOIN co_events ev ON ev.id = es.event_id
                WHERE s.step_name = ? AND ev.started_at >= ? AND ev.line_id = ?
            """, (e["target_step_name"], e["start_date"], e["line_id"])).fetchone()[0]
        else:
            avg = conn.execute("""
                SELECT AVG(es.actual_min) FROM co_event_steps es
                JOIN co_steps_v2 s ON s.id = es.step_id
                JOIN co_events ev ON ev.id = es.event_id
                WHERE s.step_name = ? AND ev.started_at >= ?
            """, (e["target_step_name"], e["start_date"])).fetchone()[0]
            
        dept = e["department"] or "Production"
        if dept not in groups:
            groups[dept] = []
        
        e_dict = dict(e)
        e_dict["current_avg"] = avg
        groups[dept].append(e_dict)
        
    conn.close()
    return render_template("pdca.html", groups=groups)

@app.route("/pdca/<int:exp_id>", methods=["GET", "POST"])
def a3_view(exp_id):
    conn = get_db_connection()
    
    if request.method == "POST":
        f = request.form
        conn.execute("""UPDATE experiments SET severity=?, start_date=?, owner=?, sponsor=?, team=?, departments=?, 
                     current_condition=?, target_condition=?, root_cause=?, fishbone_category=?, hypothesis=?, 
                     action_plan=?, action_owner=?, action_due_date=?, success_metric=? WHERE id=?""",
                  (f.get("severity"), f.get("start_date"), f.get("owner"), f.get("sponsor"), f.get("team"), f.get("departments"),
                   f.get("current_condition"), f.get("target_condition"), f.get("root_cause"), f.get("fishbone_category"), f.get("hypothesis"),
                   f.get("action_plan"), f.get("action_owner"), f.get("action_due_date"), f.get("success_metric"), exp_id))
        conn.commit()
    
    e = conn.execute("SELECT * FROM experiments WHERE id=?", (exp_id,)).fetchone()
    if not e:
        conn.close()
        return "Experiment not found", 404
        
    if e["line_id"]:
        avg = conn.execute("""SELECT AVG(es.actual_min) FROM co_event_steps es JOIN co_steps_v2 s ON s.id = es.step_id JOIN co_events ev ON ev.id = es.event_id WHERE s.step_name = ? AND ev.started_at >= ? AND ev.line_id = ?""", (e["target_step_name"], e["start_date"], e["line_id"])).fetchone()[0]
    else:
        avg = conn.execute("""SELECT AVG(es.actual_min) FROM co_event_steps es JOIN co_steps_v2 s ON s.id = es.step_id JOIN co_events ev ON ev.id = es.event_id WHERE s.step_name = ? AND ev.started_at >= ?""", (e["target_step_name"], e["start_date"])).fetchone()[0]
    
    e_dict = dict(e)
    e_dict["current_avg"] = avg
    conn.close()
    return render_template("a3.html", e=e_dict)

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=5002)
