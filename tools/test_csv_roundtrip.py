#!/usr/bin/env python3
"""CSV round-trip test for Myarra onboarding.

Imports deliberately awkward CSVs into a throwaway database and reads every
value back out, asserting equality. MYARRA_DB is redirected to /tmp before
db is imported, so the live appliance is never touched.

Run: /home/jeeves/jeeves-env/bin/python tools/test_csv_roundtrip.py
"""
import csv
import io
import os
import sys

TMP_DB = "/tmp/myarra_roundtrip.db"
os.environ["MYARRA_DB"] = TMP_DB

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "myarr_v2"))

from db import init_db, get_db_connection
from onboarding import ingest_template, INGEST_ORDER


class Upload:
    """Mimics the werkzeug FileStorage shape ingest_template expects."""
    def __init__(self, data):
        self.stream = io.BytesIO(data)


def build(rows, encoding="utf-8"):
    buf = io.StringIO()
    w = csv.writer(buf)
    for r in rows:
        w.writerow(r)
    return Upload(buf.getvalue().encode(encoding))


RESULTS = []


def check(label, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(("PASS  " if ok else "FAIL  ") + label)
    if not ok:
        print("        want: " + repr(want))
        print("        got : " + repr(got))


DATA = {
    "settings": [
        ["key", "value", "description"],
        ["unit_label", "containers", "What a unit is called"],
        ["case_label", 'Cafe" with comma, and accent: Caf\u00e9', "three hazards"],
    ],
    "component_types": [
        ["name", "is_serial", "default_swap_min"],
        ["case", 0, 12],
        ["formulation", 1, 10],
    ],
    "lines": [
        ["id", "name", "format_type"],
        [1, "Line 1 - Caf\u00e9", "beverage"],
    ],
    "skus": [
        ["part_number", "description", "case_pack", "active"],
        ["COS-CMP-RS", "Compact Rose 0.25oz", 12, 1],
        ["cos-lower-01", "lower case part number", 6, 1],
        ["COS-QUOTE", '5" roll, sanded', 24, 1],
        ["COS-NL", "line one\nline two", 12, 1],
    ],
    "sku_bom": [
        ["sku_part_number", "component_name", "component_value"],
        ["COS-CMP-RS", "case", "rose-blk"],
        ["cos-lower-01", "case", "lower-case-value"],
    ],
    "line_sku_rates": [
        ["line_id", "sku_part_number", "ideal_rate"],
        [1, "COS-CMP-RS", 7200],
    ],
    "co_procedures": [
        ["line_id", "from_sku_part_number", "to_sku_part_number", "name",
         "aggregate_standard_min"],
        [1, "COS-CMP-RS", "COS-QUOTE", "Rose to Quote", 40],
    ],
    "co_steps": [
        ["line_id", "from_sku_part_number", "to_sku_part_number", "seq",
         "step_name", "station", "standard_min"],
        [1, "COS-CMP-RS", "COS-QUOTE", 1, "Change case", "case_feeder", 12],
        [1, "COS-CMP-RS", "COS-QUOTE", 2, "Change formulation", "filler", 10],
    ],
    "jobs": [
        ["job_number", "sku_part_number", "line_id", "target_quantity",
         "scheduled_start", "scheduled_end"],
        ["WO-2026-900", "COS-CMP-RS", 1, 120000,
         "2026-11-21T07:00:00", "2026-11-21T15:00:00"],
    ],
    "users": [
        ["name", "role", "line_id", "telegram_id", "active"],
        ["Zo\u00eb \u00c5ngstr\u00f6m", "Lead", 1, "111", 1],
    ],
}


def main():
    if os.path.exists(TMP_DB):
        os.remove(TMP_DB)
    init_db()
    conn = get_db_connection()

    for name in INGEST_ORDER:
        res = ingest_template(conn, name, build(DATA[name]))
        print("%-16s uploaded=%d succeeded=%d failed=%d"
              % (name, res["uploaded"], res["succeeded"], res["failed"]))
        for e in res["errors"]:
            print("        line %d: %s" % (e["line"], e["message"]))
    print("")

    row = conn.execute("SELECT value FROM settings WHERE key='case_label'").fetchone()
    check("settings value: quote, comma, accent", row[0],
          'Cafe" with comma, and accent: Caf\u00e9')

    row = conn.execute("SELECT name FROM lines WHERE id=1").fetchone()
    check("lines name: accent survives", row[0], "Line 1 - Caf\u00e9")

    row = conn.execute("SELECT description FROM skus WHERE part_number='COS-QUOTE'").fetchone()
    check("skus description: quote and comma", row[0], '5" roll, sanded')

    row = conn.execute("SELECT description FROM skus WHERE part_number='COS-NL'").fetchone()
    check("skus description: embedded newline", row[0], "line one\nline two")

    row = conn.execute("SELECT COUNT(*) FROM sku_bom b JOIN skus s ON s.id=b.sku_id "
                       "WHERE s.part_number='cos-lower-01'").fetchone()
    check("sku_bom resolves a lower case part number", row[0], 1)

    row = conn.execute("SELECT name FROM users WHERE telegram_id='111'").fetchone()
    check("users name: non-ASCII survives", row[0], "Zo\u00eb \u00c5ngstr\u00f6m")

    row = conn.execute("SELECT standard_min FROM co_steps_v2 WHERE seq=1").fetchone()
    check("co_steps standard_min is numeric", row[0], 12.0)

    latin = "key,value,description\nlatin1_probe,Caf\u00e9,accented\n".encode("latin-1")
    ingest_template(conn, "settings", Upload(latin))
    row = conn.execute("SELECT value FROM settings WHERE key='latin1_probe'").fetchone()
    check("latin-1 file imports the real accent", row[0] if row else None, "Caf\u00e9")

    conn.close()
    print("")
    failed = RESULTS.count(False)
    print("%d checks, %d failed" % (len(RESULTS), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
