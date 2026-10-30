"""myarr/changeover.py - Compute changeover standard between two SKUs."""
import sqlite3, sys

DB = "/mnt/lake/metrics.db"
COMPONENTS = ["wine","glass","label","cork","foil","knockdown"]

def load_sku(cur, sku_id):
    cur.execute("SELECT * FROM skus WHERE id=?", (sku_id,))
    r = cur.fetchone()
    return dict(r) if r else None

def standard(from_id, to_id):
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; cur = c.cursor()
    a, b = load_sku(cur, from_id), load_sku(cur, to_id)
    if not a or not b:
        c.close(); return None
    std = {r["component"]: r for r in cur.execute("SELECT * FROM component_standards")}
    proc = cur.execute("SELECT * FROM changeover_procedures WHERE customer_id=?",
                       (b["customer_id"],)).fetchone()
    changed, serial_min, parallel = [], 0.0, []
    for comp in COMPONENTS:
        key = "wine_id" if comp == "wine" else comp + "_id"
        if a[key] != b[key]:
            changed.append(comp)
            s = std.get("blow_through" if comp == "wine" else comp)
            if not s:
                continue
            if s["serial"]:
                serial_min += s["swap_min"]
            else:
                parallel.append((comp, s["swap_min"]))
    longest = max(parallel, key=lambda x: x[1]) if parallel else ("none", 0.0)
    ver = proc["verification_min"] if proc else 10
    start = proc["startup_min"] if proc else 30
    total = serial_min + longest[1] + ver + start
    c.close()
    return {
        "from": a["part_number"], "to": b["part_number"],
        "changed": changed,
        "blow_through_min": serial_min,
        "longest_parallel": longest[0],
        "longest_parallel_min": longest[1],
        "verification_min": ver, "startup_min": start,
        "total_std_min": total,
        "flush_required": "wine" in changed,
    }

if __name__ == "__main__":
    r = standard(int(sys.argv[1]), int(sys.argv[2]))
    if not r:
        print("SKU not found"); sys.exit(1)
    print("From %s -> %s" % (r["from"], r["to"]))
    print("  components changed : %s" % ", ".join(r["changed"]))
    print("  blow-through       : %.0f min%s" % (r["blow_through_min"], " (flush required)" if r["flush_required"] else ""))
    print("  longest parallel   : %s at %.0f min" % (r["longest_parallel"], r["longest_parallel_min"]))
    print("  verification       : %.0f min" % r["verification_min"])
    print("  startup            : %.0f min" % r["startup_min"])
    print("  TOTAL STANDARD     : %.0f min" % r["total_std_min"])
