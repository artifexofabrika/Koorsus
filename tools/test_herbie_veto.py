#!/usr/bin/env python3
"""Item 2: the tracer veto, and the trace it runs against.

The tracer used to live only in tools/test_herbie_cards.py, and it compared the
narrative against the stats dictionary alone. That reported a correct card as a
liar: 32.0 came from the payload's own marker "H3 [partial hour, 32 of 60 min]",
3.0 from the hour label H3, and 10.0 from an operator note reading "shift 1 on
day 10". None of those are in stats; all of them are in the prompt. The quotes
are the most valuable thing the cards produce, so a check that punishes them
removes the wrong thing.

The trace now runs against the whole prompt the model was shown: data, glossary,
the context block with the operator notes, the intent rules and the question.
And the tracer no longer warns into a log nobody reads: a figure that appears
nowhere in the prompt replaces the model's prose with the template.

The model is faked here. This tests the veto, not the weather.

Run: /home/jeeves/jeeves-env/bin/python tools/test_herbie_veto.py
Exit 0 when every check passes, 1 when any fails, 2 when it cannot start.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "myarr_v2"))

try:
    import herbie
except Exception as exc:                                    # noqa: BLE001
    print("CANNOT START: %s" % exc)
    sys.exit(2)

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    line = ("PASS  " if ok else "FAIL  ") + name
    if not ok and detail:
        line += "\n        " + str(detail)[:400]
    print(line)


CONTEXT = (
    'OPERATOR NOTES (verbatim, hour by hour):\n'
    '  H3 [partial hour, 32 of 60 min]: starting up the line, it took 15 minutes\n'
    '  H5: Machine stopped unexpectedly due to a power outage.\n'
    'MAINTENANCE EVENTS:\n'
    '  Filler: capper jam -> cleared (20m)\n'
    'ACTIVE PDCAs:\n'
    '  Capper stops: hypothesis is a worn guide\n'
    'Operator note from shift 1 on day 10: "Machine stopped unexpectedly due to '
    'a power outage."\n'
)

STATS = {
    "line_id": 2, "date": "2026-11-23",
    "actual_units": 11987, "scrap_units": 225, "run_minutes": 720,
    "downtime_min": 0.0, "downtime_by_station": {"Filler": 20.0},
    "standard_rate": 0, "rate_loaded": False, "rate_mixed": False,
    "target_units": 11662, "lost_capacity": None, "gross_production": 12212,
    "theoretical_capacity": None, "capacity_gap": 550,
    "losses_accounted": None, "losses_unexplained": None,
    "ftq": 98.1, "p2p": 102.8, "unrated_min": 720, "unrated_downtime_min": 0.0,
    "reconciliation": ("No rate is loaded for PN-NORATE on Line 2, so 720 of "
                       "720 recorded minutes cannot be scored. The capacity gap "
                       "of +550 parts is production against the target, not a "
                       "reconciled loss: lost capacity, losses accounted for and "
                       "losses unexplained were not computed."),
}

# ------------------------------------------------------- what is a figure

check("job numbers and ISO dates are not figures",
      herbie.numbers_in_text("WO-2611-201 on 2026-11-23 gave 42") == {42.0},
      herbie.numbers_in_text("WO-2611-201 on 2026-11-23 gave 42"))

check("P2P is not a figure, and its number still is",
      herbie.numbers_in_text("P2P was 102.8%") == {102.8},
      herbie.numbers_in_text("P2P was 102.8%"))

# ------------------------------------------------- the false positive that mattered

check("a number quoted from the partial-hour marker is not untraced",
      herbie.untraced_numbers("it ran 32 minutes this hour", CONTEXT) == set(),
      herbie.untraced_numbers("it ran 32 minutes this hour", CONTEXT))

check("a number quoted from an operator note is not untraced",
      herbie.untraced_numbers("the note from day 10 about shift 1", CONTEXT) == set(),
      herbie.untraced_numbers("the note from day 10 about shift 1", CONTEXT))

check("a figure the model was never shown is still untraced",
      herbie.untraced_numbers("the line lost 4242 units", CONTEXT) == {4242.0},
      herbie.untraced_numbers("the line lost 4242 units", CONTEXT))

check("a rounded figure counts as untraced, because rounding is deriving",
      herbie.untraced_numbers("about 951 units", "the figure was 950.9") == {951.0},
      herbie.untraced_numbers("about 951 units", "the figure was 950.9"))

# ------------------------------------------------- the prompt is the trace

prompt = herbie.build_prompt("line_day", STATS, CONTEXT, "What happened on Line 2?")
check("the prompt carries the context block verbatim, which is the point",
      "32 of 60 min" in prompt and "day 10" in prompt
      and "PN-NORATE" in prompt,
      prompt[:300])

check("the payload reaches the prompt with nulls rather than zeros",
      '"losses_accounted": null' in prompt and '"rate_loaded": false' in prompt,
      prompt[:300])


# ------------------------------------------------------------ the veto

class _Resp:
    def __init__(self, text):
        self._text = text

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": self._text}}]}


_real_post = herbie.requests.post
try:
    herbie.requests.post = lambda *a, **k: _Resp(
        "Line 2 ran 4242 units and lost nothing this hour.")
    result = herbie.narrate("line_day", STATS, CONTEXT, "What happened on Line 2?")

    check("an invented figure vetoes the narrative and falls back to the template",
          result["source"] == "vetoed", result["source"])

    check("the veto names the figure it rejected",
          result.get("vetoed_numbers") == [4242.0],
          result.get("vetoed_numbers"))

    check("the veto keeps the model's text for the next session rather than "
          "throwing it away",
          "4242" in (result.get("rejected") or ""),
          result.get("rejected"))

    narrative = result["narrative"]
    check("what the card shows instead is the template, with no invented figure",
          "4242" not in narrative and "not computed" in narrative,
          narrative)

    check("the template the veto emits survives a card with no rate",
          "\u2014" in narrative and "None" not in narrative,
          narrative)

    herbie.requests.post = lambda *a, **k: _Resp(
        "First time quality was 98.1 percent. The capacity gap of 550 parts is "
        "production against the target.")
    result = herbie.narrate("line_day", STATS, CONTEXT, "What happened on Line 2?")

    check("a narrative whose figures all appear in the prompt passes untouched",
          result["source"] == "llm"
          and "98.1" in result["narrative"],
          result.get("source"))
finally:
    herbie.requests.post = _real_post

# --------------------------------------------- one implementation, not two

with open(os.path.join(ROOT, "tools", "test_herbie_cards.py")) as fh:
    tool_source = fh.read()

check("the card sweep uses the production tracer instead of its own copy",
      "herbie.untraced_numbers" in tool_source
      and "def numbers_in_text" not in tool_source,
      "tool still defines its own tracer" if "def numbers_in_text" in tool_source
      else "tool does not call herbie.untraced_numbers")

failed = RESULTS.count(False)
print("")
print("%d checks, %d failed" % (len(RESULTS), failed))
sys.exit(1 if failed else 0)
