"""myarr/export.py - Write metric entries to CSV for external systems."""
import csv, sqlite3, sys, datetime

DB_PATH = "/mnt/lake/metrics.db"

def export(path=None, since=None):
    if not path:
        path = "/mnt/lake/metrics-export-%s.csv" % datetime.date.today().isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    q = ("SELECT e.id, e.recorded_at, e.line, e.period, m.name AS metric, "
         "e.value, m.unit, m.direction, e.note, e.source, e.raw_text "
         "FROM entries e JOIN metrics m ON m.id = e.metric_id ")
    params = ()
    if since:
        q += "WHERE e.recorded_at >= ? "
        params = (since,)
    q += "ORDER BY e.recorded_at, e.line, m.name"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id","recorded_at","line","period","metric","value","unit","direction","note","source","raw_text"])
        for r in rows:
            w.writerow([r[k] for k in r.keys()])
    print("Wrote %d row(s) to %s" % (len(rows), path))
    return path

if __name__ == "__main__":
    export(sys.argv[1] if len(sys.argv) > 1 else None)
