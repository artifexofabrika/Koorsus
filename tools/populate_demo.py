"""One-shot: wipe master data, load demo-data/*.csv through the real
onboarding ingestion path, then generate 30 days of history. The
demonstration of how easy setup is."""
import argparse
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / "Client-Demo" / "myarr_v2"))
from onboarding import ingest_template, INGEST_ORDER  # noqa: E402

DB = "/mnt/lake/myarra.db"
DEMO_DATA = Path.home() / "Client-Demo" / "demo-data"
TOOLS = Path.home() / "Client-Demo" / "tools"

WIPE = ['fishbone_causes', 'experiment_actions', 'experiments',
        'co_event_steps', 'co_event_changes', 'co_events',
        'co_steps_v2', 'co_procedures_v2',
        'line_events', 'downtime_events', 'hourly_runs',
        'jobs', 'sku_bom', 'line_sku_rates',
        'skus', 'component_types', 'lines', 'bot_sessions']


class FakeFile:
    def __init__(self, path):
        self.filename = path.name
        self.stream = open(path, 'rb')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-wipe", action="store_true")
    args = ap.parse_args()

    missing = [n for n in INGEST_ORDER if not (DEMO_DATA / f"{n}.csv").exists()]
    if missing:
        print(f"FATAL: missing demo-data files: {missing}")
        return 1

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if not args.no_wipe:
        for t in WIPE:
            c.execute(f"DELETE FROM {t}")
        conn.commit()
        print("wiped master data and history (users, settings preserved)")

    print("\ningesting demo-data CSVs via the real onboarding path:")
    total_ok = 0
    total_fail = 0
    for name in INGEST_ORDER:
        ff = FakeFile(DEMO_DATA / f"{name}.csv")
        r = ingest_template(conn, name, ff)
        ff.stream.close()
        total_ok += r['succeeded']
        total_fail += r['failed']
        print(f"  {name:16s} uploaded={r['uploaded']:3d} "
              f"succeeded={r['succeeded']:3d} failed={r['failed']:3d}")
        for e in r["errors"][:3]:
            print(f"    line {e['line']}: {e['message']}")
    conn.close()
    print(f"\ningest complete: {total_ok} rows loaded, {total_fail} failed")

    print("\nrunning history generator...")
    subprocess.run(
        [sys.executable, str(TOOLS / "generate_demo_history.py"), "--force"],
        check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
