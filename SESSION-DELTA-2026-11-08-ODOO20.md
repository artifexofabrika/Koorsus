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
