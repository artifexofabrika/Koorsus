"""myarr/ingest.py - Parse floor text and write metric entries to SQLite."""
import re, sqlite3, sys

DB_PATH = "/mnt/lake/metrics.db"

def parse(text):
    raw = text.strip()
    line = period = None
    m = re.search(r"[Ll]ine\s*(\d+)", raw)
    if m:
        line = "Line " + m.group(1)
    m = re.search(r"[Hh]our\s*(\d+)\s*[-\u2013]\s*(\d+)", raw)
    if m:
        period = "H%s-%s" % (m.group(1), m.group(2))
    out = []
    m = re.search(r"(\d+)\s*(?:parts?|units?|pcs?|pieces?)", raw)
    parts = float(m.group(1)) if m else None
    if parts is not None:
        out.append(("line speed", parts, None))
    m = re.search(r"(\d+)\s*scrap", raw)
    if m:
        n = float(m.group(1))
        if parts:
            out.append(("scrap rate", round(n / parts * 100, 2), None))
        else:
            out.append(("scrap rate", n, "raw count"))
    m = re.search(r"(\d+)\s*(?:min|minutes?)\s*(?:down|downtime)(?:\s+(.+))?", raw)
    if m:
        out.append(("downtime", float(m.group(1)), m.group(2)))
    m = re.search(r"(\d+)\s*(?:min|minutes?)\s*(?:changeover|change over)", raw)
    if m:
        out.append(("changeover time", float(m.group(1)), None))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent)\s*OEE", raw, re.I)
    if m:
        out.append(("OEE", float(m.group(1)), None))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent)\s*on.?time", raw, re.I)
    if m:
        out.append(("on-time delivery", float(m.group(1)), None))
    return out, line, period, raw

def write(rows, line, period, raw, source="manual"):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    n = 0
    for name, value, note in rows:
        cur.execute("SELECT id FROM metrics WHERE name = ?", (name,))
        r = cur.fetchone()
        if not r:
            continue
        cur.execute(
            "INSERT INTO entries (metric_id, value, note, line, period, source, raw_text) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (r[0], value, note, line, period, source, raw))
        n += 1
    conn.commit()
    conn.close()
    return n

if __name__ == "__main__":
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read()
    rows, line, period, raw = parse(text)
    n = write(rows, line, period, raw)
    print("Parsed %d metric(s), wrote %d entry/entries" % (len(rows), n))
    for name, value, note in rows:
        print("  %s: %s%s" % (name, value, (" (" + note + ")") if note else ""))
