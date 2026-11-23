#!/usr/bin/env python3
"""Seed the improvement layer that the 90-day history generator does not write.

tools/gen_myarra_90d.py generates operations: jobs, hourly runs, line events,
changeovers and downtime. It writes no experiments and no maintenance events,
so after regenerating a database with it, /pdca renders empty, /maintenance
renders empty, and A22 gets worse rather than better: six thousand hourly runs
and still nothing in maintenance_events.

This adds the five PDCA experiments and three maintenance events that the older
30-day generator carried, sized for the 90-day history, and it is idempotent by
marker rather than by id. It deletes only rows whose notes column carries its
own stamp, and only maintenance rows whose source it owns.

A deliberate limitation, stated so nobody assumes otherwise: it writes no
line_events rows in the maintenance state. The line timeline from the history
generator is continuous, with exactly one open event per line, so splicing a
maintenance event into a past production window would break the one invariant
the rest of the product rests on. State history belongs inside the generator,
where the timeline is constructed, not bolted onto it afterwards. What this
gives you is the office record: what broke, on which station, and how long it
took, attached to the job that suffered it.

Run:  /home/jeeves/jeeves-env/bin/python tools/seed_improvement_layer.py
      --db /mnt/lake/myarra.db        (the default)
"""
import argparse
import sqlite3
import sys
from datetime import datetime, timedelta

MARK = "seeded by tools/seed_improvement_layer.py"
SOURCE = "seed90"

# (title, department, line_id, target_step_name, start_date, standard_min,
#  target_goal_min, fishbone_category, pri_time, pri_impact, pri_resources,
#  pri_magnitude, pri_cost, current_condition, target_condition)
EXPERIMENTS = [
    ("Pre-stage compact cases on the shadow board", "Production", 1,
     "Change case", "2026-09-08", 14.0, 8.0, "Method", 3, 2, 1, 2, 1,
     "Case stock kept in the aisle; the feeder stops while a pallet is fetched.",
     "Two hours of cases staged at the line before the changeover starts."),
    ("Pre-load the label roll before end of run", "Production", 3,
     "Change label", "2026-09-24", 9.0, 4.0, "Method", 2, 3, 1, 2, 2,
     "A new roll is fetched after the last can of the run, not before.",
     "Roll staged during the final hour of the run and spliced at changeover."),
    ("Reduce seamer parts retrieval time", "Production", 3,
     "Verify seam", "2026-10-11", 10.0, 5.0, "Machine", 4, 4, 2, 3, 3,
     "Seamer spares live in the stores and one person goes for them.",
     "A shadow-board kit at the seamer holding the four parts that wear."),
    ("Standardise the jar changeover", "Production", 5,
     "Change jar", "2026-10-29", 8.0, 4.0, "Method", 3, 3, 1, 2, 1,
     "Each lead sets the jar rail by feel; two people get two different times.",
     "One photographed sequence, agreed by both leads, pinned at the line."),
    ("Reduce formulation flush time", "Production", 2,
     "Change formulation", "2026-11-13", 12.0, 7.0, "Method", 5, 3, 2, 4, 2,
     "Flush volume is set by habit and varies by forty percent between leads.",
     "A measured flush volume with the timer running, recorded every time."),
]

# (experiment index, category, cause)
FISHBONE = [
    (0, "Method", "No staged case stock at the line"),
    (0, "Man", "Only one lead trained on the feeder"),
    (0, "Machine", "Feeder cannot run on a half pallet"),
    (2, "Machine", "Seamer spares held in stores, not at the line"),
    (2, "Method", "No kit list for seamer wear parts"),
    (4, "Measurement", "Flush volume never measured, only estimated"),
    (4, "Method", "No standard flush volume between formulations"),
]

# (line_id, station, symptom, resolution, minutes, category)
MAINTENANCE = [
    (3, "seamer", "Seam roller running tight on one head",
     "Roller replaced and the head re-shimmed; seams re-verified on ten cans",
     180.0, "unplanned"),
    (4, "filler", "Filler nozzle clogged, short fills on one valve",
     "Nozzle cleared and reseated, valve flow re-checked",
     95.0, "unplanned"),
    (5, "labeler", "Label web tracking off after a splice",
     "Web re-threaded and the splice sensor cleaned",
     55.0, "unplanned"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/mnt/lake/myarra.db")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if cur.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0:
        print("REFUSING: no jobs. Run tools/gen_myarra_90d.py first.")
        return 1

    now = datetime.now().isoformat()

    # idempotent: remove only what this script wrote
    cur.execute("DELETE FROM fishbone_causes WHERE experiment_id IN "
                "(SELECT id FROM experiments WHERE notes=?)", (MARK,))
    cur.execute("DELETE FROM experiments WHERE notes=?", (MARK,))
    cur.execute("DELETE FROM maintenance_events WHERE source=?", (SOURCE,))

    exp_ids = []
    for (title, dept, lid, step, start, std, goal, cat,
         pt, pi, pr, pm, pc, cur_cond, tgt_cond) in EXPERIMENTS:
        cur.execute(
            """INSERT INTO experiments
               (title, department, line_id, status, target_step_name, start_date,
                standard_min, target_goal_min, fishbone_category, pri_time,
                pri_impact, pri_resources, pri_magnitude, pri_cost,
                current_condition, target_condition, pdca_owner, notes,
                created_at, updated_at)
               VALUES (?,?,?,'active',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (title, dept, lid, step, start, std, goal, cat, pt, pi, pr, pm, pc,
             cur_cond, tgt_cond, "Line lead", MARK, now, now))
        exp_ids.append(cur.lastrowid)

    for (idx, cat, cause) in FISHBONE:
        cur.execute(
            "INSERT INTO fishbone_causes (experiment_id, category, cause_text,"
            " seq, created_at) VALUES (?,?,?,?,?)",
            (exp_ids[idx], cat, cause, 0, now))

    made = []
    for (lid, station, symptom, resolution, minutes, category) in MAINTENANCE:
        # Attach the repair to a job that can hold it: a window long enough for
        # the repair, and the job on that line that already collected the most
        # downtime, so the record agrees with the hours rather than inventing a
        # bad day that the runs do not show.
        row = cur.execute(
            """SELECT j.id, j.job_number, j.scheduled_start
               FROM jobs j
               WHERE j.line_id = ? AND j.status = 'completed'
                 AND j.scheduled_start IS NOT NULL
                 AND j.scheduled_end IS NOT NULL
                 AND (julianday(j.scheduled_end) - julianday(j.scheduled_start))
                     * 1440.0 >= ?
               ORDER BY (SELECT COUNT(*) FROM downtime_events de
                         JOIN hourly_runs r ON r.id = de.run_id
                         WHERE r.job_id = j.id) DESC,
                        j.scheduled_start
               LIMIT 1""", (lid, minutes)).fetchone()
        if not row:
            print("  line %d: no completed job long enough to hold a repair, "
                  "skipped" % lid)
            continue
        day = str(row["scheduled_start"])[:10]
        began = datetime.fromisoformat(str(row["scheduled_start"]))
        started = began.replace(hour=min(10, began.hour), minute=0,
                                second=0, microsecond=0)
        ended = started + timedelta(minutes=minutes)
        cur.execute(
            """INSERT INTO maintenance_events
               (line_id, job_id, station, started_at, ended_at,
                aggregate_actual_min, category, symptom, resolution, source,
                created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (lid, row["id"], station, started.isoformat(), ended.isoformat(),
             minutes, category, symptom, resolution, SOURCE, now))
        made.append((lid, row["job_number"], started.isoformat()[:16],
                     int(minutes)))

    conn.commit()

    print("improvement layer seeded")
    print("  experiments        %d" % len(exp_ids))
    print("  fishbone causes    %d" % len(FISHBONE))
    print("  maintenance events %d" % len(made))
    for (lid, jn, day, mins) in made:
        print("    line %d  %s  %s  %d min" % (lid, jn, day, int(mins)))
    print("")
    print("  %-34s %s" % ("experiments total", cur.execute(
        "SELECT COUNT(*) FROM experiments").fetchone()[0]))
    print("  %-34s %s" % ("maintenance_events total", cur.execute(
        "SELECT COUNT(*) FROM maintenance_events").fetchone()[0]))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
