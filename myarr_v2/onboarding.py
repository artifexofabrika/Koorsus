"""Myarra onboarding. Stage 1: download templates. Stage 2: full upload with resolution."""
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


# Server-side enforced processing order regardless of form submission order
INGEST_ORDER = [
    'settings', 'component_types', 'lines', 'skus', 'sku_bom',
    'line_sku_rates', 'co_procedures', 'co_steps', 'jobs', 'users',
]

# Required headers per template. Extra columns in the uploaded CSV are silently ignored.
REQUIRED_HEADERS = {
    'settings':        ['key', 'value'],
    'component_types': ['name', 'default_swap_min'],
    'lines':           ['id', 'name'],
    'skus':            ['part_number', 'case_pack'],
    'sku_bom':         ['sku_part_number', 'component_name', 'component_value'],
    'line_sku_rates':  ['line_id', 'sku_part_number', 'ideal_rate'],
    'co_procedures':   ['line_id', 'from_sku_part_number', 'to_sku_part_number',
                        'aggregate_standard_min'],
    'co_steps':        ['line_id', 'from_sku_part_number', 'to_sku_part_number',
                        'seq', 'step_name', 'standard_min'],
    'jobs':            ['job_number', 'sku_part_number', 'line_id',
                        'target_quantity', 'scheduled_start', 'scheduled_end'],
    'users':           ['name', 'telegram_id'],
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


# ---------- Resolution helpers ----------

def resolve_sku(conn, part_number):
    if not part_number:
        return None
    r = conn.execute("SELECT id FROM skus WHERE part_number=?", (part_number,)).fetchone()
    return r[0] if r else None


def resolve_component_type(conn, name):
    if not name:
        return None
    r = conn.execute("SELECT id FROM component_types WHERE name=?", (name,)).fetchone()
    return r[0] if r else None


def resolve_procedure(conn, line_id, from_sku_id, to_sku_id):
    if not (line_id and from_sku_id and to_sku_id):
        return None
    r = conn.execute(
        "SELECT id FROM co_procedures_v2 WHERE line_id=? AND from_sku_id=? AND to_sku_id=?",
        (line_id, from_sku_id, to_sku_id)
    ).fetchone()
    return r[0] if r else None


def _int_or_none(v):
    if v is None or v == '':
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


def _float_or_none(v):
    if v is None or v == '':
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


# ---------- Per-template ingest handlers ----------

def _ingest_settings(conn, rows, errors):
    succeeded = 0
    for idx, row in enumerate(rows, start=2):
        key = row.get('key', '').strip()
        value = row.get('value', '').strip()
        desc = row.get('description', '').strip() or None
        if not key:
            errors.append({'line': idx, 'message': 'missing key'}); continue
        conn.execute(
            "INSERT INTO settings (key, value, description) VALUES (?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, description=excluded.description",
            (key, value, desc))
        succeeded += 1
    return succeeded


def _ingest_component_types(conn, rows, errors):
    succeeded = 0
    for idx, row in enumerate(rows, start=2):
        name = row.get('name', '').strip()
        is_serial = _int_or_none(row.get('is_serial'))
        if is_serial is None:
            is_serial = 0
        dsm = _float_or_none(row.get('default_swap_min'))
        if not name:
            errors.append({'line': idx, 'message': 'missing name'}); continue
        if dsm is None:
            errors.append({'line': idx, 'message': 'missing default_swap_min'}); continue
        conn.execute(
            "INSERT INTO component_types (name, is_serial, default_swap_min) VALUES (?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET is_serial=excluded.is_serial, default_swap_min=excluded.default_swap_min",
            (name, is_serial, dsm))
        succeeded += 1
    return succeeded


def _ingest_lines(conn, rows, errors):
    succeeded = 0
    for idx, row in enumerate(rows, start=2):
        lid = _int_or_none(row.get('id'))
        name = row.get('name', '').strip()
        fmt = row.get('format_type', '').strip() or None
        if lid is None:
            errors.append({'line': idx, 'message': 'missing id'}); continue
        if not name:
            errors.append({'line': idx, 'message': 'missing name'}); continue
        conn.execute(
            "INSERT INTO lines (id, name, format_type) VALUES (?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, format_type=excluded.format_type",
            (lid, name, fmt))
        succeeded += 1
    return succeeded


def _ingest_skus(conn, rows, errors):
    succeeded = 0
    for idx, row in enumerate(rows, start=2):
        pn = row.get('part_number', '').strip()
        desc = row.get('description', '').strip() or None
        cp = _int_or_none(row.get('case_pack'))
        active = _int_or_none(row.get('active'))
        if active is None:
            active = 1
        if not pn:
            errors.append({'line': idx, 'message': 'missing part_number'}); continue
        if cp is None:
            errors.append({'line': idx, 'message': 'missing case_pack'}); continue
        conn.execute(
            "INSERT INTO skus (part_number, description, case_pack, active) VALUES (?,?,?,?) "
            "ON CONFLICT(part_number) DO UPDATE SET description=excluded.description, case_pack=excluded.case_pack, active=excluded.active",
            (pn, desc, cp, active))
        succeeded += 1
    return succeeded


def _ingest_sku_bom(conn, rows, errors):
    succeeded = 0
    for idx, row in enumerate(rows, start=2):
        pn = row.get('sku_part_number', '').strip()
        cname = row.get('component_name', '').strip()
        cval = row.get('component_value', '').strip()
        if not pn:
            errors.append({'line': idx, 'message': 'missing sku_part_number'}); continue
        if not cname:
            errors.append({'line': idx, 'message': 'missing component_name'}); continue
        if not cval:
            errors.append({'line': idx, 'message': 'missing component_value'}); continue
        sku_id = resolve_sku(conn, pn)
        if sku_id is None:
            errors.append({'line': idx, 'message': f'unknown SKU "{pn}"'}); continue
        ct_id = resolve_component_type(conn, cname)
        if ct_id is None:
            errors.append({'line': idx, 'message': f'unknown component type "{cname}"'}); continue
        conn.execute(
            "INSERT INTO sku_bom (sku_id, component_type_id, component_value) VALUES (?,?,?) "
            "ON CONFLICT(sku_id, component_type_id) DO UPDATE SET component_value=excluded.component_value",
            (sku_id, ct_id, cval))
        succeeded += 1
    return succeeded


def _ingest_line_sku_rates(conn, rows, errors):
    succeeded = 0
    for idx, row in enumerate(rows, start=2):
        lid = _int_or_none(row.get('line_id'))
        pn = row.get('sku_part_number', '').strip()
        rate = _float_or_none(row.get('ideal_rate'))
        if lid is None:
            errors.append({'line': idx, 'message': 'missing line_id'}); continue
        if not pn:
            errors.append({'line': idx, 'message': 'missing sku_part_number'}); continue
        if rate is None:
            errors.append({'line': idx, 'message': 'missing ideal_rate'}); continue
        sku_id = resolve_sku(conn, pn)
        if sku_id is None:
            errors.append({'line': idx, 'message': f'unknown SKU "{pn}"'}); continue
        conn.execute(
            "INSERT INTO line_sku_rates (line_id, sku_id, ideal_rate) VALUES (?,?,?) "
            "ON CONFLICT(line_id, sku_id) DO UPDATE SET ideal_rate=excluded.ideal_rate",
            (lid, sku_id, rate))
        succeeded += 1
    return succeeded


def _ingest_co_procedures(conn, rows, errors):
    succeeded = 0
    for idx, row in enumerate(rows, start=2):
        lid = _int_or_none(row.get('line_id'))
        fpn = row.get('from_sku_part_number', '').strip()
        tpn = row.get('to_sku_part_number', '').strip()
        name = row.get('name', '').strip() or None
        std = _float_or_none(row.get('aggregate_standard_min'))
        if lid is None:
            errors.append({'line': idx, 'message': 'missing line_id'}); continue
        if not fpn:
            errors.append({'line': idx, 'message': 'missing from_sku_part_number'}); continue
        if not tpn:
            errors.append({'line': idx, 'message': 'missing to_sku_part_number'}); continue
        if std is None:
            errors.append({'line': idx, 'message': 'missing aggregate_standard_min'}); continue
        fs = resolve_sku(conn, fpn)
        if fs is None:
            errors.append({'line': idx, 'message': f'unknown SKU "{fpn}"'}); continue
        ts = resolve_sku(conn, tpn)
        if ts is None:
            errors.append({'line': idx, 'message': f'unknown SKU "{tpn}"'}); continue
        conn.execute(
            "INSERT INTO co_procedures_v2 (line_id, from_sku_id, to_sku_id, name, aggregate_standard_min) VALUES (?,?,?,?,?) "
            "ON CONFLICT(line_id, from_sku_id, to_sku_id) DO UPDATE SET name=excluded.name, aggregate_standard_min=excluded.aggregate_standard_min",
            (lid, fs, ts, name, std))
        succeeded += 1
    return succeeded


def _ingest_co_steps(conn, rows, errors, full_replace=False):
    """Per-procedure step ingestion.

    Default (full_replace=False): delete only the (procedure_id, seq) rows
    present in the CSV, then insert. Steps not mentioned are left alone.
    With full_replace=True: delete ALL steps for each procedure in the CSV,
    then insert. Opt-in, protected by a checkbox on /setup.
    If any row in a group is invalid, that procedure is left untouched."""
    groups = {}
    for idx, row in enumerate(rows, start=2):
        lid = _int_or_none(row.get('line_id'))
        fpn = row.get('from_sku_part_number', '').strip()
        tpn = row.get('to_sku_part_number', '').strip()
        groups.setdefault((lid, fpn, tpn), []).append((idx, row))

    succeeded = 0
    for (lid, fpn, tpn), group_rows in groups.items():
        if lid is None or not fpn or not tpn:
            for idx, _ in group_rows:
                errors.append({'line': idx, 'message': 'missing line_id or SKU part number'})
            continue
        fs = resolve_sku(conn, fpn)
        ts = resolve_sku(conn, tpn)
        if fs is None or ts is None:
            missing = fpn if fs is None else tpn
            for idx, _ in group_rows:
                errors.append({'line': idx, 'message': f'unknown SKU "{missing}"'})
            continue
        proc_id = resolve_procedure(conn, lid, fs, ts)
        if proc_id is None:
            for idx, _ in group_rows:
                errors.append({'line': idx, 'message': f'no procedure for line {lid} {fpn}->{tpn}'})
            continue

        step_tuples = []
        group_failed = False
        for idx, row in group_rows:
            seq = _int_or_none(row.get('seq'))
            step_name = row.get('step_name', '').strip()
            station = row.get('station', '').strip() or None
            std = _float_or_none(row.get('standard_min'))
            if seq is None:
                errors.append({'line': idx, 'message': 'missing seq'})
                group_failed = True; continue
            if not step_name:
                errors.append({'line': idx, 'message': 'missing step_name'})
                group_failed = True; continue
            if std is None:
                errors.append({'line': idx, 'message': 'missing standard_min'})
                group_failed = True; continue
            step_tuples.append((seq, step_name, station, std))

        if group_failed:
            continue

        if full_replace:
            conn.execute("DELETE FROM co_steps_v2 WHERE procedure_id=?", (proc_id,))
        else:
            for seq, _, _, _ in step_tuples:
                conn.execute("DELETE FROM co_steps_v2 WHERE procedure_id=? AND seq=?",
                             (proc_id, seq))
        for seq, step_name, station, std in step_tuples:
            conn.execute(
                "INSERT INTO co_steps_v2 (procedure_id, seq, step_name, station, standard_min) VALUES (?,?,?,?,?)",
                (proc_id, seq, step_name, station, std))
        succeeded += len(step_tuples)

    return succeeded


def _ingest_jobs(conn, rows, errors):
    succeeded = 0
    for idx, row in enumerate(rows, start=2):
        jn = row.get('job_number', '').strip()
        pn = row.get('sku_part_number', '').strip()
        lid = _int_or_none(row.get('line_id'))
        tq = _int_or_none(row.get('target_quantity'))
        ss = row.get('scheduled_start', '').strip() or None
        se = row.get('scheduled_end', '').strip() or None
        if not jn:
            errors.append({'line': idx, 'message': 'missing job_number'}); continue
        if not pn:
            errors.append({'line': idx, 'message': 'missing sku_part_number'}); continue
        if lid is None:
            errors.append({'line': idx, 'message': 'missing line_id'}); continue
        if tq is None:
            errors.append({'line': idx, 'message': 'missing target_quantity'}); continue
        sku_id = resolve_sku(conn, pn)
        if sku_id is None:
            errors.append({'line': idx, 'message': f'unknown SKU "{pn}"'}); continue
        conn.execute(
            "INSERT INTO jobs (job_number, sku_id, line_id, target_quantity, scheduled_start, scheduled_end) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(job_number) DO UPDATE SET sku_id=excluded.sku_id, line_id=excluded.line_id, target_quantity=excluded.target_quantity, scheduled_start=excluded.scheduled_start, scheduled_end=excluded.scheduled_end",
            (jn, sku_id, lid, tq, ss, se))
        succeeded += 1
    return succeeded


def _ingest_users(conn, rows, errors):
    succeeded = 0
    for idx, row in enumerate(rows, start=2):
        name = row.get('name', '').strip()
        role = row.get('role', '').strip() or 'Operator'
        lid = _int_or_none(row.get('line_id'))
        tg = row.get('telegram_id', '').strip()
        active = _int_or_none(row.get('active'))
        if active is None:
            active = 1
        if not name:
            errors.append({'line': idx, 'message': 'missing name'}); continue
        if not tg:
            errors.append({'line': idx, 'message': 'missing telegram_id'}); continue
        conn.execute(
            "INSERT INTO users (name, role, line_id, telegram_id, active) VALUES (?,?,?,?,?) "
            "ON CONFLICT(telegram_id) DO UPDATE SET name=excluded.name, role=excluded.role, line_id=excluded.line_id, active=excluded.active",
            (name, role, lid, tg, active))
        succeeded += 1
    return succeeded


_HANDLERS = {
    'settings':        _ingest_settings,
    'component_types': _ingest_component_types,
    'lines':           _ingest_lines,
    'skus':            _ingest_skus,
    'sku_bom':         _ingest_sku_bom,
    'line_sku_rates':  _ingest_line_sku_rates,
    'co_procedures':   _ingest_co_procedures,
    'co_steps':        _ingest_co_steps,
    'jobs':            _ingest_jobs,
    'users':           _ingest_users,
}


# ---------- Public entry point ----------

def ingest_template(conn, template_name, file_stream, full_replace=False):
    """Ingest one template. Returns dict with uploaded, succeeded, failed, errors."""
    if template_name not in TEMPLATES:
        return {'uploaded': 0, 'succeeded': 0, 'failed': 0,
                'errors': [{'line': 0, 'message': f'unknown template "{template_name}"'}]}

    try:
        raw = file_stream.stream.read()
        text = raw.decode('utf-8-sig', errors='replace')
    except Exception as e:
        return {'uploaded': 0, 'succeeded': 0, 'failed': 0,
                'errors': [{'line': 0, 'message': f'could not read file: {e}'}]}

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return {'uploaded': 0, 'succeeded': 0, 'failed': 0,
                'errors': [{'line': 0, 'message': 'empty file (no header row)'}]}

    headers_lower = {}
    for h in reader.fieldnames:
        if h is None:
            continue
        headers_lower[h.strip().lower()] = h

    missing = [h for h in REQUIRED_HEADERS[template_name] if h.lower() not in headers_lower]
    if missing:
        return {'uploaded': 0, 'succeeded': 0, 'failed': 0,
                'errors': [{'line': 0, 'message': f'missing required columns: {", ".join(missing)}'}]}

    rows = []
    for row in reader:
        normed = {}
        for k, v in row.items():
            if k is None:
                continue
            normed[k.strip().lower()] = '' if v is None else str(v).strip()
        rows.append(normed)

    uploaded = len(rows)
    errors = []
    handler = _HANDLERS[template_name]
    try:
        if template_name == 'co_steps':
            succeeded = handler(conn, rows, errors, full_replace=full_replace)
        else:
            succeeded = handler(conn, rows, errors)
        conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return {'uploaded': uploaded, 'succeeded': 0, 'failed': uploaded,
                'errors': [{'line': 0, 'message': f'ingest aborted: {e}'}]}

    succeeded = max(0, min(succeeded, uploaded))
    return {
        'uploaded': uploaded,
        'succeeded': succeeded,
        'failed': uploaded - succeeded,
        'errors': errors,
    }
