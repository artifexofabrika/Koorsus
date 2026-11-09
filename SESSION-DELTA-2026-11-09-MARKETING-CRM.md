# MYARRA — SESSION DELTA, 2026-11-09 (Marketing & CRM)

This delta supersedes SESSION-DELTA-2026-11-08-ODOO20.md. Read alongside SESSION-DELTA-2026-11-07-REWRITE.md.
Read this for the Odoo App Store publication, Apify lead scraping, and CRM setup.

**Current entry point.** Read this first. Supersedes all earlier deltas.

## 1. WHAT WAS DONE
- Published the Myarra Connector on the Odoo Apps Store (v20.0.1.0.2, 99 EUR, OPL-1).
- Created a dedicated GitHub repository for the connector: artifexofabrika/myarra-connector (branch 20.0).
- Restored the Luxo logo as a 180x180 square icon.
- Replaced the primary screenshot with a cropped 750x400 Odoo Sync view.
- Set up Odoo CRM with a custom Pipeline (New, Contacted, Proposition, Won).
- Utilized Apify (Compass Google Maps Scraper) to scrape Columbus-area manufacturers.
- Vetted and imported 146 leads into Odoo CRM, tagged by Tier 1 and Tier 2.

## 2. WHAT CHANGED
- ~/myarra-connector-repo/ is the new source of truth for the Odoo connector.
- Odoo manifest currency changed to EUR.
- Odoo CRM tags created for Tier 1 (Packaging, Cosmetics, Food, Bottling, Partners) and Tier 2 (Beverage).

## 3. WHAT IS VERIFIED
- Odoo Apps Store listing is Active and live at https://apps.odoo.com/apps/modules/20.0/myarra_connector/.
- Luxo icon renders correctly.
- CRM holds 146 vetted leads.
- Apify scraping works efficiently (cost ~$3.73 for two runs).

## 4. WHAT IS NOT VERIFIED
- Odoo HTML compliance: The index.html description contains external links to raw.githubusercontent.com for image enlargement. Odoo vendor guidelines may strip these. A compliant rewrite is pending.
- 12 unclassified records remain in the CRM None tag group.
- Kingswood Company and Alene's Candles are missing from the scrape and not yet in the CRM.

## 5. NEXT INSTANCE MUST DO
1. Rewrite index.html to remove external links (use local relative paths only).
2. Review and tag/delete the 12 unknown CRM records.
3. Manually add Kingswood and Alene's Candles to the CRM.
4. Begin outreach to Tier 1 partners and manufacturers.

## 6. LESSONS / WORKING METHOD ADDITIONS
- Odoo CRM bulk tag editing is finicky; using list view and updating tags manually in bulk is safer than custom filters for does not contain.
- Apify Google Maps Scraper is highly cost-effective for regional B2B lead generation.
- Always verify git branch default settings on GitHub; Odoo requires the default branch to match the series (e.g., 20.0).

END OF DELTA.
