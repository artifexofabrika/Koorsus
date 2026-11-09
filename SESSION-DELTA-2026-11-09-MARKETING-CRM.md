# MYARRA — SESSION DELTA, 2026-11-09 (Marketing & CRM)

This delta supersedes SESSION-DELTA-2026-11-08-ODOO20.md. Read alongside SESSION-DELTA-2026-11-07-REWRITE.md.
Read this for the Odoo App Store publication, Apify lead scraping, and CRM setup.

**Current entry point.** Read this first. Supersedes all earlier deltas.

**Before anything else, read PHILOSOPHY.md.** It is the governing document, never superseded. If a proposed change contradicts it, the change is wrong, not the document.

**Prior context — required reading before representing the product.**
- `SESSION-DELTA-2026-11-07-REWRITE.md` — modular bot architecture.
- `SESSION-DELTA-2026-11-08-ODOO20.md` — the connector, verified end to end.

## 0. WHAT THE PRODUCT IS

Myarra is a private, on-premise production tracker running on an NVIDIA Jetson
at 192.168.100.2. It is a working appliance, not a concept.

**Web application (port 5002):** Dashboard with live line status and hourly
mini-tables; `/reconciliation` with two-measure OEE (Total OEE and Operator
Performance side by side); `/line/<id>/report` shift reports with Takt time,
accumulated actuals, residuals, P2P and FTQ; `/pdca` with the Lean Planning
Board and A3 forms; `/maintenance` with the plant lifecycle memory; `/ask`, a
text-to-SQL engine that answers plain-English questions against eleven views.

**Telegram bot (`myarr_v2/bot/`, ten modules):** production with scrap capture,
changeover with per-station step walkthrough, maintenance with operator-stated
duration, shift reconciliation, variance gate on job close, relog with audit
trail, handover and takeover. All paths verified on live Telegram.

**Marketing site:** `docs/index.html` and `docs/myarra.html`, live at
artifexofabrika.com.

**Pricing:** `outreach/pricing_tiers.md` — five tiers, $1,200 to $5,500.

## 1. WHAT WAS DONE
- Published the Myarra Connector on the Odoo Apps Store (v20.0.1.0.2, 99 EUR, OPL-1).
- Created a dedicated GitHub repository for the connector: artifexofabrika/myarra-connector (branch 20.0).
- Restored the Luxo logo as a 180x180 square icon.
- Replaced the primary screenshot with a cropped 750x400 Odoo Sync view.
- Rewrote `index.html` to remove external links, for Odoo vendor guideline compliance.
- Set up Odoo CRM with a custom Pipeline (New, Contacted, Proposition, Won).
- Utilized Apify (Compass Google Maps Scraper) to scrape Columbus-area manufacturers.
- Vetted and imported 146 leads into Odoo CRM, tagged by Tier 1 and Tier 2.
- Contacted three partners: eBusiness Solutions, Adatasol, Metrotechs.
- Ran a Contact Details Scraper against 111 websites; yielded two new emails.
- Wrote and committed four outreach documents that had previously existed only in chat.

## 2. WHAT CHANGED
- `~/myarra-connector-repo/` is the source of truth for the Odoo connector.
- Odoo manifest currency changed to EUR.
- Odoo CRM tags created for Tier 1 (Packaging, Cosmetics, Food, Bottling, Partners, Manufacturing, Mobile Canning) and Tier 2 (Beverage, Distillery, Winery).
- New files in `outreach/`: `myarr-one-pager.md`, `reddit_outreach.md`, `puzzle_box_concept.md`, `hardware_sourcing.md`.

## 3. WHAT IS VERIFIED
- Odoo Apps Store listing is Active and live at https://apps.odoo.com/apps/modules/20.0/myarra_connector/.
- `index.html` is compliant with Odoo vendor guidelines; no external links remain.
- Luxo icon renders correctly at 180x180.
- CRM holds approximately 146 vetted leads.
- All three partner emails sent; Adatasol corrected to sales@adatasol.com after bounce.
- Apify scraping works efficiently (cost ~$3.73 for two Google Maps runs).

## 4. WHAT IS NOT VERIFIED
- 57 CRM records still lack email addresses. The Contact Details Scraper yielded only two.
- 12 unclassified records remain in the CRM None tag group (reviewed partially).
- The one-pager predates final pricing tiers and may reference a flat $5,500 figure. Needs review.
- No mass-mailing infrastructure. Odoo sends from `notifications@artifexofabrika.odoo.com`, with Reply-To reaching contact@artifexofabrika.com. Daily limit is 20 emails on the free plan.
- Kingswood Company and Alene'"'"'s Candles are in the CRM but without verified decision-maker contacts.

## 5. NEXT INSTANCE MUST DO
1. Review the one-pager against `outreach/pricing_tiers.md` and correct any stale pricing.
2. Contact the top 10 Tier 1 targets directly, by phone or website form. Do not bulk-email.
3. Assemble and ship the New Albany jigsaw mailer using addresses from `~/Desktop/odoo_leads_vetted.csv` (Odoo does not expose address fields in the form view).
4. Begin Reddit participation per `outreach/reddit_outreach.md`.
5. If mass mailing is needed, configure a free Mailjet SMTP account in Odoo's Email Marketing settings.

## 6. LESSONS / WORKING METHOD ADDITIONS
- Odoo CRM bulk tag editing is finicky; updating tags in bulk from the list view is more reliable than custom "does not contain" filters.
- Odoo's CRM form view does not display address fields. Use the CSV export from Apify, not Odoo, for mailing lists.
- Apify Google Maps Scraper is highly cost-effective for regional B2B lead generation.
- The Contact Details Scraper with `maxDepth=1` yields poor results. Use `maxDepth=2` or rely on manual contact finding.
- **If it was only discussed in chat, it is not in the repository. Verify file existence with `ls` or `git log --all -- <path>` before citing a path in a handover. Chat memory is not a source of truth.**
- Always verify git branch default settings on GitHub; Odoo requires the default branch to match the series (e.g., 20.0).
- Long pastes into the Jetson terminal can silently truncate. Write files via PowerShell to Desktop and `scp`, or use `python3 -c` with short content.

END OF DELTA.