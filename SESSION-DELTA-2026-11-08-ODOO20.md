# MYARRA — SESSION DELTA, 2026-11-08 (Odoo 20 Adaptation)

Read alongside 2026-11-07-REWRITE.

## 1. TEST ENVIRONMENT

Docker on Windows 11, network odoo-net:
- odoo-db (postgres:16)
- odoo-test (odoo:20) at 8069, database myarra

CRITICAL: Odoo 20 requires PostgreSQL 16. Version 15 fails with function any_value(integer) does not exist.
Login admin/admin on database myarra.

## 2. MODULE CHANGES FOR ODOO 20

Settings view anchor changed from //div[hasclass(settings)] to //form with app/block/setting children. Odoo 17 rewrote the settings architecture.

mrp_production_views.xml removed from manifest: inherited //tree which Odoo 17 renamed to list. Sync button currently absent from MRP Production list view. Follow-up: rewrite for list, 15 minutes.

Version string changed 18.0.1.0.0 to 20.0.1.0.0 so Odoo 20 accepts the module.

## 3. VERIFIED

- Module installs on Odoo 20, log ends Modules loaded, no errors.
- Settings page renders with Myarra group and two fields (API URL, API Token).
- Container-to-Jetson connectivity works: curl POST to /api/odoo/jobs returns errors empty imported 0.

## 4. NOT VERIFIED

- Sync button (does not exist yet).
- Actual MO import (needs the button).

## 5. NEXT INSTANCE MUST DO

1. Restore Sync button: rewrite mrp_production_views.xml for list, re-add to manifest, test with real MO.
2. Capture Odoo Settings screenshot for App Store (screenshot_5).
3. Rebuild tarball: cd ~/odoo_connector and tar -czf myarra_connector.tar.gz myarra_connector/
4. Upload to apps.odoo.com/apps/upload.

## 6. LESSONS

- Set-Content in Windows PowerShell writes UTF-16 and breaks Python. Use [IO.File]::WriteAllText with explicit UTF-8.
- docker exec odoo -d ... -i ... does not inherit container env vars. Pass --db_host, --db_user, --db_password explicitly.
- docker restart required after addon changes for web server to see new views.

END OF DELTA.

---

## 7. ADDENDUM — END-TO-END SYNC VERIFIED (2026-11-08, later)

The Sync button was restored and the full Odoo-to-Myarra path was proven:

1. Created product with default_code COS-CMP-RS via Odoo shell.
2. Created MO WH/MO/00002 for qty 1000.
3. Clicked Sync to Myarra in Manufacturing > Operations > Manufacturing Orders.
4. Odoo returned green notification: Synced: 1 jobs.
5. Verified in Myarra database:

   sqlite3 /mnt/lake/myarra.db SELECT id, job_number, sku_id, line_id, target_quantity, status FROM jobs WHERE job_number LIKE "WH/%"
   -> 31|WH/MO/00002|1|1|1000|scheduled

That is the full loop: Odoo MO -> connector module -> Jetson API -> Myarra jobs table, with SKU correctly mapped from default_code to sku_id.

### The fix that unblocked it
The Sync button view was rewritten for Odoo 20's list view (tree was renamed to list). The Python model used ir.config_parameter.get_param() which does not exist in Odoo 20; replaced with a search() on the key. Full corrected files are in the repository at odoo_connector/myarra_connector/.

### Submission package
Tarball built at ~/odoo_connector/myarra_connector.tar.gz (460KB), copied to Windows Desktop. Contains 5 screenshots including screenshot_5_odoo_sync.png (the Sync button in action), clean manifest, verified model and view files. Ready to upload.

### Remaining before Friday
- Odoo Apps Store vendor account setup (if not already created).
- Upload myarra_connector.tar.gz at https://apps.odoo.com/apps/upload.
- Fill the submission form using outreach/odoo_listing.md.
- Set price 99 USD, license OPL-1.

END OF ADDENDUM.
