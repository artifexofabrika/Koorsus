"""End-to-end scenarios through bot_v3 against myarra.db. Cleans up after itself."""
import os, sys, sqlite3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("MYARRA_DB", "/mnt/lake/myarra.db")
from bot_v2 import get_conn, ensure_schema, Session, get_user
from bot_v3 import dispatch

conn = get_conn(); ensure_schema(conn)
conn.execute("DELETE FROM bot_sessions WHERE chat_id='test'"); conn.commit()
user = get_user(conn, 1)

def cleanup():
    c = conn.cursor()
    ids = [r[0] for r in c.execute("SELECT id FROM hourly_runs WHERE source='telegram'").fetchall()]
    if ids:
        ph = ','.join('?'*len(ids))
        c.execute(f"DELETE FROM downtime_events WHERE run_id IN ({ph})", ids)
        c.execute(f"DELETE FROM hourly_runs WHERE id IN ({ph})", ids)
    co_ids = [r[0] for r in c.execute("SELECT id FROM co_events WHERE source='telegram'").fetchall()]
    if co_ids:
        ph = ','.join('?'*len(co_ids))
        c.execute(f"DELETE FROM co_event_steps WHERE event_id IN ({ph})", co_ids)
        c.execute(f"DELETE FROM co_events WHERE id IN ({ph})", co_ids)
    c.execute("DELETE FROM bot_sessions")
    c.execute("UPDATE jobs SET status='running', actual_end=NULL WHERE id IN (1,3)")
    c.execute("UPDATE jobs SET status='scheduled', actual_end=NULL WHERE id IN (2,4)")
    conn.commit()

cleanup()  # start from known state

SCENARIOS = [
    ("status line 1",       lambda r: "Line 1" in r and "Running" in r),
    ("status line 2",       lambda r: "Line 2" in r and "Running" in r),
    ("status line 9",       lambda r: "not configured" in r),
    ("status WO-2026-001",  lambda r: "RUNNING" in r.upper() and "cases" in r),
    ("running job WO-2026-001, hour 5, 7000 bottles, 4 minutes down jam at filler",
     lambda r: "7000" in r.replace(",", "") and "H5" in r),
    ("running job WO-2026-001, hour 6, 6900 bottles",
     lambda r: "6900" in r.replace(",", "") and "H6" in r),
    ("end WO-2026-001 changeover to WO-2026-002",
     lambda r: "Minutes into" in r or "minutes into" in r.lower()),
    ("30",                    lambda r: "units" in r.lower()),
    ("3500",                  lambda r: "Changeover started" in r),
    ("end changeover",        lambda r: "Total minutes" in r),
    ("40",                    lambda r: "Minutes for" in r),
    ("14",                    lambda r: "Minutes for" in r),
    ("10",                    lambda r: "Minutes for" in r),
    ("10",                    lambda r: "Minutes for" in r or "Changeover saved" in r),
    ("6",                     lambda r: "Changeover saved" in r),
    ("status WO-2026-002",    lambda r: "SCHEDULED" in r.upper() or "scheduled" in r.lower()),
]

passed = failed = 0
for i, (text, check) in enumerate(SCENARIOS, 1):
    s = Session(conn, "test")
    try:
        reply = dispatch(conn, s, text, user)
        ok = check(reply)
        print(f"{'PASS' if ok else 'FAIL'}  {i:2d}. {text[:58]}")
        if not ok:
            print(f"         reply: {reply[:140]}")
            failed += 1
        else:
            passed += 1
    except Exception as e:
        print(f"ERROR {i:2d}. {text[:58]}  -> {e}")
        failed += 1

cleanup()  # end from known state
print(f"\n{passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
