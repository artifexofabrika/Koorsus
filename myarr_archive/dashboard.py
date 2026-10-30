"""myarr/dashboard.py - Myarra metrics dashboard."""
import sqlite3
from flask import Flask, render_template_string, jsonify, send_file, request
import os
from werkzeug.utils import secure_filename

DB = "/mnt/lake/metrics.db"
app = Flask(__name__)

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Myarra</title><link rel="icon" type="image/png" href="/favicon.png">
<style>
body{background:#1a1a1a;color:#d4d4d4;font-family:Georgia,serif;margin:0;padding:2rem}
h1{color:#c0a878;font-size:1.5rem;margin:0 0 .2rem}
.sub{color:#888;font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;margin-bottom:1.8rem}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:1rem}
.card{background:#2c2c2c;border:1px solid #444;border-radius:6px;padding:1.2rem}
.name{color:#fff;font-weight:bold;font-size:.95rem}
.unit{color:#888;font-size:.72rem;margin-top:.15rem}
.pct{color:#c0a878;font-size:1.4rem;font-weight:bold;margin:.7rem 0 .2rem}
.bar{background:#1a1a1a;height:9px;border-radius:5px;overflow:hidden;margin:.35rem 0}
.fill{background:#c0a878;height:100%}
.nums{display:flex;justify-content:space-between;font-size:.72rem;color:#b0b0b0;margin-top:.3rem}
.empty{color:#777;font-style:italic;font-size:.8rem;margin:.8rem 0}
.spark{margin-top:.6rem}
.last{color:#777;font-size:.68rem;margin-top:.4rem}
footer{color:#666;font-size:.7rem;margin-top:2rem}
@media (prefers-color-scheme: light) {
  body{background:#faf9f7;color:#2a2a2a}
  h1{color:#8a6d3b}
  .sub{color:#777}
  th{color:#777;border-bottom-color:#ddd}
  td{border-bottom-color:#e8e6e3}
  td:first-child{color:#000}
  .good{color:#2e7d32}
  .bad{color:#c62828}
  .pass{background:#e8f5e9;color:#2e7d32}
  .flag{background:#ffebee;color:#c62828}
  footer{color:#888}
  .card{background:#fff;border-color:#ddd}
  .name{color:#000}
  .unit,.last{color:#888}
  .bar{background:#e8e6e3}
  .nums{color:#555}
  .empty{color:#999}
  .pct{color:#8a6d3b}
  .fill{background:#8a6d3b}
}
</style></head><body>
<h1>Myarra</h1>
<div class="sub">Current state, future state, and the distance between them</div>
<div class="grid">
{% for c in cards %}
<div class="card">
  <div class="name">{{ c.name }}</div>
  <div class="unit">{{ c.unit }} &middot; {{ 'higher is better' if c.direction == 'higher_better' else 'lower is better' }}</div>
  {% if c.current is none %}
    <div class="empty">No readings yet</div>
    <div class="bar"><div class="fill" style="width:0"></div></div>
    <div class="nums"><span>baseline {{ c.baseline if c.baseline is not none else 'unset' }}</span><span>target {{ c.target if c.target is not none else 'unset' }}</span></div>
  {% else %}
    <div class="pct">{{ '%.0f'|format(c.pct) }}%</div>
    <div class="bar"><div class="fill" style="width:{{ '%.0f'|format(c.pct) }}%"></div></div>
    <div class="nums"><span>now {{ c.current }} {{ c.unit }}</span><span>{{ c.count }} reading{{ '' if c.count == 1 else 's' }}</span></div>
    <div class="nums"><span>baseline {{ c.baseline if c.baseline is not none else 'unset' }}</span><span>target {{ c.target if c.target is not none else 'unset' }}</span></div>
    {% if c.spark %}<div class="spark">{{ c.spark|safe }}</div>{% endif %}
    <div class="last">last {{ c.last }}</div>
  {% endif %}
</div>
{% endfor %}
</div>
<footer>Myarra is the measure. Most plants work hard. Few close the loop.</footer>
</body></html>"""

def progress(baseline, target, current, direction):
    if current is None or baseline is None or target is None:
        return 0.0
    if baseline == target:
        return 100.0
    if direction == "higher_better":
        p = (current - baseline) / (target - baseline) * 100.0
    else:
        p = (baseline - current) / (baseline - target) * 100.0
    return max(0.0, min(100.0, p))

def sparkline(values, w=120, h=28):
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    pts = []
    for i, v in enumerate(values):
        x = i / (len(values) - 1) * w
        y = h - (v - lo) / span * (h - 4) - 2
        pts.append("%.1f,%.1f" % (x, y))
    return ('<svg width="%d" height="%d" viewBox="0 0 %d %d">'
            '<polyline points="%s" fill="none" stroke="#c0a878" stroke-width="1.5"/></svg>'
            % (w, h, w, h, " ".join(pts)))

def build_cards():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    out = []
    for m in c.execute("SELECT * FROM metrics ORDER BY id").fetchall():
        last = c.execute("SELECT value, recorded_at FROM entries WHERE metric_id=? ORDER BY recorded_at DESC LIMIT 1", (m["id"],)).fetchone()
        cnt = c.execute("SELECT COUNT(*) FROM entries WHERE metric_id=?", (m["id"],)).fetchone()[0]
        hist = c.execute("SELECT value FROM entries WHERE metric_id=? ORDER BY recorded_at DESC LIMIT 20", (m["id"],)).fetchall()
        cur = last["value"] if last else None
        out.append({
            "name": m["name"], "unit": m["unit"], "direction": m["direction"],
            "baseline": m["baseline_value"], "target": m["target_value"],
            "current": cur, "count": cnt,
            "pct": progress(m["baseline_value"], m["target_value"], cur, m["direction"]),
            "last": last["recorded_at"] if last else None,
            "spark": sparkline([r["value"] for r in reversed(hist)]),
        })
    c.close()
    return out

@app.route("/")
def index():
    return render_template_string(PAGE, cards=build_cards())

@app.route("/favicon.png")
def favicon():
    return send_file("/home/jeeves/Client-Demo/favicon.png", mimetype="image/png")

def shift_rows():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    out = []
    for sh in c.execute("SELECT DISTINCT shift FROM hourly_runs ORDER BY shift").fetchall():
        rows = c.execute("""SELECT r.id, r.job_seq, r.bottles_filled,
            (SELECT ideal_bpm FROM line_sku_rates WHERE line_id=r.line_id AND sku_id=r.sku_id) bpm
            FROM hourly_runs r WHERE r.shift=? ORDER BY r.id""", (sh["shift"],)).fetchall()
        if not rows: continue
        jobs = set(r["job_seq"] for r in rows)
        filled = sum(r["bottles_filled"] for r in rows)
        exp = sum(r["bpm"]*60.0 for r in rows)
        gap = sum((r["bpm"]*60.0 - r["bottles_filled"])/r["bpm"] for r in rows)
        ids = ",".join(str(r["id"]) for r in rows)
        logged = c.execute("SELECT COALESCE(SUM(minutes),0) FROM downtime_events WHERE run_id IN (%s)" % ids).fetchone()[0]
        out.append({"shift": sh["shift"], "filled": filled, "expected": exp, "gap": gap,
                    "logged": logged, "unacc": gap - logged, "jobs": len(jobs),
                    "perf": filled/exp*100.0})
    c.close(); return out

SHIFT_PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Myarra - Shifts</title>
<link rel="icon" type="image/png" href="/favicon.png">
<style>
body{background:#1a1a1a;color:#d4d4d4;font-family:Georgia,serif;margin:0;padding:2rem}
h1{color:#c0a878;font-size:1.5rem;margin:0 0 .2rem}
.sub{color:#888;font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;margin-bottom:1.8rem}
table{border-collapse:collapse;width:100%;max-width:900px}
th{color:#888;font-size:.68rem;text-transform:uppercase;letter-spacing:.1em;text-align:right;padding:.6rem .8rem;border-bottom:1px solid #444}
th:first-child{text-align:left}
td{padding:.85rem .8rem;text-align:right;border-bottom:1px solid #2c2c2c;font-size:.95rem}
td:first-child{text-align:left;color:#fff}
.good{color:#8fd08f}.bad{color:#e09080;font-weight:bold}
.pill{display:inline-block;padding:.15rem .55rem;border-radius:3px;font-size:.68rem;letter-spacing:.05em}
.pass{background:#243b24;color:#8fd08f}.flag{background:#3b2424;color:#e09080}
footer{color:#666;font-size:.7rem;margin-top:2rem}
@media (prefers-color-scheme: light) {
  body{background:#faf9f7;color:#2a2a2a}
  h1{color:#8a6d3b}
  .sub{color:#777}
  th{color:#777;border-bottom-color:#ddd}
  td{border-bottom-color:#e8e6e3}
  td:first-child{color:#000}
  .good{color:#2e7d32}
  .bad{color:#c62828}
  .pass{background:#e8f5e9;color:#2e7d32}
  .flag{background:#ffebee;color:#c62828}
  footer{color:#888}
  .card{background:#fff;border-color:#ddd}
  .name{color:#000}
  .unit,.last{color:#888}
  .bar{background:#e8e6e3}
  .nums{color:#555}
  .empty{color:#999}
  .pct{color:#8a6d3b}
  .fill{background:#8a6d3b}
}
</style></head><body>
<h1>Shift reconciliation</h1>
<div class="sub">Expected = line optimum &times; minutes available</div>
<table><tr><th>Shift</th><th>Jobs</th><th>Filled</th><th>Expected</th><th>Gap min</th><th>Logged</th><th>Unaccounted</th><th>Performance</th><th></th></tr>
{% for r in rows %}
<tr><td>Shift {{ r.shift }}</td><td>{{ r.jobs }}</td><td>{{ '{:,}'.format(r.filled) }}</td>
<td>{{ '{:,.0f}'.format(r.expected) }}</td><td>{{ '%.2f'|format(r.gap) }}</td>
<td>{{ '%.2f'|format(r.logged) }}</td>
<td class="{{ 'good' if r.unacc <= 1 else 'bad' }}">{{ '%.2f'|format(r.unacc) }}</td>
<td>{{ '%.1f'|format(r.perf) }}%</td>
<td><span class="pill {{ 'pass' if r.unacc <= 1 else 'flag' }}">{{ 'reconciled' if r.unacc <= 1 else 'FLAG' }}</span></td></tr>
{% endfor %}
</table>
<footer>Myarra is the measure. Most plants work hard. Few close the loop.</footer>
</body></html>"""

@app.route("/shift")
def shift_view():
    return render_template_string(SHIFT_PAGE, rows=shift_rows())

def changeover_rows():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    ev = c.execute("""
        SELECT e.id, p.name, p.aggregate_standard_min, e.aggregate_actual_min, e.started_at, e.raw_text, e.from_job_number, e.to_job_number
        FROM co_events e JOIN co_procedures_v2 p ON p.id = e.procedure_id
        ORDER BY e.started_at DESC LIMIT 1
    """).fetchone()
    if not ev:
        c.close(); return None, []
    steps = c.execute("""
        SELECT s.step_name, s.station, s.standard_min, es.actual_min, es.note
        FROM co_event_steps es JOIN co_steps_v2 s ON s.id = es.step_id
        WHERE es.event_id = ? ORDER BY s.seq
    """, (ev["id"],)).fetchall()
    c.close()
    return dict(ev), [dict(s) for s in steps]

CHANGEOVER_PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Myarra - Changeover</title>
<link rel="icon" type="image/png" href="/favicon.png">
<style>
body{background:#1a1a1a;color:#d4d4d4;font-family:Georgia,serif;margin:0;padding:2rem}
h1{color:#c0a878;font-size:1.5rem;margin:0 0 .2rem}
.sub{color:#888;font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;margin-bottom:1.8rem}
.agg{background:#2c2c2c;border:1px solid #444;border-radius:6px;padding:1.5rem;margin-bottom:2rem;max-width:900px}
.agg h2{color:#c0a878;margin:0 0 1rem;font-size:1.2rem}
.row{display:flex;justify-content:space-between;margin-bottom:.5rem;font-size:1.1rem}
.bad{color:#e09080;font-weight:bold}.good{color:#8fd08f;font-weight:bold}
table{border-collapse:collapse;width:100%;max-width:900px}
th{color:#888;font-size:.68rem;text-transform:uppercase;text-align:right;padding:.6rem .8rem;border-bottom:1px solid #444}
th:first-child, th:nth-child(2){text-align:left}
td{padding:.85rem .8rem;text-align:right;border-bottom:1px solid #2c2c2c;font-size:.95rem}
td:first-child, td:nth-child(2){text-align:left;color:#fff}
.note{color:#888;font-size:.75rem;font-style:italic;display:block;margin-top:.2rem}
footer{color:#666;font-size:.7rem;margin-top:2rem}
@media (prefers-color-scheme: light) {
  body{background:#faf9f7;color:#2a2a2a} h1,.agg h2{color:#8a6d3b}
  .agg{background:#fff;border-color:#ddd}
  th{color:#777;border-bottom-color:#ddd} td{border-bottom-color:#e8e6e3;color:#000}
  td:first-child, td:nth-child(2){color:#000} .bad{color:#c62828} .good{color:#2e7d32}
}
</style></head><body>
<h1>Changeover Analysis</h1>
<div class="sub">{{ ev.name }} &middot; {{ ev.started_at }}</div>
<div class="sub" style="margin-top:-1rem;color:#c0a878">Job {{ ev.from_job_number }} &rarr; Job {{ ev.to_job_number }}</div>
<div class="agg">
  <h2>Aggregate Time</h2>
  <div class="row"><span>Standard</span><span>{{ '%.0f'|format(ev.aggregate_standard_min) }} min</span></div>
  <div class="row"><span>Actual</span><span class="{{ 'bad' if ev.aggregate_actual_min > ev.aggregate_standard_min else 'good' }}">{{ '%.0f'|format(ev.aggregate_actual_min) }} min</span></div>
  <div class="row"><span>Variance</span><span class="{{ 'bad' if ev.aggregate_actual_min > ev.aggregate_standard_min else 'good' }}">{{ '%+.0f'|format(ev.aggregate_actual_min - ev.aggregate_standard_min) }} min</span></div>
</div>
<table>
<tr><th>Step</th><th>Station</th><th>Standard</th><th>Actual</th><th>Variance</th></tr>
{% for s in steps %}
<tr>
  <td>{{ s.step_name }}{% if s.note %}<span class="note">{{ s.note }}</span>{% endif %}</td>
  <td>{{ s.station }}</td>
  <td>{{ '%.0f'|format(s.standard_min) }}m</td>
  <td>{{ '%.0f'|format(s.actual_min) }}m</td>
  <td class="{{ 'bad' if s.actual_min > s.standard_min else 'good' if s.actual_min < s.standard_min else '' }}">
    {{ '%+.0f'|format(s.actual_min - s.standard_min) }}m
  </td>
</tr>
{% endfor %}
</table>
<footer>Myarra is the measure. Most plants work hard. Few close the loop.</footer>
</body></html>"""

@app.route("/changeover")
def changeover_view():
    ev, steps = changeover_rows()
    if not ev:
        return "No changeover data found."
    return render_template_string(CHANGEOVER_PAGE, ev=ev, steps=steps)

def pdca_cards():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    exps = c.execute("SELECT * FROM experiments WHERE status='active' ORDER BY department, line_id").fetchall()
    out = {}
    for e in exps:
        if e["line_id"]:
            avg = c.execute("""
                SELECT AVG(es.actual_min) FROM co_event_steps es
                JOIN co_steps_v2 s ON s.id = es.step_id
                JOIN co_events ev ON ev.id = es.event_id
                WHERE s.step_name = ? AND ev.started_at >= ? AND ev.line_id = ?
            """, (e["target_step_name"], e["start_date"], e["line_id"])).fetchone()[0]
        else:
            avg = c.execute("""
                SELECT AVG(es.actual_min) FROM co_event_steps es
                JOIN co_steps_v2 s ON s.id = es.step_id
                JOIN co_events ev ON ev.id = es.event_id
                WHERE s.step_name = ? AND ev.started_at >= ?
            """, (e["target_step_name"], e["start_date"])).fetchone()[0]
        dept = e["department"] or "Production"
        if dept not in out:
            out[dept] = []
        out[dept].append(dict(e, current_avg=avg))
    c.close(); return out

PDCA_PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Myarra - PDCA</title>
<link rel="icon" type="image/png" href="/favicon.png">
<style>
body{background:#1a1a1a;color:#d4d4d4;font-family:Georgia,serif;margin:0;padding:2rem}
h1{color:#c0a878;font-size:1.5rem;margin:0 0 .2rem}
.sub{color:#888;font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;margin-bottom:1.8rem}
.board{display:flex;gap:1.5rem;flex-wrap:wrap}
.card{background:#2c2c2c;border:1px solid #444;border-left:3px solid #c0a878;border-radius:6px;padding:1.5rem;width:320px}
.card h3{color:#fff;margin:0 0 1rem;font-size:1.1rem}
.card p{color:#b0b0b0;font-size:.85rem;line-height:1.5;margin:0 0 1rem}
.stats{display:flex;justify-content:space-between;border-top:1px solid #444;padding-top:1rem;margin-top:1rem;font-size:.85rem}
.stat{text-align:center}
.stat span{display:block;color:#888;font-size:.65rem;text-transform:uppercase;letter-spacing:.1em;margin-bottom:.2rem}
.val{font-weight:bold;font-size:1.1rem}
.bad{color:#e09080}.good{color:#8fd08f}.neutral{color:#c0a878}
@media (prefers-color-scheme: light) {
  body{background:#faf9f7;color:#2a2a2a} h1{color:#8a6d3b}
  .card{background:#fff;border-color:#ddd;border-left-color:#8a6d3b}
  .card h3{color:#000} .card p{color:#555} .stats{border-top-color:#ddd}
  .bad{color:#c62828} .good{color:#2e7d32} .neutral{color:#8a6d3b}
}
</style></head><body>
<h1>Lean Planning Board</h1>
<div class="sub">Active PDCA Experiments</div>
{% for dept, cards in groups.items() %}
  <h2 style="color:#c0a878;margin-top:2rem;margin-bottom:1rem;border-bottom:1px solid #444;padding-bottom:.5rem">{{ dept }}</h2>
  <div class="board">
  {% for c in cards %}
  <a href="/pdca/{{ c.id }}" style="text-decoration:none; color:inherit;">
  <div class="card" style="transition: background 0.2s;" onmouseover="this.style.background='#3a3a3a'" onmouseout="this.style.background='#2c2c2c'">
    <h3>{{ c.title }} <span style="font-size:.7rem;color:#888;font-weight:normal">(Line {{ c.line_id }})</span></h3>
    <p><strong>Problem:</strong> {{ c.problem_statement }}</p>
    <p><strong>Hypothesis:</strong> {{ c.hypothesis }}</p>
    <div class="stats">
      <div class="stat"><span>Standard</span><div class="val neutral">{{ '%.0f'|format(c.standard_min) }}m</div></div>
      <div class="stat"><span>Target</span><div class="val neutral">{{ '%.0f'|format(c.target_goal_min) }}m</div></div>
      <div class="stat"><span>Current Avg</span>
        {% if c.current_avg is not none %}
          <div class="val {{ 'good' if c.current_avg <= c.target_goal_min else 'bad' }}">{{ '%.0f'|format(c.current_avg) }}m</div>
        {% else %}
          <div class="val bad">N/A</div>
        {% endif %}
      </div>
    </div>
  </div>
  </a>
  {% endfor %}
  </div>
{% endfor %}
<footer style="color:#666;font-size:.7rem;margin-top:2rem">Myarra is the measure. Most plants work hard. Few close the loop.</footer>
</body></html>"""

@app.route("/pdca")
def pdca_view():
    return render_template_string(PDCA_PAGE, groups=pdca_cards())


A3_PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>A3 - {{ e.title }}</title>
<link rel="icon" type="image/png" href="/favicon.png">
<style>
body{background:#1a1a1a;color:#d4d4d4;font-family:Georgia,serif;margin:0;padding:2rem}
h1{color:#c0a878;font-size:1.5rem;margin:0 0 1.5rem}
.a3{background:#2c2c2c;border:1px solid #444;border-radius:6px;padding:1.5rem;max-width:900px}
.row{display:flex;gap:1rem;margin-bottom:1rem}
.col{flex:1}
label{display:block;color:#888;font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.3rem}
input[type="text"], input[type="date"], textarea, select{width:100%;background:#1a1a1a;border:1px solid #444;color:#fff;padding:.6rem;border-radius:4px;font-family:Georgia,serif;font-size:.9rem;box-sizing:border-box}
textarea{resize:vertical;min-height:80px}
button{background:#c0a878;color:#1a1a1a;border:none;padding:.8rem 1.5rem;border-radius:4px;font-weight:bold;cursor:pointer;font-size:.9rem;margin-top:1rem}
.stats{display:flex;gap:2rem;background:#1a1a1a;padding:1rem;border-radius:4px;margin-bottom:1.5rem;border-left:3px solid #c0a878}
.stat span{display:block;color:#888;font-size:.65rem;text-transform:uppercase;margin-bottom:.2rem}
.stat .val{font-size:1.2rem;font-weight:bold;color:#fff}
.bad{color:#e09080 !important}.good{color:#8fd08f !important}.neutral{color:#c0a878 !important}
a{color:#c0a878;text-decoration:none;font-size:.9rem;display:inline-block;margin-bottom:1rem}
@media (prefers-color-scheme: light) {
  body{background:#faf9f7;color:#2a2a2a} h1,a{color:#8a6d3b}
  .a3{background:#fff;border-color:#ddd} label{color:#777}
  input,textarea,select{background:#faf9f7;border-color:#ccc;color:#000}
  .stats{background:#f0f0f0;border-left-color:#8a6d3b} .stat .val{color:#000}
  .bad{color:#c62828 !important}.good{color:#2e7d32 !important}.neutral{color:#8a6d3b !important}
}
</style></head><body>
<a href="/pdca">&larr; Back to Board</a>
<h1>{{ e.title }} (Line {{ e.line_id or 'N/A' }})</h1>
<div class="stats">
  <div class="stat"><span>Standard</span><div class="val neutral">{{ '%.0f'|format(e.standard_min) }}m</div></div>
  <div class="stat"><span>Target</span><div class="val neutral">{{ '%.0f'|format(e.target_goal_min) }}m</div></div>
  <div class="stat"><span>Current Avg</span>
    {% if e.current_avg is not none %}
      <div class="val {{ 'good' if e.current_avg <= e.target_goal_min else 'bad' }}">{{ '%.0f'|format(e.current_avg) }}m</div>
    {% else %}
      <div class="val bad">N/A</div>
    {% endif %}
  </div>
</div>
<form method="POST" class="a3">
  <div class="row">
    <div class="col"><label>Problem Severity (1, 3, 5)</label>
      <select name="severity">
        <option value="1" {{ 'selected' if e.severity == 1 }}>1 - Low</option>
        <option value="3" {{ 'selected' if e.severity == 3 }}>3 - Medium</option>
        <option value="5" {{ 'selected' if e.severity == 5 }}>5 - High</option>
      </select>
    </div>
    <div class="col"><label>Start Date</label><input type="date" name="start_date" value="{{ e.start_date }}"></div>
    <div class="col"><label>PDCA Owner(s)</label><input type="text" name="owner" value="{{ e.owner or '' }}"></div>
    <div class="col"><label>Mgmt/CI Sponsor</label><input type="text" name="sponsor" value="{{ e.sponsor or '' }}"></div>
  </div>
  <div class="row">
    <div class="col"><label>Team Members Involved</label><input type="text" name="team" value="{{ e.team or '' }}"></div>
    <div class="col"><label>Departments Involved</label><input type="text" name="departments" value="{{ e.departments or '' }}"></div>
  </div>
  <div class="row">
    <div class="col"><label>What is our Current Condition?</label><textarea name="current_condition">{{ e.current_condition or '' }}</textarea></div>
    <div class="col"><label>What is our Target Condition?</label><textarea name="target_condition">{{ e.target_condition or '' }}</textarea></div>
  </div>
  <div class="row">
    <div class="col"><label>What is the Problem? (Root Cause)</label><textarea name="root_cause">{{ e.root_cause or '' }}</textarea></div>
    <div class="col"><label>Fishbone Category</label>
      <select name="fishbone_category">
        <option value="">-- Select --</option>
        <option value="Man" {{ 'selected' if e.fishbone_category == 'Man' }}>Man</option>
        <option value="Method" {{ 'selected' if e.fishbone_category == 'Method' }}>Method</option>
        <option value="Material" {{ 'selected' if e.fishbone_category == 'Material' }}>Material</option>
        <option value="Machine" {{ 'selected' if e.fishbone_category == 'Machine' }}>Machine</option>
        <option value="Environment" {{ 'selected' if e.fishbone_category == 'Environment' }}>Environment</option>
        <option value="Measurement" {{ 'selected' if e.fishbone_category == 'Measurement' }}>Measurement</option>
      </select>
    </div>
  </div>
  <div class="row">
    <div class="col"><label>What is our Hypothesis?</label><textarea name="hypothesis">{{ e.hypothesis or '' }}</textarea></div>
    <div class="col"><label>What is our Action Plan?</label><textarea name="action_plan">{{ e.action_plan or '' }}</textarea></div>
  </div>
  <div class="row">
    <div class="col"><label>Who is responsible?</label><input type="text" name="action_owner" value="{{ e.action_owner or '' }}"></div>
    <div class="col"><label>When will it be done?</label><input type="date" name="action_due_date" value="{{ e.action_due_date or '' }}"></div>
    <div class="col"><label>How do we know it's solved?</label><input type="text" name="success_metric" value="{{ e.success_metric or '' }}"></div>
  </div>
  <button type="submit">Save A3</button>
</form>
</body></html>"""

@app.route("/pdca/<int:exp_id>", methods=["GET", "POST"])
def a3_view(exp_id):
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    if request.method == "POST":
        f = request.form
        c.execute("""UPDATE experiments SET severity=?, start_date=?, owner=?, sponsor=?, team=?, departments=?, 
                     current_condition=?, target_condition=?, root_cause=?, fishbone_category=?, hypothesis=?, 
                     action_plan=?, action_owner=?, action_due_date=?, success_metric=? WHERE id=?""",
                  (f.get("severity"), f.get("start_date"), f.get("owner"), f.get("sponsor"), f.get("team"), f.get("departments"),
                   f.get("current_condition"), f.get("target_condition"), f.get("root_cause"), f.get("fishbone_category"), f.get("hypothesis"),
                   f.get("action_plan"), f.get("action_owner"), f.get("action_due_date"), f.get("success_metric"), exp_id))
        c.commit()
    
    e = c.execute("SELECT * FROM experiments WHERE id=?", (exp_id,)).fetchone()
    if not e:
        c.close(); return "Experiment not found", 404
        
    if e["line_id"]:
        avg = c.execute("""SELECT AVG(es.actual_min) FROM co_event_steps es JOIN co_steps_v2 s ON s.id = es.step_id JOIN co_events ev ON ev.id = es.event_id WHERE s.step_name = ? AND ev.started_at >= ? AND ev.line_id = ?""", (e["target_step_name"], e["start_date"], e["line_id"])).fetchone()[0]
    else:
        avg = c.execute("""SELECT AVG(es.actual_min) FROM co_event_steps es JOIN co_steps_v2 s ON s.id = es.step_id JOIN co_events ev ON ev.id = es.event_id WHERE s.step_name = ? AND ev.started_at >= ?""", (e["target_step_name"], e["start_date"])).fetchone()[0]
    
    e_dict = dict(e)
    e_dict["current_avg"] = avg
    c.close()
    return render_template_string(A3_PAGE, e=e_dict)


SETUP_PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Myarra - Setup</title>
<link rel="icon" type="image/png" href="/favicon.png">
<style>
body{background:#1a1a1a;color:#d4d4d4;font-family:Georgia,serif;margin:0;padding:2rem}
h1{color:#c0a878;font-size:1.5rem;margin:0 0 .2rem}
.sub{color:#888;font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;margin-bottom:1.8rem}
.grid{display:flex;gap:1.5rem;flex-wrap:wrap;max-width:900px}
.box{background:#2c2c2c;border:1px solid #444;border-radius:6px;padding:1.5rem;flex:1 1 400px}
.box h2{color:#c0a878;margin:0 0 1rem;font-size:1.1rem;border-bottom:1px solid #444;padding-bottom:.5rem}
.stat-row{display:flex;justify-content:space-between;padding:.5rem 0;border-bottom:1px dotted #444}
.stat-row span:last-child{font-weight:bold;color:#fff}
form{display:flex;flex-direction:column;gap:1rem}
.file-input{background:#1a1a1a;border:1px solid #444;padding:.6rem;border-radius:4px;color:#d4d4d4;width:100%;box-sizing:border-box}
button{background:#c0a878;color:#1a1a1a;border:none;padding:.8rem 1.5rem;border-radius:4px;font-weight:bold;cursor:pointer;font-size:.9rem;margin-top:1rem}
.success{background:#243b24;color:#8fd08f;padding:1rem;border-radius:4px;margin-bottom:1rem;border-left:3px solid #8fd08f}
a{color:#c0a878;text-decoration:none;font-size:.9rem;display:inline-block;margin-bottom:1rem}
@media (prefers-color-scheme: light) {
  body{background:#faf9f7;color:#2a2a2a} h1,.box h2,a{color:#8a6d3b}
  .box{background:#fff;border-color:#ddd} .stat-row{border-bottom-color:#eee}
  .stat-row span:last-child{color:#000} .file-input{background:#faf9f7;border-color:#ccc;color:#000}
  .success{background:#e8f5e9;color:#2e7d32;border-left-color:#2e7d32}
}
</style></head><body>
<a href="/">&larr; Back to Dashboard</a>
<h1>Plant Configuration</h1>
<div class="sub">Build the Digital Twin</div>

{% if msg %}<div class="success">{{ msg }}</div>{% endif %}

<div class="grid">
  <div class="box">
    <h2>Current Database State</h2>
    <div class="stat-row"><span>Lines Configured</span><span>{{ stats.lines }}</span></div>
    <div class="stat-row"><span>SKUs / Products</span><span>{{ stats.skus }}</span></div>
    <div class="stat-row"><span>Standard Work Instructions</span><span>{{ stats.skills }}</span></div>
    <div class="stat-row"><span>Changeover Procedures</span><span>{{ stats.procedures }}</span></div>
    <div class="stat-row"><span>Active Experiments</span><span>{{ stats.experiments }}</span></div>
  </div>
  
  <div class="box">
    <h2>Upload New Configuration</h2>
    <p style="font-size:.85rem;color:#888;margin-bottom:1rem">Upload CSV files to initialize or overwrite the plant data.</p>
    <div style="margin-bottom:1.5rem;font-size:.85rem">
      <span style="color:#c0a878;font-weight:bold">Download Blank Templates:</span>
      <a href="/setup/template/assets" style="margin-left:.5rem">Assets</a> | 
      <a href="/setup/template/skus">Products</a> | 
      <a href="/setup/template/swi">Standard Work</a> | 
      <a href="/setup/template/changeovers">Changeovers</a>
    </div>
    <form method="POST" enctype="multipart/form-data">
      <div>
        <label style="color:#888;font-size:.7rem;text-transform:uppercase;margin-bottom:.2rem;display:block">1. Assets (Lines & Stations)</label>
        <input type="file" name="assets" class="file-input" accept=".csv">
      </div>
      <div>
        <label style="color:#888;font-size:.7rem;text-transform:uppercase;margin-bottom:.2rem;display:block">2. Products (SKUs & BOM)</label>
        <input type="file" name="skus" class="file-input" accept=".csv">
      </div>
      <div>
        <label style="color:#888;font-size:.7rem;text-transform:uppercase;margin-bottom:.2rem;display:block">3. Standard Work</label>
        <input type="file" name="swi" class="file-input" accept=".csv">
      </div>
      <div>
        <label style="color:#888;font-size:.7rem;text-transform:uppercase;margin-bottom:.2rem;display:block">4. Changeover Procedures</label>
        <input type="file" name="changeovers" class="file-input" accept=".csv">
      </div>
      <button type="submit">Process Uploads</button>
    </form>
  </div>
</div>
</body></html>"""

@app.route("/setup/template/<name>")
def download_template(name):
    # Generate the CSV content on the fly based on the name
    templates = {
        "assets": "line_name,line_id,station_name,ideal_bpm,buffer_bottles\nLine 1,1,Filler,600,10000\nLine 1,1,Labeler,1200,5000",
        "skus": "sku_id,part_number,description,customer,wine,glass,label,cork,foil,knockdown,case_pack\n1,WW-750-Mer,Wolf Merlot 750,Wolf Winery,Cabernet,Claret 750,Label A,Cork A,Foil A,KD 12x750,12",
        "swi": "station_name,operator_role,standard_steps,standard_minutes\nLabeler,Operator A,Load roll and thread web,10",
        "changeovers": "from_sku,to_sku,step_name,station,standard_min,is_serial\nWW-750-Mer,WW-750-CS,Blow-through,Filler,45,1\nWW-750-Mer,WW-750-CS,Change label,Labeler,62,0"
    }
    if name not in templates:
        return "Template not found", 404
    from flask import Response
    return Response(templates[name], mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename={name}_template.csv"})

@app.route("/setup", methods=["GET", "POST"])
def setup_view():
    msg = None
    if request.method == "POST":
        # Mock processing - in reality, this would parse CSVs and update DB
        files = request.files
        uploaded = []
        for key in ["assets", "skus", "swi", "changeovers"]:
            if key in files:
                f = files[key]
                if f.filename != '':
                    filename = secure_filename(f.filename)
                    f.save(os.path.join("/home/jeeves/Client-Demo/uploads", filename))
                    uploaded.append(key)
        if uploaded:
            msg = "Successfully processed and saved: " + ", ".join(uploaded)
        else:
            msg = "No files were selected."

    c = sqlite3.connect(DB)
    stats = {
        "lines": c.execute("SELECT COUNT(*) FROM lines").fetchone()[0],
        "skus": c.execute("SELECT COUNT(*) FROM skus").fetchone()[0],
        "skills": c.execute("SELECT COUNT(*) FROM component_standards").fetchone()[0],
        "procedures": c.execute("SELECT COUNT(*) FROM co_procedures_v2").fetchone()[0],
        "experiments": c.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
    }
    c.close()
    return render_template_string(SETUP_PAGE, stats=stats, msg=msg)

@app.route("/api/summary")
def api_summary():
    return jsonify(build_cards())

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=5001)
