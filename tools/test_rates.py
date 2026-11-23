#!/usr/bin/env python3
"""A01: what the reporting pages do when a SKU has no rate on its line.

The reference appliance has a rate for every open job, so the missing-rate path
is never exercised there and a green page sweep proves nothing about it. This
builds a database that deliberately lacks one, renders the four pages that
carry rate-derived figures, and asserts that each says so instead of inventing
600.0.

FTQ is asserted as a real number on the same pages, because FTQ does not need a
rate: it is good units over produced units. A page that dashes FTQ as well
would be hiding a measure that is still known.

Run: /home/jeeves/jeeves-env/bin/python tools/test_rates.py
Exit 0 when all four pages behave, 1 when any does not, 2 when it cannot start.
"""
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "myarr_v2"))

WORK = tempfile.mkdtemp(prefix="myarra_rates_")
DB = os.path.join(WORK, "rates.db")
os.environ["MYARRA_DB"] = DB

import myarra_settings

myarra_settings.check_llm = lambda *a, **k: (True, "stubbed by test_rates")

import db as myarra_db

myarra_db.init_db()

try:
    import app as webapp
except Exception as exc:                                    # noqa: BLE001
    print("CANNOT START: importing app failed: %s" % exc)
    shutil.rmtree(WORK, ignore_errors=True)
    sys.exit(2)

client = webapp.app.test_client()

NOW = datetime.now()
RUN_AT = NOW.replace(minute=0, second=0, microsecond=0).isoformat()
RUN_DATE = RUN_AT[:10]
DASH = "\u2014"


def seed():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        INSERT INTO lines (id, name) VALUES (1, 'Line 1');
        INSERT INTO skus (id, part_number, description, case_pack)
            VALUES (1, 'PN-NORATE', 'Wallet, no rate on line 1', 1);
        INSERT INTO jobs (id, job_number, sku_id, line_id, target_quantity, status)
            VALUES (1, 'WO-9001', 1, 1, 1000, 'completed');
        """
    )
    c.execute(
        "INSERT INTO hourly_runs (job_id, line_id, sku_id, shift, period,"
        " recorded_at, units_filled, scrap_units, duration_min, source)"
        " VALUES (1, 1, 1, '1', 'H1', ?, 900, 25, 60, 'floor')", (RUN_AT,))
    c.commit()
    # Deliberately no line_sku_rates row for (line 1, sku 1). That absence is
    # the entire subject of this test.
    have = c.execute("SELECT COUNT(*) FROM line_sku_rates").fetchone()[0]
    c.close()
    return have


RATE_ROWS = seed()

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    line = ("PASS  " if ok else "FAIL  ") + name
    if not ok and detail:
        line += "\n        " + str(detail)[:400]
    print(line)


def page(path):
    r = client.get(path)
    return r.status_code, r.get_data(as_text=True)


def looks_like_a_rate_problem(body):
    return ("no rate loaded" in body) and (DASH in body) and ("97.2" in body)


check(
    "fixture: no rate row exists for the SKU on line 1",
    RATE_ROWS == 0,
    "line_sku_rates holds %r rows" % (RATE_ROWS,),
)

code, body = page("/board/1")
check("/board/1 shows no rate, dashes the targets, keeps FTQ",
      code == 200 and looks_like_a_rate_problem(body),
      "status=%s rate_text=%s dash=%s ftq=%s 600=%s"
      % (code, "no rate loaded" in body, DASH in body, "97.2" in body, "600" in body))

code, body = page("/line/1/report")
check("/line/1/report shows no rate, dashes the targets, keeps FTQ",
      code == 200 and looks_like_a_rate_problem(body),
      "status=%s rate_text=%s dash=%s ftq=%s 600=%s"
      % (code, "no rate loaded" in body, DASH in body, "97.2" in body, "600" in body))

code, body = page("/job/WO-9001")
check("/job/WO-9001 shows no rate, dashes the targets, keeps FTQ",
      code == 200 and looks_like_a_rate_problem(body),
      "status=%s rate_text=%s dash=%s ftq=%s 600=%s"
      % (code, "no rate loaded" in body, DASH in body, "97.2" in body, "600" in body))

code, body = page("/shift/%s/1" % RUN_DATE)
check("/shift/<date>/1 dashes the expected figure and the gap",
      code == 200 and DASH in body and "no rate" not in body,
      "status=%s dash=%s 600=%s" % (code, DASH in body, "600" in body))

failed = RESULTS.count(False)
print("")
print("%d checks, %d failed" % (len(RESULTS), failed))
if failed:
    print("Database kept for inspection: " + DB)
else:
    shutil.rmtree(WORK, ignore_errors=True)
sys.exit(1 if failed else 0)
