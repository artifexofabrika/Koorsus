"""Myarra onboarding templates. Stage 1: download only."""
import io
import csv

TEMPLATES = {
    'lines': {
        'filename': 'lines.csv',
        'description': 'Lines in the plant',
        'headers': ['id', 'name', 'format_type'],
        'examples': [
            [1, 'Cosmetics Compacts', 'cosmetics'],
            [2, 'Cosmetics Foundation', 'cosmetics'],
        ],
    },
    'skus': {
        'filename': 'skus.csv',
        'description': 'SKUs and part numbers. case_pack is units per case.',
        'headers': ['part_number', 'description', 'case_pack', 'active'],
        'examples': [
            ['COS-CMP-RS', 'Compact Rose 0.25oz', 12, 1],
            ['COS-CMP-SD', 'Compact Sand 0.25oz', 12, 1],
        ],
    },
    'component_types': {
        'filename': 'component_types.csv',
        'description': 'BOM component types. is_serial=1 means the component always changes (e.g. formulation).',
        'headers': ['name', 'is_serial', 'default_swap_min'],
        'examples': [
            ['case', 0, 12],
            ['formulation', 1, 10],
        ],
    },
    'sku_bom': {
        'filename': 'sku_bom.csv',
        'description': 'Bill of materials per SKU. One row per component per SKU.',
        'headers': ['sku_part_number', 'component_name', 'component_value'],
        'examples': [
            ['COS-CMP-RS', 'case', 'rose-blk'],
            ['COS-CMP-RS', 'formulation', 'rose-pwd'],
        ],
    },
    'line_sku_rates': {
        'filename': 'line_sku_rates.csv',
        'description': 'Ideal production rate per line per SKU, in units per HOUR.',
        'headers': ['line_id', 'sku_part_number', 'ideal_rate'],
        'examples': [
            [1, 'COS-CMP-RS', 7200],
            [1, 'COS-CMP-SD', 7200],
        ],
    },
    'co_procedures': {
        'filename': 'co_procedures.csv',
        'description': 'Changeover procedures: line, from-SKU, to-SKU, standard minutes.',
        'headers': ['line_id', 'from_sku_part_number', 'to_sku_part_number',
                    'name', 'aggregate_standard_min'],
        'examples': [
            [1, 'COS-CMP-RS', 'COS-CMP-SD', 'Cosmetics Rose to Sand', 40],
            [1, 'COS-CMP-SD', 'COS-CMP-RS', 'Cosmetics Sand to Rose', 40],
        ],
    },
    'co_steps': {
        'filename': 'co_steps.csv',
        'description': 'Steps per changeover procedure. Identified by line + from + to.',
        'headers': ['line_id', 'from_sku_part_number', 'to_sku_part_number',
                    'seq', 'step_name', 'station', 'standard_min'],
        'examples': [
            [1, 'COS-CMP-RS', 'COS-CMP-SD', 1, 'Change case', 'case_feeder', 12],
            [1, 'COS-CMP-RS', 'COS-CMP-SD', 2, 'Change formulation', 'filler', 10],
        ],
    },
    'jobs': {
        'filename': 'jobs.csv',
        'description': 'Weekly schedule. Uploaded again each week; existing job numbers are updated.',
        'headers': ['job_number', 'sku_part_number', 'line_id',
                    'target_quantity', 'scheduled_start', 'scheduled_end'],
        'examples': [
            ['WO-2026-100', 'COS-CMP-RS', 1, 120000,
             '2026-11-04T07:00:00', '2026-11-04T15:00:00'],
            ['WO-2026-101', 'COS-CMP-SD', 1, 100000,
             '2026-11-04T15:00:00', '2026-11-04T23:00:00'],
        ],
    },
    'users': {
        'filename': 'users.csv',
        'description': 'Line leads and managers. telegram_id maps to a Telegram account.',
        'headers': ['name', 'role', 'line_id', 'telegram_id', 'active'],
        'examples': [
            ['Randy Wolf', 'Admin', 1, '7451582244', 1],
            ['Alice Smith', 'Lead', 1, '1234567890', 1],
        ],
    },
    'settings': {
        'filename': 'settings.csv',
        'description': 'Configuration: unit label, shift times, lunch duration.',
        'headers': ['key', 'value', 'description'],
        'examples': [
            ['unit_label', 'containers', 'What a single output unit is called'],
            ['case_label', 'cases', 'Display label for cases'],
        ],
    },
}


def generate_csv(name):
    """Return CSV text for the named template, or None if unknown."""
    if name not in TEMPLATES:
        return None
    t = TEMPLATES[name]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(t['headers'])
    for row in t['examples']:
        writer.writerow(row)
    return buf.getvalue()
