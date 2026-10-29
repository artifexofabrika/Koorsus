"""myarr/dashboard.py - Myarra metrics dashboard."""
import sqlite3
from flask import Flask, render_template_string, jsonify, send_file

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
        SELECT e.id, p.name, p.aggregate_standard_min, e.aggregate_actual_min, e.started_at, e.raw_text
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

@app.route("/api/summary")
def api_summary():
    return jsonify(build_cards())

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=5001)
