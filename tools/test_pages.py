#!/usr/bin/env python3
"""Page sweep for the Myarra web app. GET only, nothing is written.

Reads real ids from the live database, so the dynamic routes are exercised
with data that exists rather than with guesses.

Run: /home/jeeves/jeeves-env/bin/python tools/test_pages.py
"""
import sqlite3
import sys

import requests
import urllib3

urllib3.disable_warnings()

BASE = "https://127.0.0.1:5002"
DB = "/mnt/lake/myarra.db"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row


def one(sql, default=None):
    try:
        r = conn.execute(sql).fetchone()
        return r[0] if r and r[0] is not None else default
    except sqlite3.Error:
        return default


line_id = one("SELECT id FROM lines ORDER BY id LIMIT 1", 1)
co_id = one("SELECT id FROM co_events ORDER BY id DESC LIMIT 1")
mx_id = one("SELECT id FROM maintenance_events ORDER BY id DESC LIMIT 1")
exp_id = one("SELECT id FROM experiments ORDER BY id LIMIT 1")
job = one("SELECT job_number FROM jobs ORDER BY id DESC LIMIT 1")
run_date = one("SELECT date(MAX(recorded_at)) FROM hourly_runs")
shift = one("SELECT shift FROM hourly_runs WHERE shift IS NOT NULL LIMIT 1", "1")

URLS = [
    "/",
    "/reconciliation",
    "/reconciliation?line=%d&days=7" % line_id,
    "/changeover",
    "/changeover?line=%d&days=90" % line_id,
    "/pdca",
    "/pdca/log",
    "/maintenance",
    "/maintenance?line=%d&days=90" % line_id,
    "/setup",
    "/setup/verify",
    "/setup/download/lines",
    "/setup/download/skus",
    "/setup/download/jobss",
    "/herbie",
    "/floor",
    "/board/%d" % line_id,
    "/line/%d/report" % line_id,
    "/ask",
    "/admin",
    "/favicon.ico",
]

if co_id is not None:
    URLS.append("/changeover/%d" % co_id)
if mx_id is not None:
    URLS.append("/maintenance/%d" % mx_id)
if exp_id is not None:
    URLS.append("/pdca/%d" % exp_id)
    URLS.append("/pdca/%d/edit" % exp_id)
if job:
    URLS.append("/job/%s" % job)
if run_date and shift:
    URLS.append("/shift/%s/%s" % (run_date, shift))

# A deliberately misspelled template name must 404 rather than raise.
EXPECT = {"/setup/download/jobss": 404}

results = []
for path in URLS:
    try:
        r = requests.get(BASE + path, verify=False, timeout=30)
        code = r.status_code
    except Exception as e:
        code = "ERR " + str(e)[:60]
    want = EXPECT.get(path, 200)
    ok = code == want
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + "%-34s %s wanted %s" % (path, code, want))

conn.close()
print("")
failed = results.count(False)
print("%d routes, %d failed" % (len(results), failed))
sys.exit(1 if failed else 0)
