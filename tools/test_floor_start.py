#!/usr/bin/env python3
"""Floor start, end and the three switches: fifteen cases, throwaway database.

Nothing in here touches the live database. MYARRA_DB is pointed at a temp file
before anything from myarr_v2 is imported, the schema is applied from
tools/schema.sql, and every assertion reads back through a fresh connection
rather than through the app's own, so what is checked is what reached the disk.

Case 2 induces a real failure inside SQLite with a BEFORE INSERT trigger on
line_events. A monkeypatched exception would only prove that the except block
runs; a trigger proves the transaction rolls back.

Run: /home/jeeves/jeeves-env/bin/python tools/test_floor_start.py
Exit 0 when all fifteen pass, 1 when any fail, 2 when the test cannot start.
"""
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "myarr_v2"))

WORK = tempfile.mkdtemp(prefix="myarra_floor_start_")
DB = os.path.join(WORK, "floor_start.db")
os.environ["MYARRA_DB"] = DB

# app.py pings the model at import time and ask.py builds its view cache at
# import time (A21). Both happen before any route is reachable, so a dead model
# would make this test fail for a reason that has nothing to do with /floor.
import myarra_settings

myarra_settings.check_llm = lambda *a, **k: (True, "stubbed by test_floor_start")

import db as myarra_db

myarra_db.init_db()

from bot import jobs as bot_jobs

try:
    import app as webapp
except Exception as exc:                                    # noqa: BLE001
    print("CANNOT START: importing app failed: %s" % exc)
    print("A21 is the known cause: import-time side effects in app.py and ask.py.")
    shutil.rmtree(WORK, ignore_errors=True)
    sys.exit(2)

client = webapp.app.test_client()


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def seed():
    c = conn()
    c.executescript(
        """
        INSERT INTO lines (id, name) VALUES
            (1, 'Line 1'), (2, 'Line 2'), (3, 'Line 3'), (4, 'Line 4'),
            (5, 'Line 5');
        INSERT INTO skus (id, part_number, description, case_pack) VALUES
            (1, 'PN-1', 'Claret 750ml', 12);
        INSERT INTO users (id, name, role, line_id, active) VALUES
            (1, 'Randy', 'Operator', 1, 1),
            (2, 'Ana', 'Operator', 3, 1);
        INSERT INTO jobs (id, job_number, sku_id, line_id, target_quantity, status) VALUES
            (1, 'WO-1001', 1, 1, 1000, 'scheduled'),
            (2, 'WO-1002', 1, 2, 1000, 'scheduled'),
            (3, 'WO-1003', 1, 1, 1000, 'completed'),
            (4, 'WO-1004', 1, 1, 1000, 'paused'),
            (5, 'WO-1005', 1, 3, 1000, 'scheduled'),
            (6, 'WO-1006', 1, 3, 1000, 'running'),
            (7, 'WO-1007', 1, 4, 1000, 'scheduled');
        INSERT INTO line_events (id, line_id, state, started_at, job_id, source) VALUES
            (1, 3, 'production', '2026-11-21T07:00:00', 6, 'seed');
        """
    )
    c.commit()
    c.close()


def post(**form):
    """POST to /floor without following the redirect. Returns (response, msg)."""
    resp = client.post("/floor", data=form, follow_redirects=False)
    loc = resp.headers.get("Location", "")
    qs = parse_qs(urlparse(loc).query)
    return resp, (qs.get("msg") or [""])[0]


def open_events(line_id):
    c = conn()
    rows = c.execute(
        "SELECT * FROM line_events WHERE line_id=? AND ended_at IS NULL "
        "ORDER BY started_at", (line_id,)).fetchall()
    c.close()
    return [dict(r) for r in rows]


def job_row(job_number):
    c = conn()
    r = c.execute("SELECT * FROM jobs WHERE job_number=?", (job_number,)).fetchone()
    c.close()
    return dict(r) if r else None


def events_for(job_id):
    c = conn()
    n = c.execute("SELECT COUNT(*) FROM line_events WHERE job_id=?",
                  (job_id,)).fetchone()[0]
    c.close()
    return n


RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    line = ("PASS  " if ok else "FAIL  ") + name
    if not ok and detail:
        line += "\n        " + str(detail)[:300]
    print(line)


# ---------------------------------------------------------------- case 1 ----
# One good start, proving the row lands with source='floor' and a real user_id.

seed()

resp, msg = post(action="start", line_id="1", job_number="WO-1001", operator_id="1")
ev = open_events(1)
job = job_row("WO-1001")
row = ev[0] if len(ev) == 1 else {}
check(
    "start: job status and line event both land, in one commit",
    resp.status_code == 302
    and len(ev) == 1
    and row.get("state") == "production"
    and row.get("job_id") == 1
    and row.get("source") == "floor"
    and row.get("user_id") == 1
    and row.get("ended_at") is None
    and job["status"] == "running"
    and job["actual_start"]
    and job["actual_end"] is None
    and msg.startswith("Started"),
    "status=%s msg=%r events=%r job=%r" % (resp.status_code, msg, ev, job),
)

# ---------------------------------------------------------------- case 2 ----
# An induced failure inside SQLite. jobs.status must be unchanged afterwards,
# which is only true if the UPDATE and the event INSERT share a transaction.

c = conn()
c.execute(
    "CREATE TRIGGER t_floor_start_block BEFORE INSERT ON line_events "
    "BEGIN SELECT RAISE(ABORT, 'induced line_events insert failure'); END;")
c.commit()
c.close()

before = job_row("WO-1002")
resp, msg = post(action="start", line_id="2", job_number="WO-1002", operator_id="1")
after = job_row("WO-1002")
ev2 = open_events(2)
orphans = events_for(2)

c = conn()
c.execute("DROP TRIGGER IF EXISTS t_floor_start_block")
c.commit()
c.close()

check(
    "induced failure: line event insert fails, jobs.status is unchanged",
    after["status"] == before["status"]
    and after["status"] == "scheduled"
    and after["actual_start"] == before["actual_start"]
    and after["actual_end"] == before["actual_end"]
    and not ev2
    and orphans == 0
    and "induced" in msg.lower(),
    "before=%r after=%r msg=%r events=%r" % (before, after, msg, ev2),
)

# ---------------------------------------------------------------- case 3 ----
# Refusal: a completed job.

resp, msg = post(action="start", line_id="1", job_number="WO-1003", operator_id="1")
check(
    "refusal: completed job is not started",
    job_row("WO-1003")["status"] == "completed"
    and events_for(3) == 0
    and "completed" in msg.lower(),
    "msg=%r" % (msg,),
)

# ---------------------------------------------------------------- case 4 ----
# Refusal: a paused job.

resp, msg = post(action="start", line_id="1", job_number="WO-1004", operator_id="1")
check(
    "refusal: paused job is not started",
    job_row("WO-1004")["status"] == "paused"
    and events_for(4) == 0
    and "paused" in msg.lower(),
    "msg=%r" % (msg,),
)

# ---------------------------------------------------------------- case 5 ----
# Refusal: a line already running another job. Twice, because the second one
# is the moved case: WO-1007 belongs to Line 4 and is being started on Line 3,
# which is running WO-1006. Before this fix that start closed WO-1006's event
# without a word, because the check looked at the job's own line.

resp, msg = post(action="start", line_id="3", job_number="WO-1005", operator_id="2")
resp_m, msg_m = post(action="start", line_id="3", job_number="WO-1007", operator_id="2")
ev3 = open_events(3)
check(
    "refusal: busy line, including a job moved onto it",
    job_row("WO-1005")["status"] == "scheduled"
    and job_row("WO-1007")["status"] == "scheduled"
    and "changeover" in msg.lower()
    and "changeover" in msg_m.lower()
    and len(ev3) == 1
    and ev3[0]["job_id"] == 6,
    "msg=%r moved=%r events=%r" % (msg, msg_m, ev3),
)

# ---------------------------------------------------------------- case 6 ----
# The record path, which posts no action field, must behave exactly as before.

resp = client.post("/floor", data={
    "line_id": "1",
    "job_number": "WO-1001",
    "period": "H3",
    "units_filled": "0",
    "scrap_units": "0",
    "duration_min": "60",
    "operator_id": "1",
    "notes": "",
}, follow_redirects=False)

c = conn()
run = c.execute(
    "SELECT * FROM hourly_runs WHERE job_id=1 ORDER BY id DESC LIMIT 1").fetchone()
c.close()
run = dict(run) if run else {}

check(
    "record path with no action field still writes the hour, source='floor'",
    resp.status_code == 200
    and run.get("source") == "floor"
    and run.get("user_id") == 1
    and run.get("units_filled") == 0
    and run.get("period") == "H3"
    and run.get("shift") not in (None, ""),
    "status=%s row=%r" % (resp.status_code, run),
)

# ---------------------------------------------------------------- case 7 ----
# A45. The same production passes or fails depending on whether lunch is
# deducted: 918 against 1000 is -8.2 percent and the old gate refuses it,
# 918 against 950 is -3.4 percent and sits inside the default five percent.

c = conn()
c.execute(
    "INSERT INTO jobs (id, job_number, sku_id, line_id, target_quantity, status,"
    " scheduled_start, scheduled_end) VALUES (?,?,?,?,?,?,?,?)",
    (10, 'WO-2001', 1, 1, 1000, 'running',
     '2026-11-18T07:00:00', '2026-11-18T17:00:00'))
c.execute(
    "INSERT INTO line_events (line_id, state, started_at, ended_at, source)"
    " VALUES (1, 'lunch', '2026-11-18T12:00:00', '2026-11-18T12:30:00', 'floor')")
c.execute(
    "INSERT INTO hourly_runs (job_id, line_id, sku_id, shift, period, recorded_at,"
    " units_filled, scrap_units, duration_min, source)"
    " VALUES (10, 1, 1, '1', 'H5', '2026-11-18T12:00:00', 918, 0, 60, 'floor')")
c.commit()
c.close()

when = datetime(2026, 11, 18, 18, 0)
c = conn()
job = dict(c.execute("SELECT * FROM jobs WHERE id=10").fetchone())
allowance = bot_jobs.variance_allowance(c, job, now=when)
refusal = bot_jobs.variance_refusal(c, job, now=when)
c.close()

raw_variance = (918 - 1000) / 1000.0
check(
    "A45: lunch deducted, 918 of 1000 passes where the raw gate refuses",
    allowance["window"] == 600
    and allowance["off_minutes"] == 30
    and allowance["allowed"] == 950
    and allowance["variance"] is not None
    and abs(allowance["variance"]) < 0.05
    and abs(raw_variance) > 0.05
    and refusal is None,
    "allowance=%r refusal=%r" % (allowance, refusal),
)

# ---------------------------------------------------------------- case 8 ----
# A job whose weekly schedule was never loaded still gates, against the raw
# target, and the sentence says the allowance was not applied.

c = conn()
c.execute(
    "INSERT INTO jobs (id, job_number, sku_id, line_id, target_quantity, status)"
    " VALUES (11, 'WO-2002', 1, 2, 1000, 'running')")
c.execute(
    "INSERT INTO hourly_runs (job_id, line_id, sku_id, shift, period, recorded_at,"
    " units_filled, scrap_units, duration_min, source)"
    " VALUES (11, 2, 1, '1', 'H2', '2026-11-18T09:00:00', 900, 0, 60, 'floor')")
c.commit()
c.close()

c = conn()
job = dict(c.execute("SELECT * FROM jobs WHERE id=11").fetchone())
allowance = bot_jobs.variance_allowance(c, job, now=when)
refusal = bot_jobs.variance_refusal(c, job, now=when)
c.close()

check(
    "A45: no scheduled window still gates against the raw target, and says so",
    allowance["window"] is None
    and allowance["allowed"] == 1000
    and allowance["variance"] is not None
    and abs(allowance["variance"] + 0.10) < 0.0001
    and refusal is not None
    and "no scheduled window" in refusal,
    "allowance=%r refusal=%r" % (allowance, refusal),
)

# ---------------------------------------------------------------- case 9 ----
# A refused close changes nothing. The gate returns a sentence and writes no
# row, so the job is still running and nothing has been recorded against it.

before = job_row("WO-2002")
before_events = events_for(11)
before_runs = sqlite3.connect(DB).execute(
    "SELECT COUNT(*) FROM hourly_runs WHERE job_id=11").fetchone()[0]

c = conn()
job = dict(c.execute("SELECT * FROM jobs WHERE id=11").fetchone())
refusal = bot_jobs.variance_refusal(c, job, now=when)
c.close()

after = job_row("WO-2002")
after_events = events_for(11)
after_runs = sqlite3.connect(DB).execute(
    "SELECT COUNT(*) FROM hourly_runs WHERE job_id=11").fetchone()[0]

check(
    "A45: a refused close leaves the job running and writes nothing",
    refusal is not None
    and before["status"] == "running"
    and after["status"] == "running"
    and after["actual_end"] is None
    and after["completion_variance_reason"] is None
    and after_events == before_events
    and after_runs == before_runs,
    "before=%r after=%r refusal=%r" % (before, after, refusal),
)

# --------------------------------------------------------------- case 10 ----
# Capacity against quality, the owner's distinction. 1000 parts in an hour
# that owed 1000, 25 of them scrap: no capacity lost, so the gate must not
# fire, and the capacity figure must be 1000 rather than 975. If someone later
# changes the gate to sum units_filled minus scrap_units, this case fails.

c = conn()
c.execute(
    "INSERT INTO jobs (id, job_number, sku_id, line_id, target_quantity, status)"
    " VALUES (12, 'WO-3001', 1, 4, 1000, 'scheduled')")
c.execute(
    "INSERT INTO hourly_runs (job_id, line_id, sku_id, shift, period, recorded_at,"
    " units_filled, scrap_units, duration_min, source)"
    " VALUES (12, 4, 1, '1', 'H1', '2026-11-19T08:00:00', 1000, 25, 60, 'floor')")
c.commit()
run = dict(c.execute(
    "SELECT * FROM hourly_runs WHERE job_id=12").fetchone())
c.close()

c = conn()
job = dict(c.execute("SELECT * FROM jobs WHERE id=12").fetchone())
allowance = bot_jobs.variance_allowance(c, job, now=when)
refusal = bot_jobs.variance_refusal(c, job, now=when)
c.close()

check(
    "capacity at 1000 of 1000 with 25 scrap: no capacity lost, no refusal",
    run["units_filled"] == 1000
    and run["scrap_units"] == 25
    and allowance["actual"] == 1000
    and allowance["allowed"] == 1000
    and allowance["variance"] == 0.0
    and refusal is None,
    "run=%r allowance=%r refusal=%r" % (run, allowance, refusal),
)

# --------------------------------------------------------------- case 11 ----
# End refuses without a reason and leaves everything where it was.

c = conn()
c.execute(
    "INSERT INTO jobs (id, job_number, sku_id, line_id, target_quantity, status)"
    " VALUES (13, 'WO-3002', 1, 4, 1000, 'running')")
c.execute(
    "INSERT INTO hourly_runs (job_id, line_id, sku_id, shift, period, recorded_at,"
    " units_filled, scrap_units, duration_min, source)"
    " VALUES (13, 4, 1, '1', 'H1', '2026-11-20T08:00:00', 900, 0, 60, 'floor')")
c.execute(
    "INSERT INTO line_events (line_id, state, started_at, job_id, source)"
    " VALUES (4, 'production', '2026-11-20T07:00:00', 13, 'seed')")
c.commit()
c.close()

c = conn()
job = dict(c.execute("SELECT * FROM jobs WHERE id=13").fetchone())
refusal = bot_jobs.end_job(c, job, 4, user_id=2, source="floor")
c.close()

still = job_row("WO-3002")
open4 = open_events(4)
check(
    "end: refused without a reason, job still running, line still in production",
    refusal is not None
    and "off target" in refusal
    and still["status"] == "running"
    and still["actual_end"] is None
    and len(open4) == 1
    and open4[0]["state"] == "production"
    and open4[0]["job_id"] == 13,
    "refusal=%r job=%r open=%r" % (refusal, still, open4),
)

# --------------------------------------------------------------- case 12 ----
# The same end, with the reason supplied, closes and flags, and the line goes
# idle in the same transaction.

c = conn()
job = dict(c.execute("SELECT * FROM jobs WHERE id=13").fetchone())
outcome = bot_jobs.end_job(c, job, 4, user_id=2, source="floor",
                           reason="filler jammed on station four")
c.close()

done = job_row("WO-3002")
open4 = open_events(4)
check(
    "end: with a reason it closes, flags, and leaves the line idle",
    outcome is None
    and done["status"] == "completed"
    and done["actual_end"]
    and done["completion_flagged"] == 1
    and "filler jammed" in (done["completion_variance_reason"] or "")
    and len(open4) == 1
    and open4[0]["state"] == "idle"
    and open4[0]["source"] == "floor",
    "outcome=%r job=%r open=%r" % (outcome, done, open4),
)

# --------------------------------------------------------------- case 13 ----
# The switches. Throwing lunch closes the production event and opens a lunch
# event carrying the same job id; throwing it again returns the line to
# production with the job id read back off the event, not from a session.

c = conn()
c.execute(
    "INSERT INTO jobs (id, job_number, sku_id, line_id, target_quantity, status)"
    " VALUES (14, 'WO-4001', 1, 5, 1000, 'running')")
c.execute(
    "INSERT INTO line_events (line_id, state, started_at, job_id, source)"
    " VALUES (5, 'production', '2026-11-21T07:00:00', 14, 'floor')")
c.commit()
c.close()

c = conn()
said_on = bot_jobs.toggle_line_state(c, 5, "lunch", user_id=2, source="floor")
live = open_events(5)
c.close()

c = conn()
said_off = bot_jobs.toggle_line_state(c, 5, "lunch", user_id=2, source="floor")
live2 = open_events(5)
c.close()

check(
    "toggle: lunch on, lunch off, job id carried both ways",
    len(live) == 1
    and live[0]["state"] == "lunch"
    and live[0]["job_id"] == 14
    and live[0]["source"] == "floor"
    and "now in lunch" in said_on
    and len(live2) == 1
    and live2[0]["state"] == "production"
    and live2[0]["job_id"] == 14
    and "back in production" in said_off,
    "said_on=%r live=%r said_off=%r live2=%r" % (said_on, live, said_off, live2),
)

# --------------------------------------------------------------- case 14 ----
# A line with no job on it has nothing to take time from, and says which it is.

c = conn()
said = bot_jobs.toggle_line_state(c, 4, "maintenance", user_id=2, source="floor")
c.close()

check(
    "toggle: refused on a line with no job on it, naming what it found",
    "no job on it" in said,
    "said=%r" % (said,),
)

# --------------------------------------------------------------- case 15 ----
# The two features meet. The gate subtracts the event the switch writes. A real
# thirty minute lunch cannot be waited out in a test, so the event is written
# by the real toggle and then its timestamps are moved onto the job window.

c = conn()
bot_jobs.toggle_line_state(c, 5, "lunch", user_id=2, source="floor")
c.execute(
    "UPDATE line_events SET started_at='2026-11-21T12:00:00',"
    " ended_at='2026-11-21T12:30:00'"
    " WHERE line_id=5 AND state='lunch' AND ended_at IS NULL")
c.execute(
    "UPDATE jobs SET scheduled_start='2026-11-21T07:00:00',"
    " scheduled_end='2026-11-21T17:00:00' WHERE id=14")
c.commit()
job = dict(c.execute("SELECT * FROM jobs WHERE id=14").fetchone())
allowance = bot_jobs.variance_allowance(c, job, now=datetime(2026, 11, 21, 18, 0))
c.close()

check(
    "toggle feeds the gate: a thrown lunch is 30 off-time minutes, 950 allowed",
    allowance["window"] == 600
    and allowance["off_minutes"] == 30
    and allowance["allowed"] == 950,
    "allowance=%r" % (allowance,),
)

# ------------------------------------------------------------------ end -----

failed = RESULTS.count(False)
print("")
print("%d cases, %d failed" % (len(RESULTS), failed))
if failed:
    print("Database kept for inspection: " + DB)
else:
    shutil.rmtree(WORK, ignore_errors=True)
sys.exit(1 if failed else 0)
