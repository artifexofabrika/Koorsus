"""myarr/procedure.py - Changeover as a named-step procedure."""
import sqlite3, sys
DB = "/mnt/lake/metrics.db"

def total(proc_id):
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    steps = c.execute("SELECT * FROM co_steps WHERE procedure_id=? ORDER BY seq",(proc_id,)).fetchall()
    if not steps:
        c.close(); return None
    serial = sum(s["standard_min"] for s in steps if s["is_serial"])
    par = max((s["standard_min"] for s in steps if not s["is_serial"]), default=0.0)
    par_name = next((s["step_name"] for s in steps if not s["is_serial"] and s["standard_min"]==par), None)
    c.close()
    return {"steps":[dict(s) for s in steps], "serial_min":serial, "parallel_max":par,
            "parallel_constraint":par_name, "total_min":serial+par}

if __name__ == "__main__":
    pid = int(sys.argv[1])
    r = total(pid)
    if not r:
        print("Procedure not found"); sys.exit(1)
    print("Procedure %d - standard %.0f min" % (pid, r["total_min"]))
    print("%-4s %-40s %-14s %6s %s" % ("seq","step","station","min","mode"))
    for s in r["steps"]:
        mode = "serial" if s["is_serial"] else "parallel"
        print("%-4d %-40s %-14s %6.0f %s" % (s["seq"],s["step_name"],s["station"] or "",s["standard_min"],mode))
    print("  serial total      : %.0f min" % r["serial_min"])
    print("  parallel max      : %.0f min (%s)" % (r["parallel_max"], r["parallel_constraint"] or "-"))
    print("  TOTAL STANDARD    : %.0f min" % r["total_min"])
