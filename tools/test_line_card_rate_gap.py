#!/usr/bin/env python3
"""A50: the line card when a SKU has no rate on its line.

Two defects, both of the same family as A01 and both with a zero where an
unknown belongs.

The view v_unaccounted_minutes_by_run ended with "AND lsr.ideal_rate > 0", so an
hour with no rate disappeared from the view altogether and took its recorded
downtime with it. Downtime is a duration read off downtime_events; it never
needed a rate. A card could therefore say no downtime was recorded about an hour
that had a logged repair.

The line card itself priced that silence as a figure: lost capacity was summed
with COALESCE(rate, 0), so no rate read as no loss, and the card reconciled its
losses to zero and then reported a capacity gap beside them.

What must be true now: the row survives a missing rate, the rate-derived columns
are NULL rather than zero, recorded downtime survives with it, capacity_gap is
still computable because it compares production with the target, and
losses_accounted and losses_unexplained are unknown rather than zero. The rated
line is asserted just as hard, to the old arithmetic, so a fix that flattened
both lines into dashes fails here.

Run: /home/jeeves/jeeves-env/bin/python tools/test_line_card_rate_gap.py
Exit 0 when every check passes, 1 when any fails, 2 when it cannot start.
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "myarr_v2"))

WORK = tempfile.mkdtemp(prefix="myarra_ratecard_")
DB = os.path.join(WORK, "ratecard.db")
os.environ["MYARRA_DB"] = DB

try:
    import db as myarra_db
    myarra_db.init_db()
    import views
    import herbie
except Exception as exc:                                    # noqa: BLE001
    print("CANNOT START: %s" % exc)
    shutil.rmtree(WORK, ignore_errors=True)
    sys.exit(2)

DASH = "\u2014"
DAY = datetime.now().strftime("%Y-%m-%d")
RUN_AT = DAY + "T08:00:00"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
conn.executescript(
    """
    INSERT INTO lines (id, name) VALUES (1, 'Line 1'), (2, 'Line 2');
    INSERT INTO skus (id, part_number, description, case_pack)
        VALUES (1, 'PN-RATED', 'Wallet, rate loaded', 1),
               (2, 'PN-NORATE', 'Wallet, no rate on line 2', 1);
    INSERT INTO line_sku_rates (line_id, sku_id, ideal_rate) VALUES (1, 1, 1200.0);
    """
)
for job_id, job_number, sku_id, line_id in ((1, "WO-1200-001", 1, 1),
                                            (2, "WO-1200-002", 2, 2)):
    conn.execute(
        "INSERT INTO jobs (id, job_number, sku_id, line_id, target_quantity,"
        " scheduled_start, status) VALUES (?,?,?,?,1000,?,'running')",
        (job_id, job_number, sku_id, line_id, DAY))
    conn.execute(
        "INSERT INTO hourly_runs (id, job_id, line_id, sku_id, shift, period,"
        " recorded_at, units_filled, scrap_units, duration_min, source)"
        " VALUES (?,?,?,?,'S1','H1',?,?,?,60,'floor')",
        (job_id, job_id, line_id, sku_id, RUN_AT,
         1000 if job_id == 1 else 900, 20 if job_id == 1 else 25))
conn.execute(
    "INSERT INTO downtime_events (run_id, station, reason, minutes)"
    " VALUES (1, 'Filler', 'capper jam', 20),"
    "        (2, 'Filler', 'label roll change', 15)")
conn.commit()
views.ensure_views(conn)

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    line = ("PASS  " if ok else "FAIL  ") + name
    if not ok and detail:
        line += "\n        " + str(detail)[:400]
    print(line)


# ------------------------------------------------- the view keeps the row

rows = conn.execute(
    "SELECT * FROM v_unaccounted_minutes_by_run ORDER BY run_id").fetchall()
check("the view keeps an hour that has no rate", len(rows) == 2,
      "rows=%d" % len(rows))

row2 = conn.execute(
    "SELECT * FROM v_unaccounted_minutes_by_run WHERE run_id = 2").fetchone()
unrated = dict(row2) if row2 else {}
check("the unrated row still carries its recorded downtime",
      row2 is not None and unrated.get("recorded_downtime_min") == 15,
      "recorded_downtime_min=%r" % (unrated.get("recorded_downtime_min"),))

check("the unrated row's rate-derived figures are NULL, not zero",
      row2 is not None
      and "gap_units" in unrated and unrated["gap_units"] is None
      and "gap_min" in unrated and unrated["gap_min"] is None
      and "unaccounted_min" in unrated and unrated["unaccounted_min"] is None,
      "row=%r" % (unrated,))

check("the unrated row says how much of itself could not be scored",
      row2 is not None and unrated.get("unrated_min") == 60,
      "unrated_min=%r" % (unrated.get("unrated_min"),))

row1 = conn.execute(
    "SELECT * FROM v_unaccounted_minutes_by_run WHERE run_id = 1").fetchone()
rated_row = dict(row1) if row1 else {}
check("the rated row is scored as before and carries no unrated minutes",
      row1 is not None and rated_row.get("unrated_min") == 0
      and rated_row.get("gap_units") == 200
      and rated_row.get("gap_min") == 10.0,
      "unrated_min=%r gap_units=%r gap_min=%r"
      % (rated_row.get("unrated_min"), rated_row.get("gap_units"),
         rated_row.get("gap_min")))

# ------------------------------------------------------ the line card

stats = herbie.get_line_summary(conn, 2, DAY)
check("no rate: the card says the rate figures are unknown rather than zero",
      stats.get("rate_loaded") is False
      and "lost_capacity" in stats and stats["lost_capacity"] is None
      and "losses_accounted" in stats and stats["losses_accounted"] is None
      and "losses_unexplained" in stats and stats["losses_unexplained"] is None
      and "theoretical_capacity" in stats
      and stats["theoretical_capacity"] is None,
      json.dumps({k: stats.get(k, "<absent>") for k in
                  ("rate_loaded", "lost_capacity", "losses_accounted",
                   "losses_unexplained", "theoretical_capacity")}))

check("no rate: the capacity gap survives, because it compares with the target",
      stats["capacity_gap"] == 900 - 1000,
      "capacity_gap=%r" % (stats["capacity_gap"],))

check("no rate: the card names the SKU and the line and the unrated minutes",
      "PN-NORATE" in stats.get("reconciliation", "")
      and "Line 2" in stats.get("reconciliation", "")
      and stats.get("unrated_min") == 60
      and stats.get("unrated_downtime_min") == 15.0,
      stats.get("reconciliation"))

check("no rate: the payload sent to the model carries null, not zero",
      '"losses_accounted": null' in json.dumps(stats)
      and '"lost_capacity": null' in json.dumps(stats),
      json.dumps(stats)[:300])

body = herbie.narrate_capacity_gap(stats, "")
check("no rate: the template dashes the loss figures and prints no None",
      DASH in body and "None" not in body
      and "not computed" in body and "15" in body,
      body)

# ------------------------------------------------- the rated line, unchanged

rated = herbie.get_line_summary(conn, 1, DAY)
check("a rated line still prices its downtime in parts",
      rated["lost_capacity"] == 400 and rated["rate_loaded"] is True,
      "lost_capacity=%r" % (rated["lost_capacity"],))

check("a rated line computes the gap from produced parts plus the downtime "
      "uplift, and no longer adds scrap a second time",
      rated["gross_production"] == 1000
      and rated["theoretical_capacity"] == 1400
      and rated["capacity_gap"] == 400
      and rated["losses_accounted"] == 420
      and rated["losses_unexplained"] == 0,
      json.dumps({k: rated[k] for k in
                  ("gross_production", "theoretical_capacity", "capacity_gap",
                   "losses_accounted", "losses_unexplained")}))

check("scrap is not counted twice: gross production is the parts produced, "
      "on both lines",
      rated["gross_production"] == rated["actual_units"] == 1000
      and stats["gross_production"] == stats["actual_units"] == 900,
      "rated gross=%r actual=%r, unrated gross=%r actual=%r"
      % (rated["gross_production"], rated["actual_units"],
         stats["gross_production"], stats["actual_units"]))

body = herbie.narrate_capacity_gap(rated, "")
check("a rated line's template still reports numbers and no dash",
      DASH not in body and "Losses accounted for: 420 units" in body,
      body)

# ------------------------------------- the other cards that read the view

job = herbie.get_job_summary(conn, "WO-1200-002")
check("the job card no longer loses downtime on an unrated hour",
      job["recorded_downtime_min"] == 15 and job["unrated_min"] == 60,
      "recorded=%r unrated=%r"
      % (job["recorded_downtime_min"], job.get("unrated_min")))

unacc = herbie.get_unaccounted_minutes(conn, 2, 30)
check("the unaccounted card reports the recorded time and says how much is unscored",
      unacc["recorded_min"] == 15 and unacc["unrated_min"] == 60
      and unacc["unaccounted_min"] == 0,
      json.dumps({k: unacc[k] for k in ("recorded_min", "unrated_min",
                                        "unaccounted_min")}))

conn.close()
failed = RESULTS.count(False)
print("")
print("%d checks, %d failed" % (len(RESULTS), failed))
if failed:
    print("Database kept for inspection: " + DB)
else:
    shutil.rmtree(WORK, ignore_errors=True)
sys.exit(1 if failed else 0)
