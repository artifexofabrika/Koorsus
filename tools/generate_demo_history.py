"""Generate 30 days of demo history against the master data already in the DB."""
import argparse
import random
import sqlite3
import sys
from datetime import datetime, timedelta

DB = "/mnt/lake/myarra.db"


def write_co_event_changes(cur, event_id, from_sku_id, to_sku_id):
    a = {r[0]: r[1] for r in cur.execute(
        "SELECT component_type_id, component_value FROM sku_bom WHERE sku_id=?",
        (from_sku_id,))}
    b = {r[0]: r[1] for r in cur.execute(
        "SELECT component_type_id, component_value FROM sku_bom WHERE sku_id=?",
        (to_sku_id,))}
    for cid in sorted(set(a) | set(b)):
        if a.get(cid) != b.get(cid):
            cur.execute(
                "INSERT INTO co_event_changes (event_id, component_type_id, from_value, to_value, created_at) "
                "VALUES (?,?,?,?,?)",
                (event_id, cid, a.get(cid), b.get(cid), datetime.now().isoformat()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="wipe existing history first")
    args = ap.parse_args()

    random.seed(42)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    n = c.execute("SELECT COUNT(*) FROM hourly_runs").fetchone()[0]
    if n and not args.force:
        print(f"REFUSING: hourly_runs already has {n} rows. Use --force.")
        return 1
    if n:
        for t in ["downtime_events", "hourly_runs", "co_event_steps",
                  "co_event_changes", "co_events", "line_events"]:
            c.execute(f"DELETE FROM {t}")
        c.execute("DELETE FROM bot_sessions")
        conn.commit()

    rates = {(r["line_id"], r["sku_id"]): r["ideal_rate"]
             for r in c.execute("SELECT line_id, sku_id, ideal_rate FROM line_sku_rates")}
    procedures = {(r["line_id"], r["from_sku_id"], r["to_sku_id"]): dict(r)
                  for r in c.execute("SELECT * FROM co_procedures_v2")}
    jobs = [dict(r) for r in c.execute(
        "SELECT * FROM jobs ORDER BY line_id, scheduled_start, id")]

    if not jobs:
        print("REFUSING: no jobs in DB. Upload demo-data/jobs.csv first.")
        return 1

    TODAY = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    START = TODAY - timedelta(days=30)
    SHIFTS = [(7, 15), (15, 23), (23, 7)]

    by_line = {}
    for j in jobs:
        by_line.setdefault(j["line_id"], []).append(j)

    for lid, lst in by_line.items():
        for i, j in enumerate(lst):
            jday = START + timedelta(days=1 + i * 5 + (lid % 3))
            shifts_count = random.choice([1, 2])
            j["_start"] = jday
            j["_shifts"] = shifts_count
            j["_rate"] = rates.get((lid, j["sku_id"]), 1000)
            c.execute(
                "UPDATE jobs SET scheduled_start=?, scheduled_end=? WHERE id=?",
                ((jday + timedelta(hours=7)).isoformat(),
                 (jday + timedelta(hours=7 + 8 * shifts_count)).isoformat(),
                 j["id"]))
    conn.commit()

    for lid, lst in by_line.items():
        for j in lst:
            total_jh = 0.0
            for sh_i in range(j["_shifts"]):
                sh_start = j["_start"].replace(
                    hour=SHIFTS[sh_i][0], minute=0, second=0, microsecond=0)
                sh_end = sh_start + timedelta(hours=8)
                shift_val = str(sh_i + 1)
                for h in range(7):
                    if h == 4:
                        continue
                    hour_start = sh_start + timedelta(hours=h)
                    units = int(j["_rate"] * random.uniform(0.93, 0.99))
                    c.execute(
                        """INSERT INTO hourly_runs
                        (job_id,line_id,shift,period,recorded_at,units_filled,duration_min,phase,
                         job_hour_start,job_hour_end,user_id,flagged,source,sku_id)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (j["id"], lid, shift_val, f"H{h+1}", hour_start.isoformat(),
                         units, 60, 'run', total_jh / 60, (total_jh + 60) / 60,
                         1, 0, 'demo', j["sku_id"]))
                    total_jh += 60
                hour8_start = sh_start + timedelta(hours=7)
                units8 = int(j["_rate"] * 0.5 * random.uniform(0.93, 0.99))
                c.execute(
                    """INSERT INTO hourly_runs
                    (job_id,line_id,shift,period,recorded_at,units_filled,duration_min,phase,
                     job_hour_start,job_hour_end,user_id,flagged,source,sku_id)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (j["id"], lid, shift_val, 'H8', hour8_start.isoformat(),
                     units8, 30, 'run', total_jh / 60, (total_jh + 30) / 60,
                     1, 0, 'demo', j["sku_id"]))
                total_jh += 30
                prod_end = sh_start + timedelta(minutes=450)
                lunch_end = prod_end + timedelta(minutes=30)
                c.execute(
                    """INSERT INTO line_events (line_id,state,started_at,ended_at,job_id,user_id,source)
                       VALUES (?,?,?,?,?,?,'demo')""",
                    (lid, 'production', sh_start.isoformat(),
                     prod_end.isoformat(), j["id"], 1))
                c.execute(
                    """INSERT INTO line_events (line_id,state,started_at,ended_at,reason,user_id,source)
                       VALUES (?,?,?,?,?,?,'demo')""",
                    (lid, 'lunch', prod_end.isoformat(),
                     lunch_end.isoformat(), 'scheduled', 1))
                c.execute("UPDATE jobs SET status='completed', actual_end=? WHERE id=?",
                          (sh_end.isoformat(), j["id"]))
    conn.commit()

    for lid, lst in by_line.items():
        for i in range(len(lst) - 1):
            fr, to = lst[i], lst[i + 1]
            if fr["sku_id"] == to["sku_id"]:
                continue
            proc = procedures.get((lid, fr["sku_id"], to["sku_id"]))
            if not proc:
                continue
            co_start = fr["_start"] + timedelta(days=2, hours=16)
            co_actual = int(proc["aggregate_standard_min"] * random.uniform(0.85, 1.30))
            co_end = co_start + timedelta(minutes=co_actual)
            c.execute(
                """INSERT INTO co_events (procedure_id,line_id,started_at,ended_at,
                   aggregate_actual_min,from_job_number,to_job_number,source)
                   VALUES (?,?,?,?,?,?,?,'demo')""",
                (proc["id"], lid, co_start.isoformat(), co_end.isoformat(),
                 co_actual, fr["job_number"], to["job_number"]))
            co_id = c.lastrowid
            write_co_event_changes(c, co_id, fr["sku_id"], to["sku_id"])
            for s in c.execute(
                "SELECT * FROM co_steps_v2 WHERE procedure_id=? ORDER BY seq",
                (proc["id"],)).fetchall():
                c.execute(
                    "INSERT INTO co_event_steps (event_id,step_id,actual_min) VALUES (?,?,?)",
                    (co_id, s["id"], round(s["standard_min"] * random.uniform(0.7, 1.4), 1)))
            c.execute(
                """INSERT INTO line_events (line_id,state,started_at,ended_at,
                   co_event_id,user_id,source) VALUES (?,?,?,?,?,?,'demo')""",
                (lid, 'changeover', co_start.isoformat(), co_end.isoformat(), co_id, 1))
    conn.commit()

    NOW = datetime.now()
    STAGGER = [3.0, 2.2, 1.5, 4.1, 2.7]
    for i, lid in enumerate(sorted(by_line.keys())):
        lst = by_line[lid]
        last = max(lst, key=lambda j: j["_start"])
        started = (NOW - timedelta(hours=STAGGER[i])).replace(
            minute=0, second=0, microsecond=0)
        c.execute(
            """INSERT INTO line_events (line_id,state,started_at,ended_at,
               job_id,user_id,source) VALUES (?,?,?,NULL,?,?,'demo')""",
            (lid, 'production', started.isoformat(), last["id"], 1))
        c.execute("UPDATE jobs SET status='running', actual_end=NULL WHERE id=?",
                  (last["id"],))
        for h in range(int(STAGGER[i])):
            hr = started + timedelta(hours=h)
            units = int(last["_rate"] * random.uniform(0.93, 0.99))
            c.execute(
                """INSERT INTO hourly_runs
                (job_id,line_id,shift,period,recorded_at,units_filled,duration_min,phase,
                 job_hour_start,job_hour_end,user_id,flagged,source,sku_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (last["id"], lid, '1', f"H{h+1}", hr.isoformat(),
                 units, 60, 'run', h, h + 1, 1, 0, 'demo', last["sku_id"]))
            if not c.execute("SELECT 1 FROM hourly_runs WHERE job_id=? AND period='H6'", (last["id"],)).fetchone():
                for extra in [6, 7, 8]:
                    extra_hr = started + timedelta(hours=extra)
                    extra_units = int(last["_rate"] * random.uniform(0.93, 0.99))
                    extra_dur = 30 if extra == 8 else 60
                    c.execute("""INSERT INTO hourly_runs
                        (job_id,line_id,shift,period,recorded_at,units_filled,duration_min,phase,
                         job_hour_start,job_hour_end,user_id,flagged,source,sku_id)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (last["id"], lid, '1', f"H{extra}", extra_hr.isoformat(),
                         extra_units, extra_dur, 'run', extra, extra + extra_dur/60.0, 1, 0, 'demo', last["sku_id"]))
        total_units = c.execute(
            "SELECT SUM(units_filled) FROM hourly_runs WHERE job_id=?",
            (last["id"],)).fetchone()[0] or 0
        progress = random.uniform(0.55, 0.65)
        new_target = int(total_units / progress)
        c.execute("UPDATE jobs SET target_quantity=? WHERE id=?",
                  (new_target, last["id"]))
    conn.commit()

    if c.execute("SELECT COUNT(*) FROM experiments").fetchone()[0] == 0:
        EXPS = [
            (1, "Pre-stage case parts on shadow board", "Production", 1,
             "Change case", "2026-10-10", 14, 8, "Method"),
            (2, "Pre-load label roll before end of run", "Production", 3,
             "Change label", "2026-10-10", 9, 4, "Method"),
            (3, "Reduce seamer parts retrieval time", "Production", 3,
             "Verify seam", "2026-10-10", 10, 5, "Machine"),
            (4, "Standardize jar changeover", "Production", 5,
             "Change jar", "2026-10-10", 8, 4, "Method"),
            (5, "Reduce formulation flush time", "Production", 2,
             "Change formulation", "2026-10-10", 12, 7, "Method"),
        ]
        for eid, t, d, lid, ts, sd, std, goal, cat in EXPS:
            c.execute(
                """INSERT INTO experiments (id,title,department,line_id,status,
                   target_step_name,start_date,standard_min,target_goal_min,
                   fishbone_category) VALUES (?,?,?,?,'active',?,?,?,?,?)""",
                (eid, t, d, lid, ts, sd, std, goal, cat))
        conn.commit()

    # Agreed 2026-11-06: seed one demo maintenance event so OEE and operator
    # performance visibly diverge. Line 4, day of highest production (not
    # most recent): 180 min on a 240-min day reads 55% OEE and looks
    # alarming; on a 780-min day it reads ~78%, the plausible mid-70s story.
    # 180 min chosen to separate the two measures by ~13 points. job_id
    # links to the running line-4 job so /job/<number> shows the block.
    already = c.execute("SELECT COUNT(*) FROM maintenance_events WHERE source='demo'").fetchone()[0]
    if already == 0:
        row = c.execute("""SELECT date(recorded_at) AS d, SUM(units_filled) AS u FROM hourly_runs
                           WHERE line_id=4 GROUP BY date(recorded_at)
                           ORDER BY u DESC LIMIT 1""").fetchone()
        if row:
            md = row["d"]
            job_row = c.execute("SELECT id FROM jobs WHERE line_id=4 AND status='running' LIMIT 1").fetchone()
            jid = job_row["id"] if job_row else None
            c.execute("""INSERT INTO maintenance_events
                (line_id, job_id, station, started_at, ended_at, aggregate_actual_min,
                 category, symptom, resolution, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'demo', ?)""",
                (4, jid, 'filler', md + 'T10:00:00', md + 'T13:00:00', 180,
                 'unplanned', 'Filler nozzle clog', 'Cleared and reseated',
                 md + 'T13:05:00'))
            conn.commit()
            print(f"  Seeded maintenance: line 4, {md}, 180 min, job {jid}")
    print("HISTORY GENERATED")
    for t in ["hourly_runs", "co_events", "co_event_changes", "experiments"]:
        print(f"  {t:20s} "
              f"{c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]}")
    print("\nCurrently running:")
    for r in c.execute(
        """SELECT j.job_number, j.line_id, j.target_quantity,
           (SELECT SUM(units_filled) FROM hourly_runs WHERE job_id=j.id) AS produced
           FROM jobs j WHERE status='running' ORDER BY j.line_id"""):
        pct = (r["produced"] / r["target_quantity"] * 100) if r["target_quantity"] else 0
        print(f"  Line {r['line_id']} {r['job_number']}: "
              f"{r['produced']:,} / {r['target_quantity']:,} = {pct:.1f}%")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
