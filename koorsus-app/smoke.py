#!/usr/bin/env python3
"""Smoke tests for the Arkiv appliance. Run: python3 smoke.py"""
import sys, warnings
import requests
import config
import users

warnings.filterwarnings("ignore")
BASE = "https://127.0.0.1:5001"
results = []

def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))

s = requests.Session()
s.verify = False

try:
    users.create_user("smoke", "smoke-test-pin", "admin")
except Exception:
    pass
r = s.post(BASE + "/login", data={"username": "smoke", "pin": "smoke-test-pin"}, allow_redirects=False)
check("correct PIN accepted", r.status_code in (301, 302, 303), "status=" + str(r.status_code))

r = s.get(BASE + "/")
check("index page loads", r.status_code == 200 and "Ask your firm" in r.text, "status=" + str(r.status_code))

r = s.get(BASE + "/matters")
d = r.json() if r.ok else {}
check("matters endpoint", r.status_code == 200 and len(d.get("matters", [])) > 0,
      "count=" + str(len(d.get("matters", []))))

r = s.get(BASE + "/documents")
d2 = r.json() if r.ok else {}
check("documents endpoint", r.status_code == 200 and d2.get("total_chunks", 0) > 0,
      "chunks=" + str(d2.get("total_chunks")))

r = s.post(BASE + "/ask", json={"question": "Who is Sarah Jenkins?"})
d3 = r.json() if r.ok else {}
check("answers with citation", r.status_code == 200 and bool(d3.get("sources")),
      "sources=" + str(len(d3.get("sources") or [])))

r = s.post(BASE + "/ask", json={"question": "What did the court order on the motion for temporary orders?", "matter": "Marriage of Jenkins"})
d4 = r.json() if r.ok else {}
check("outcome gate refuses", r.status_code == 200 and not d4.get("sources"),
      "sources=" + str(len(d4.get("sources") or [])))

r = s.post(BASE + "/ask", json={"question": "What did the court order on the motion for summary judgment?", "matter": "Henderson v Copper Kettle"})
d6 = r.json() if r.ok else {}
check("outcome question answers from an order", r.status_code == 200 and "order_matter_05_granting_summary_judgment.txt" in (d6.get("sources") or []), "sources=" + str(d6.get("sources")))

r = s.post(BASE + "/ask", json={"question": "judgement amount",
                                   "matter": "Henderson v Copper Kettle"})
d7 = r.json() if r.ok else {}
check("refusal without citations", r.status_code == 200 and
      not (d7.get("sources") or []), "sources=" + str(d7.get("sources")))

r = s.post(BASE + "/ask", json={"question": "how many marriage cases are there"})
d5 = r.json() if r.ok else {}
check("aggregate gate refuses", r.status_code == 200 and not d5.get("sources"),
      "sources=" + str(len(d5.get("sources") or [])))

r = s.get(BASE + "/ingest")
check("ingest page loads", r.status_code == 200 and "Add documents" in r.text, "status=" + str(r.status_code))

r = s.get(BASE + "/admin")
check("admin page loads", r.status_code == 200 and "Administrator controls" in r.text, "status=" + str(r.status_code))

r = s.get(BASE + "/users")
check("users page loads", r.status_code == 200 and
      "Change my PIN" in r.text, "status=" + str(r.status_code))

r = s.get(BASE + "/users/export.csv")
check("query log exports", r.status_code == 200 and
      "text/csv" in r.headers.get("content-type", ""),
      r.headers.get("content-type", ""))

r = s.post(BASE + "/ask", data="not json", headers={"Content-Type": "application/json"})
check("malformed body returns JSON",
      r.headers.get("content-type", "").startswith("application/json"),
      r.headers.get("content-type", ""))

fails = 0
for name, ok, detail in results:
    print(("PASS  " if ok else "FAIL  ") + name + ("  [" + detail + "]" if detail else ""))
    if not ok:
        fails += 1
print("\n" + str(len(results) - fails) + "/" + str(len(results)) + " passed")
sys.exit(1 if fails else 0)
