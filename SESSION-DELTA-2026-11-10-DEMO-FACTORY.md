# MYARRA — SESSION DELTA, 2026-11-10 (Demo Factory & UI Finalization)

This delta supersedes SESSION-DELTA-2026-11-09-MARKETING-CRM.md.
Read alongside PHILOSOPHY.md and SESSION-DELTA-2026-11-07-REWRITE.md.

**Current entry point.** Read this first. Supersedes all earlier deltas.

**Before anything else, read PHILOSOPHY.md.** It is the governing document, never superseded. If a proposed change contradicts it, the change is wrong, not the document.

## 0. WHAT THE PRODUCT IS
Myarra is a private, on-premise production tracker running on an NVIDIA Jetson. It is a working appliance, not a concept. The core philosophy is TPS (Toyota Production System) and closing the "Check" step of the PDCA cycle without requiring a data janitor. It measures line-level takt time, FTQ (First Time Quality), and exposes "Floor Truth" math (gross output + downtime capacity). It is not an MRP or ERP. It tracks labor and time, assuming the ERP handles materials and BOMs.

## 1. WHAT WAS DONE
- **Schema Extension:** Added `line_sku_stations` table to map the sequence of stations for every SKU on every line. This restores the station-level context lost in prior iterations.
- **Demo Factory:** Built a comprehensive 7-line seed script (`tools/seed_demo_master.py`). Lines include Silkscreen, Filler 1 (Legacy), Filler 2 (New), Assembly, Winery, Beer, Cosmetics.
- **Data Volume:** Generated 406 jobs spanning 14 days of history, today, and 14 days of future scheduling.
- **UI Finalization:** Unified the visual language across the Live Board, Shift Report, and Job Detail. All three now use the high-contrast, white-background, thick-grid CSS.
- **PDCA Population:** Populated `experiments` with 3 active PDCAs. Added fishbone causes (19 total), action plans, priority scores, and baseline/current targets.
- **Pricing Update:** Clarified the $3,500 Turnkey tier on the website and one-pager. It now explicitly caps support at "up to 4 hours of live training and 30 days of email support for installation issues."

## 2. WHAT CHANGED (Files & Schema)
- `line_sku_stations` table created.
- `myarr_v2/app.py`: `job_detail` and `line_report` routes rewritten to generate the full 8-hour grid. `pdca_view` rewritten to handle aggregate (parent) and step-level (child) PDCAs.
- `myarr_v2/templates/line_report.html`, `job_detail.html`, `board.html`, `pdca.html`: All updated with the unified high-contrast CSS.
- `tools/seed_demo_master.py`: Completely rewritten from scratch to generate the 7-line factory.
- `tools/populate_pdca_fields.py` and `tools/populate_fishbones.py`: New utility scripts to populate PDCA metadata.

## 3. WHAT IS VERIFIED
- The 7-line seed script runs without integrity errors.
- Live Board, Shift Report, and Job Detail look identical in structure (white background, thick borders, left-aligned comments).
- Job Detail correctly calculates and displays Total Scrap, Total Gap, P2P, and FTQ.
- The PDCA board renders without overlapping. The Parent PDCA ("Reduce Filler 2 Changeover") correctly calculates the aggregate drop (60m down to 32m).
- Fishbone causes render correctly on the A3 pages.
- Website and one-pager pricing text are consistent and legally protective.

## 4. WHAT IS NOT VERIFIED
- The Telegram bot changeover walkthrough has not been tested against the new `line_sku_stations` data.
- The AI Lean Counselor (Herbie) has not been built. The "Floor Truth" calculation is currently a manual exercise demonstrated in conversation, not a software feature.
- The Live Board still falls back to the most recent date if today has no data. (Parking Lot item: must default to blank for production safety).
- Reddit post is drafted but not published.
- Colin (Odoo Partner) replied; we have not yet sent the follow-up to schedule the Thursday call.

## 5. NEXT INSTANCE MUST DO
1. Send the reply to Colin to schedule the Thursday 20-minute call regarding the Odoo Partner Program ($3,950 fee, 1 lead/month).
2. Post the drafted Reddit question in `r/LeanManufacturing`.
3. Begin work on the AI Lean Counselor (Herbie). This will require loading a local LLM and testing latency on the Jetson Nano.
4. Call Sensience and Mettler Toledo (both hiring CI Managers) to offer the 2-week free trial.
5. Fix the Live Board safety issue (default to blank if no data today).

## 6. LESSONS / WORKING METHOD ADDITIONS
- **CSS is Global:** When trying to make a page look like another page, read `static/style.css` first. Do not write inline table styles that fight the global rules.
- **Job Number Format:** The format is `WO-YYMM-XXX`, no dots. (e.g., `WO-2611-001`).
- **Schema Drift:** We lost the station sequence in prior iterations. The `line_sku_stations` table restores it. Do not delete it.

END OF DELTA.