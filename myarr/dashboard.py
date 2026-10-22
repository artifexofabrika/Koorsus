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

@app.route("/api/summary")
def api_summary():
    return jsonify(build_cards())

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=5001)
