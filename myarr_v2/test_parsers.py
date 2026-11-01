"""Test suite for Myarra parsers. No DB, no bot, no network."""
from parsers import (parse_job_number, parse_hour, parse_line_number,
                     parse_bottles, parse_downtime, parse_int, parse_float)

CASES = []
def t(name, fn, inp, expected):
    CASES.append((name, fn, inp, expected))

# --- Job number ---
t("job canonical", parse_job_number, "WO-2610-029", "WO-2610-029")
t("job lowercase", parse_job_number, "wo-2610-029", "WO-2610-029")
t("job spaced",    parse_job_number, "WO 2610 029", "WO-2610-029")
t("job mangled 20-dash", parse_job_number, "20-2610-029", "WO-2610-029")
t("job mangled 20-space", parse_job_number, "20 2610 029", "WO-2610-029")
t("job absent",    parse_job_number, "no job here", None)

# --- Hour ---
t("hour basic", parse_hour, "running job WO-2610-029, hour 5, 35022 bottles", 5)
t("hour absent", parse_hour, "no hour here", None)

# --- Line ---
t("line digit", parse_line_number, "status line 1", 1)
t("line word",  parse_line_number, "status line one", 1)
t("line five",  parse_line_number, "status line five", 5)
t("line absent", parse_line_number, "status job WO-2610-029", None)

# --- Bottles (the critical regressions) ---
t("bottles plain",         parse_bottles, "35022 bottles", 35022)
t("bottles comma",         parse_bottles, "35,022 bottles", 35022)
t("bottles space",         parse_bottles, "35 022 bottles", 35022)
t("bottles with job+hour", parse_bottles,
  "running job WO-2610-029, hour 5, 35022 bottles, 2 minutes down jam at the filler", 35022)
t("bottles mangled job",   parse_bottles,
  "running job 20-2610-029, hour 6, 34000 bottles", 34000)
t("bottles absent",        parse_bottles, "no bottles keyword", None)

# --- Downtime ---
t("downtime with station",
  parse_downtime, "2 minutes down jam at the filler",
  [{'minutes': 2.0, 'station': 'Filler', 'reason': 'jam'}])
t("downtime station only",
  parse_downtime, "3 min down labeler",
  [{'minutes': 3.0, 'station': 'Labeler', 'reason': 'unspecified'}])
t("downtime full message",
  parse_downtime,
  "running job WO-2610-029, hour 5, 35022 bottles, 2 minutes down jam at the filler",
  [{'minutes': 2.0, 'station': 'Filler', 'reason': 'jam'}])
t("downtime absent", parse_downtime, "no downtime here", [])

# --- Numeric helpers ---
t("int basic",   parse_int, "30", 30)
t("float basic", parse_float, "35.5", 35.5)
t("float comma", parse_float, "35,5", 35.5)

def main():
    passed = failed = 0
    for name, fn, inp, expected in CASES:
        try:
            got = fn(inp)
            if got == expected:
                passed += 1
                print(f"PASS  {name}")
            else:
                failed += 1
                print(f"FAIL  {name}")
                print(f"      input:    {inp!r}")
                print(f"      expected: {expected!r}")
                print(f"      got:      {got!r}")
        except Exception as e:
            failed += 1
            print(f"ERROR {name}: {e}")
    print(f"\n{passed} passed, {failed} failed, out of {len(CASES)}")
    return 0 if failed == 0 else 1

if __name__ == '__main__':
    import sys
    sys.exit(main())
