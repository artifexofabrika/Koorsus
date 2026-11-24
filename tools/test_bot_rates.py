#!/usr/bin/env python3
"""A01, the Telegram half: what the bot does when a SKU has no rate on its line.

bot/db.py ideal_rate() returned 600.0 when no rate row existed, and five call
sites in production.py and shift.py did arithmetic on the result, so a plant
with an unloaded rate got confident answers to questions nobody could answer:
expected units, the gap, unaccounted minutes, a plausibility challenge that
stopped the operator, the flagged hour, and the shift residual. shift.py added
two more substitutions of its own on the way through.

The reference appliance has a rate for every open job, and two SKU-line pairs
carry none on purpose, so walking the bot by hand rarely lands on the defect.
This builds its own database with a rated pair and an unrated pair and drives
the bot's own functions at both. The rated pair is asserted as hard as the
unrated one: a fix that simply deleted the arithmetic fails here too.

Run: /home/jeeves/jeeves-env/bin/python tools/test_bot_rates.py
Exit 0 when every check passes, 1 when any fails, 2 when it cannot start.
"""
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "myarr_v2"))

WORK = tempfile.mkdtemp(prefix="myarra_botrates_")
DB = os.path.join(WORK, "botrates.db")
os.environ["MYARRA_DB"] = DB

try:
    import db as myarra_db
    myarra_db.init_db()
    from bot import db as bdb
    from bot import production
    from bot import resolve
    from bot import shift
except Exception as exc:                                    # noqa: BLE001
    print("CANNOT START: %s" % exc)
    shutil.rmtree(WORK, ignore_errors=True)
    sys.exit(2)

DASH = "\u2014"
DAY = datetime.now().strftime("%Y-%m-%d")
# Inside today's S1 window (07:00-15:00), so shift reconciliation sees it
# whenever this test is run.
RUN_AT = DAY + "T08:00:00"


def seed():
    c = sqlite3.connect(DB)
    c.executescript(
        """
        INSERT INTO lines (id, name) VALUES (1, 'Line 1'), (2, 'Line 2');
        INSERT INTO skus (id, part_number, description, case_pack)
            VALUES (1, 'PN-RATED', 'Wallet, rate loaded', 12),
                   (2, 'PN-NORATE', 'Wallet, no rate on line 2', 1);
        INSERT INTO jobs (id, job_number, sku_id, line_id, target_quantity, status)
            VALUES (1, 'WO-1200-001', 1, 1, 1200, 'running'),
                   (2, 'WO-1200-002', 2, 2, 1000, 'running');
        INSERT INTO users (id, name, role, line_id, telegram_id, active)
            VALUES (1, 'Lead', 'Operator', 1, '111', 1),
                   (2, 'Lead Two', 'Operator', 2, '222', 1);
        INSERT INTO settings (key, value) VALUES
            ('unit_label', 'units'), ('case_label', 'cases');
        """
    )
    # The rated pair, and nothing for (line 2, sku 2). The absence is the
    # subject of the test.
    c.execute("INSERT INTO line_sku_rates (line_id, sku_id, ideal_rate)"
              " VALUES (1, 1, 1200.0)")
    # A row holding zero cannot divide anything, so it counts as absent.
    c.execute("INSERT INTO line_sku_rates (line_id, sku_id, ideal_rate)"
              " VALUES (1, 2, 0.0)")
    for job_id, line_id, sku_id, units, scrap in (
            (1, 1, 1, 1200, 25), (2, 2, 2, 900, 25)):
        c.execute(
            "INSERT INTO hourly_runs (job_id, line_id, sku_id, shift, period,"
            " recorded_at, units_filled, scrap_units, duration_min, source)"
            " VALUES (?,?,?,'S1',?,?,?,?,60,'telegram')",
            (job_id, line_id, sku_id, "H1", RUN_AT, units, scrap))
    c.commit()
    rows = c.execute("SELECT COUNT(*) FROM line_sku_rates").fetchone()[0]
    c.close()
    return rows


RATE_ROWS = seed()

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    line = ("PASS  " if ok else "FAIL  ") + name
    if not ok and detail:
        line += "\n        " + str(detail)[:400]
    print(line)


conn = bdb.connect()
rated_job = {"id": 1, "job_number": "WO-1200-001", "line_id": 1, "sku_id": 1}
unrated_job = {"id": 2, "job_number": "WO-1200-002", "line_id": 2, "sku_id": 2}
user_one = {"id": 1, "line_id": 1}
user_two = {"id": 2, "line_id": 2}

check("fixture: one configured rate and one zero row, nothing for line 2 / sku 2",
      RATE_ROWS == 2, "line_sku_rates holds %r rows" % (RATE_ROWS,))

# ---------------------------------------------------------------- ideal_rate

r = bdb.ideal_rate(conn, 1, 1)
check("db.ideal_rate returns the configured rate when one exists",
      r == 1200.0, "got %r" % (r,))

r = bdb.ideal_rate(conn, 2, 2)
check("db.ideal_rate returns None when the SKU has no rate on that line",
      r is None, "got %r" % (r,))

r = bdb.ideal_rate(conn, 1, 2)
check("db.ideal_rate treats a zero rate as no rate rather than dividing by it",
      r is None, "got %r" % (r,))

check("bot/resolve.py no longer offers a second ideal_rate with its own 600.0",
      not hasattr(resolve, "ideal_rate"))

# ---------------------------------------------------------- _summarize, chat

text = production._summarize(conn, unrated_job, 3, 900, 25, 60.0, 2.0, 3.0,
                             None, user=user_two)
check("_summarize with no rate names the SKU and the line and invents no figure",
      "600" not in text and "Expected" not in text and "Gap:" not in text
      and "PN-NORATE" in text and "Line 2" in text and "FTQ 97.2%" in text,
      text)

text = production._summarize(conn, rated_job, 3, 1100, 0, 60.0, 2.0, 3.0,
                             5.0, user=user_one)
check("_summarize with a rate still does the arithmetic",
      "Expected 1,200 at 1,200/hr" in text and "Gap: 100 units (5.0 min)" in text
      and "No rate" not in text,
      text)

text = production._summarize(conn, rated_job, 3, 1100, 0, 60.0, 2.0, 3.0,
                             None, user=user_one)
check("_summarize with a rate and no measured gap says so instead of raising",
      "Gap: 100 units (no minutes measured)" in text,
      text)

# --------------------------------------------------- the plausibility gate

s1 = bdb.Session(conn, "chat-unrated")
reply = production.h_running_job(conn, s1, "running WO-1200-002 hour 3 900 units",
                                 user_two)
check("h_running_job does not challenge an hour it has no rate to judge",
      "Recorded:" in reply and "far above" not in reply and "600" not in reply,
      reply)

row = conn.execute(
    "SELECT units_filled, flagged, duration_min FROM hourly_runs"
    " WHERE job_id=2 ORDER BY id DESC LIMIT 1").fetchone()
check("the hour written with no rate carries its units and is not flagged",
      row is not None and row["units_filled"] == 900 and row["flagged"] == 0,
      "row=%r" % (dict(row) if row else None,))

s2 = bdb.Session(conn, "chat-unrated-flow")
reply = production.h_record_hour(
    conn, s2, "record WO-1200-002 H4, 60 minutes, 900 units, 20 scrap", user_two)
check("the conversational record path also records instead of challenging",
      "Recorded:" in reply and "far above" not in reply and "600" not in reply,
      reply)

# ------------------------------------------------ shift reconciliation, math

rec_unrated = shift.compute_reconciliation(conn, 2, "S1", DAY)
tot = conn.execute(
    "SELECT SUM(units_filled) AS u, SUM(scrap_units) AS s FROM hourly_runs"
    " WHERE line_id=2").fetchone()
check("compute_reconciliation still totals units, scrap and FTQ with no rate",
      rec_unrated["actual_units"] == tot["u"]
      and rec_unrated["scrap_units"] == tot["s"]
      and abs(rec_unrated["ftq_pct"]
              - ((tot["u"] - tot["s"]) / tot["u"] * 100.0)) < 1e-9,
      "rec=%r tot=%r" % (dict(rec_unrated), dict(tot)))

check("compute_reconciliation invents no production time or residual with no rate",
      rec_unrated["production_time_min"] is None
      and rec_unrated["scrap_time_min"] is None
      and rec_unrated["residual_min"] is None
      and rec_unrated["rate"] is None
      and "PN-NORATE" in (rec_unrated["rate_missing"] or ""),
      "rec=%r" % (dict(rec_unrated),))

rec_rated = shift.compute_reconciliation(conn, 1, "S1", DAY)
check("compute_reconciliation still scores a rated line, run by run",
      abs(rec_rated["production_time_min"] - ((1200 - 25) / 1200.0 * 60.0)) < 1e-9
      and rec_rated["residual_min"] is not None
      and rec_rated["rate"] == 1200.0
      and rec_rated["rate_missing"] is None,
      "rec=%r" % (dict(rec_rated),))

body = shift._report(rec_unrated, "Line 2")
check("the report dashes the residual and states why, without a number",
      DASH in body and "600" not in body and "balanced" not in body
      and "Residual:" in body and "PN-NORATE" in body,
      body)

body = shift._report(rec_rated, "Line 1")
rated_residual = 480.0 - (1175 / 1200.0 * 60.0) - (25 / 1200.0 * 60.0)
check("the report still reports a rated line as a number",
      ("Residual:    %+.1f min unaccounted" % rated_residual) in body
      and "not computed" not in body,
      body)

# ------------------------------------------------------- end shift behaviour

s3 = bdb.Session(conn, "chat-end-unrated")
s3.set("line_id", 2)
s3.set("shift", "S1")
s3.save()
reply = shift.h_end_shift(conn, s3, "end shift", user_two)
check("end shift on an unrated line closes without asking an unanswerable question",
      "What happened?" not in reply and "Shift closed" in reply
      and "600" not in reply,
      reply)

last = conn.execute(
    "SELECT residual_min, explanation FROM shift_reconciliations"
    " ORDER BY id DESC LIMIT 1").fetchone()
check("the closed shift records the absence rather than a zero",
      last is not None and last["residual_min"] is None
      and "no rate" in (last["explanation"] or "").lower(),
      "row=%r" % (dict(last) if last else None,))

s4 = bdb.Session(conn, "chat-end-rated")
s4.set("line_id", 1)
s4.set("shift", "S1")
s4.save()
reply = shift.h_end_shift(conn, s4, "end shift", user_one)
check("end shift on a rated line still asks for the reason it is owed",
      "What happened?" in reply and s4.get("state") == "awaiting_shift_reason",
      reply)

failed = RESULTS.count(False)
print("")
print("%d checks, %d failed" % (len(RESULTS), failed))
if failed:
    print("Database kept for inspection: " + DB)
else:
    conn.close()
    shutil.rmtree(WORK, ignore_errors=True)
sys.exit(1 if failed else 0)
