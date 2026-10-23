"""myarr/shift_reconcile.py - Shift and job reconciliation."""
import sqlite3
DB = "/mnt/lake/metrics.db"
THRESHOLD = 1.0

def blocks(shift):
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    rows = c.execute("""
        SELECT r.id, r.job_seq, r.period, r.phase, r.bottles_filled,
               s.part_number,
               (SELECT ideal_bpm FROM line_sku_rates
                 WHERE line_id=r.line_id AND sku_id=r.sku_id) AS bpm
        FROM hourly_runs r JOIN skus s ON s.id=r.sku_id
        WHERE r.shift=? ORDER BY r.id""", (shift,)).fetchall()
    out = {}
    for r in rows:
        out.setdefault(r["job_seq"], []).append(dict(r))
    c.close(); return out

def report(shift):
    print("=" * 58); print("SHIFT %s" % shift); print("=" * 58)
    tf = te = tl = tg = 0.0
    for job, rows in sorted(blocks(shift).items()):
        bpm = rows[0]["bpm"]; sku = rows[0]["part_number"]
        filled = sum(r["bottles_filled"] for r in rows)
        exp_b  = sum(r["bpm"] * 60.0 for r in rows)
        gap_m  = sum((r["bpm"]*60.0 - r["bottles_filled"]) / r["bpm"] for r in rows)
        c = sqlite3.connect(DB)
        ids = ",".join(str(r["id"]) for r in rows)
        logged = c.execute("SELECT COALESCE(SUM(minutes),0) FROM downtime_events WHERE run_id IN (%s)" % ids).fetchone()[0]
        c.close()
        unacc = gap_m - logged
        flag = "FLAG - notify line manager" if unacc > THRESHOLD else "reconciled"
        print()
        print("  job %d  %s  (%d bpm, %d rows)" % (job, sku, bpm, len(rows)))
        print("    filled          : %8d bottles" % filled)
        print("    expected        : %8.0f bottles" % exp_b)
        print("    gap             : %8.0f bottles = %6.2f min" % (exp_b - filled, gap_m))
        print("    logged downtime : %8.2f min" % logged)
        print("    UNACCOUNTED     : %8.2f min   [%s]" % (unacc, flag))
        print("    performance     : %8.1f%%" % (filled / exp_b * 100.0))
        tf += filled; te += exp_b; tl += logged; tg += gap_m
    print()
    print("  SHIFT %s TOTAL" % shift)
    print("    filled          : %8d" % tf)
    print("    expected        : %8.0f" % te)
    print("    gap             : %8.0f bottles = %6.2f min" % (te-tf, tg))
    print("    logged          : %8.2f min" % tl)
    print("    UNACCOUNTED     : %8.2f min" % (tg - tl))

if __name__ == "__main__":
    report("2"); print(); report("3")
