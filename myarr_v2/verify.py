"""Myarra Stage 3: /setup/verify blueprint."""
import sqlite3
from flask import Blueprint, render_template
from db import get_db_connection

verify_bp = Blueprint('verify', __name__)

TABLES = [
    ('lines', 'Lines'),
    ('skus', 'SKUs'),
    ('component_types', 'Component types'),
    ('sku_bom', 'SKU BOM'),
    ('line_sku_rates', 'Line-SKU rates'),
    ('co_procedures_v2', 'Changeover procedures'),
    ('co_steps_v2', 'Changeover steps'),
    ('jobs', 'Jobs'),
    ('users', 'Users'),
    ('settings', 'Settings'),
]


def _count(conn, table):
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except sqlite3.Error:
        return 0


def _preview(conn, table, limit=3):
    try:
        cur = conn.execute(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT {limit}")
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = [dict(zip(cols, tuple(r))) for r in cur.fetchall()]
        return cols, rows
    except sqlite3.Error:
        return [], []


def _warnings(conn):
    out = []

    for r in conn.execute("""
        SELECT s.part_number FROM skus s
        WHERE NOT EXISTS (SELECT 1 FROM line_sku_rates r WHERE r.sku_id = s.id)
        ORDER BY s.part_number LIMIT 10
    """).fetchall():
        out.append(f"SKU {r['part_number']} has no line rate")

    for r in conn.execute("""
        SELECT p.id, l.name AS line_name, pf.part_number AS from_pn, pt.part_number AS to_pn
        FROM co_procedures_v2 p
        LEFT JOIN lines l ON l.id = p.line_id
        LEFT JOIN skus pf ON pf.id = p.from_sku_id
        LEFT JOIN skus pt ON pt.id = p.to_sku_id
        WHERE NOT EXISTS (SELECT 1 FROM co_steps_v2 s WHERE s.procedure_id = p.id)
        ORDER BY p.id LIMIT 10
    """).fetchall():
        out.append(f"Procedure on {r['line_name']} {r['from_pn']} -> {r['to_pn']} has no steps defined")

    for r in conn.execute("""
        SELECT j.job_number FROM jobs j
        WHERE j.sku_id IS NULL
           OR NOT EXISTS (SELECT 1 FROM skus s WHERE s.id = j.sku_id)
        ORDER BY j.job_number LIMIT 10
    """).fetchall():
        out.append(f"Job {r['job_number']} references an unknown SKU")

    for r in conn.execute("""
        SELECT l.id, l.name FROM lines l
        WHERE NOT EXISTS (SELECT 1 FROM line_sku_rates r WHERE r.line_id = l.id)
        ORDER BY l.id LIMIT 10
    """).fetchall():
        out.append(f"Line {r['id']} ({r['name']}) has no SKUs assigned")

    for r in conn.execute("""
        SELECT s.part_number FROM skus s
        WHERE NOT EXISTS (SELECT 1 FROM sku_bom b WHERE b.sku_id = s.id)
        ORDER BY s.part_number LIMIT 10
    """).fetchall():
        out.append(f"SKU {r['part_number']} has no BOM components")

    return out


@verify_bp.route('/setup/verify')
def setup_verify():
    conn = get_db_connection()
    tables = []
    for table, label in TABLES:
        tables.append({
            'table': table,
            'label': label,
            'count': _count(conn, table),
            'cols': None,
            'rows': None,
        })
        tables[-1]['cols'], tables[-1]['rows'] = _preview(conn, table)
    warnings = _warnings(conn)
    conn.close()
    return render_template('setup_verify.html', tables=tables, warnings=warnings)
