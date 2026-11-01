"""Tests LLM intent extraction on realistic operator messages."""
from intent import extract

CASES = [
    "running job WO-2610-008, hour 5, 35022 bottles, 2 minutes down jam at the filler",
    "w0-2610-016 hour five 34 thousand bottles",
    "just started hour 6 on 008, 34000 bottles, no downtime",
    "logging 008 hour 6, thirty-four thousand bottles",
    "running job 2610-008 hour 5 35022",
    "ending job WO-2610-008",
    "changeover job WO-2610-008 to WO-2610-016",
    "start job WO-2610-016",
    "status job WO-2610-008",
    "status job w0-2610-008",
    "status line 1",
    "status line one",
    "handover job WO-2610-008",
    "taking over job WO-2610-008",
    "sop, labeler E44 error code",
    "labeler is throwing an E44, what does the SOP say",
    "cancel",
    "what is the weather",
]

for i, text in enumerate(CASES, 1):
    p = extract(text)
    line = (f"[{i:2d}] {text[:70]}\n"
            f"     intent={p.get('intent')}  job={p.get('job_number')}  hour={p.get('hour')}  "
            f"bottles={p.get('bottles')}  line={p.get('line')}  q={p.get('question')}")
    if p.get("error"):
        line += f"\n     ERROR: {p['error']}"
    print(line + "\n")
