"""Myarra admin operations: database export and reset."""
import csv
import io
import sqlite3
import zipfile
from datetime import datetime
from flask import Blueprint, Response, redirect, request, url_for
from db import get_db_connection

admin_ops_bp = Blueprint('admin_ops', __name__)

EXPORT_TABLES = [
    'lines', 'skus', 'component_types', 'sku_bom', 'line_sku_rates',
    'co_procedures_v2', 'co_steps_v2', 'jobs', 'users', 'settings',
    'hourly_runs', 'downtime_events', 'co_events', 'co_event_steps',
    'co_event_changes', 'line_events',
    'maintenance_events', 'shift_handovers',
    'experiments', 'experiment_actions', 'fishbone_causes',
]

# Children before parents, so a future FK-enabled schema still works.
SOFT_RESET_TABLES = [
    'downtime_events', 'hourly_runs',
    'co_event_steps', 'co_event_changes', 'co_events',
    'line_events', 'bot_sessions',
]

HARD_RESET_TABLES = SOFT_RESET_TABLES + [
    'fishbone_causes', 'experiment_actions', 'experiments',
    'jobs', 'sku_bom', 'line_sku_rates',
    'co_steps_v2', 'co_procedures_v2',
    'skus', 'component_types', 'lines',
]


@admin_ops_bp.route('/setup/export')
def export_all():
    conn = get_db_connection()
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    buf = io.BytesIO()
    manifest = [
        "Myarra database export",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
    ]
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for table in EXPORT_TABLES:
            try:
                cur = conn.execute(f"SELECT * FROM {table}")
                cols = [d[0] for d in cur.description] if cur.description else []
                rows = cur.fetchall()
            except sqlite3.Error as e:
                manifest.append(f"{table}: SKIPPED ({e})")
                continue
            text = io.StringIO()
            writer = csv.writer(text)
            writer.writerow(cols)
            for row in rows:
                writer.writerow([row[c] for c in cols])
            zf.writestr(f"{table}.csv", text.getvalue())
            manifest.append(f"{table}.csv: {len(rows)} rows")
        manifest += [
            "",
            "Onboarding re-import: /setup accepts lines, skus, component_types,",
            "  sku_bom, line_sku_rates, co_procedures, co_steps, jobs, users, settings.",
            "Other CSVs are archival only (they use internal IDs).",
        ]
        zf.writestr("MANIFEST.txt", "\n".join(manifest) + "\n")
    conn.close()
    buf.seek(0)
    return Response(
        buf.getvalue(),
        mimetype='application/zip',
        headers={'Content-Disposition': f'attachment; filename="myarra-export-{ts}.zip"'},
    )


@admin_ops_bp.route('/setup/reset', methods=['POST'])
def reset_database():
    confirm = (request.form.get('confirm') or '').strip()
    mode = request.form.get('reset_mode', 'soft')
    if confirm != 'RESET':
        return redirect(url_for('setup') + '?reset_error=Type+RESET+exactly+to+confirm')
    if mode not in ('soft', 'hard'):
        return redirect(url_for('setup') + '?reset_error=Unknown+reset+mode')
    tables = SOFT_RESET_TABLES if mode == 'soft' else HARD_RESET_TABLES
    conn = get_db_connection()
    total = 0
    try:
        for t in tables:
            n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            conn.execute(f"DELETE FROM {t}")
            total += n
        conn.commit()
    except Exception as e:
        try: conn.rollback()
        except Exception: pass
        conn.close()
        return redirect(url_for('setup') + '?reset_error=' + str(e).replace(' ', '+'))
    conn.close()
    return redirect(url_for('setup') + f'?reset_done={mode}&rows={total}')
