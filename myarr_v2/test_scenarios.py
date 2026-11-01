"""Automated end-to-end scenarios for bot_v2. No typing required."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("MYARRA_DB", "/mnt/lake/demo_beverage.db")

from bot_v2 import get_conn, ensure_schema, Session, dispatch, get_user

# Read from command line or default
DEMO_FROM = sys.argv[1] if len(sys.argv) > 1 else "WO-2610-001"
DEMO_TO   = sys.argv[2] if len(sys.argv) > 2 else "WO-2610-002"

conn = get_conn(); ensure_schema(conn)
conn.execute("DELETE FROM bot_sessions WHERE chat_id='test'")
conn.commit()
user = get_user(conn, 1)

SCENARIOS = [
    ("running job {FROM}, hour 5, 35022 bottles, 2 minutes down jam at the filler",
     lambda r: "35,022" in r and "H5" in r),
    ("running job 20-2610-001, hour 6, 34000 bottles",
     lambda r: "34,000" in r and "H6" in r),
    ("ending job {FROM}",              lambda r: "How many minutes" in r),
    ("30",                            lambda r: "How many bottles" in r),
    ("18000",                         lambda r: "18,000" in r and "30 min" in r),
    ("changeover job {FROM} to {TO}", lambda r: "Changeover started" in r or "No procedure" in r),
    ("end changeover",                lambda r: "Total minutes" in r),
    ("35",                            lambda r: "Minutes for" in r),
    ("10",                            lambda r: "Minutes for" in r),
    ("15",                            lambda r: "Minutes for" in r),
    ("5",                             lambda r: "Minutes for" in r),
    ("5",                             lambda r: "Minutes for" in r),
    ("0",                             lambda r: "Changeover saved" in r),
    ("status line 1",                 lambda r: "Line 1" in r),
    ("status line 5",                 lambda r: "not configured" in r),
    ("status job {FROM}",             lambda r: "bottles" in r and "%" in r),
    ("running job {FROM}, hour 7, 3022 bottles",
     lambda r: "far below" in r or "confirm" in r),
    ("confirm running job {FROM}, hour 7, 3022 bottles",
     lambda r: "Logged" in r and "3,022" in r),
]

passed = failed = 0
for i, (tpl, check) in enumerate(SCENARIOS, 1):
    text = tpl.replace("{FROM}", DEMO_FROM).replace("{TO}", DEMO_TO)
    s = Session(conn, "test")
    try:
        reply = dispatch(conn, s, text, user)
        ok = check(reply)
        print(f"{'PASS' if ok else 'FAIL'}  {i:2d}. {text[:60]}")
        if not ok:
            print(f"         reply: {reply[:120]}")
            failed += 1
        else:
            passed += 1
    except Exception as e:
        print(f"ERROR {i:2d}. {text[:60]}  -> {e}")
        failed += 1

conn.execute("DELETE FROM bot_sessions WHERE chat_id='test'")
conn.commit()
print(f"\n{passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
