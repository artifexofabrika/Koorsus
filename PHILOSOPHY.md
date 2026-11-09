# Myarra — Philosophy and Inviolable Commitments

This document is not a delta. It is never superseded. Every session delta
opens by pointing here. If a proposed change contradicts this document, the
change is wrong, not the document. Only the owner may revise it.

## What Myarra is for

Myarra exists to make the Toyota Production System practicable for plants
doing $3M to $15M a year, where continuous improvement stalls at Check
because Check costs data and data costs a person.

Plan and Do cost thought. Check costs data. In most plants, one person
becomes the human interface—walks the floor, chases the leads, rebuilds the
spreadsheet—and the CI function quietly becomes a data-collection function
while the improvement work waits. Myarra removes that person from the loop
by making capture freeform and retrieval intelligent.

## Commitments no future instance may quietly remove

1. **Two measures, never one.**
   OEE counts every loss: breakdowns, changeovers, scrap, idle. Operator
   performance excludes what the operator did not cause. Do not collapse
   them into a weighted number. The owner's objection to vOEE—a number
   engineered to flatter a COO—is the reason. `recon.py` carries the math
   and the comment. Do not simplify it to actual/expected.

2. **Jidoka in software.**
   Capture never blocks the operator. A vocabulary of stations may guide
   parsing, but an unrecognised description is recorded verbatim. The
   parser sets `station='unspecified'` and preserves the full text in
   `raw_text` before attempting to match. The operator's own words are the
   data of record. No dropdown may ever be required to log an event.

3. **"Unknown" and "skip" are valid answers.**
   Every prompt that asks for a reason must accept ignorance. A system that
   forces a code gets a wrong code. A system that accepts "unknown" gets
   the truth. See `notes.py` and `handle_maint_prompt`.

4. **Check must close without a data janitor.**
   Any feature that adds a person to the loop is a regression, however
   elegant the feature. If the tool requires someone to reconcile it, the
   tool has failed.

5. **PDCA is the frame; OEE is a symptom.**
   The goal is current state to future state via root cause analysis. OEE
   is one number along the way. Marketing leads with PDCA, not OEE.
   `v_pdca_trend` ties an experiment to a changeover step so the check is
   measurable, not anecdotal.

6. **Standardized work is measured, not posted.**
   A standard that is never compared to actual is a poster. Every
   changeover step carries a `standard_min`, and `v_changeover_by_station`
   returns the variance. Do not add a standard that nothing measures.

7. **The floor owns it.**
   If the operator cannot see his own data, it is a whip with better
   charts. The appliance may live in the data room, but the display must be
   reachable from the floor. Visual management is a commitment, not a
   feature.

8. **Root cause targets the process, never the person.**
   "Operator error" is not a root cause. It prompts "why did the process
   allow the error?" The taxonomy wall is a process failure, not an
   operator failure. The 101st category is our fault, not his.

9. **Six Sigma is a control method, not an improvement method.**
   The owner's position from 25 years on the floor: correlation, not
   causation, between Six Sigma implementation and improvement in
   manufacturing capability. This stays out of public marketing. It is
   present in the reasoning. Do not soften it, and do not publish it.

## The test for any proposed feature

Ask, in order:

1. Does it make Check cheaper for the operator?
2. Does it preserve the two measures without collapsing them?
3. Does it ever block the operator or force a code?
4. Does it add a person to the loop?
5. Can the floor see it?

A feature that fails any of these is not a Myarra feature, whatever else it
may be.