"""Export the ten onboarding tables from the current DB into template-format
CSVs under demo-data/. Run once, commit the CSVs. Idempotent."""
import csv
import sqlite3
from pathlib import Path

DB = "/mnt/lake/myarra.db"
OUT = Path.home() / "Client-Demo" / "demo-data"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row


def write(name, headers, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"{name}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    print(f"  {name}.csv: {len(rows)} rows")


print("EXPORTING DEMO DATA")
write("lines", ["id", "name", "format_type"],
      [(r["id"], r["name"], r["format_type"])
       for r in conn.execute("SELECT * FROM lines ORDER BY id")])

write("skus", ["part_number", "description", "case_pack", "active"],
      [(r["part_number"], r["description"], r["case_pack"], r["active"])
       for r in conn.execute("SELECT * FROM skus ORDER BY id")])

write("component_types", ["name", "is_serial", "default_swap_min"],
      [(r["name"], r["is_serial"], r["default_swap_min"])
       for r in conn.execute("SELECT * FROM component_types ORDER BY id")])

write("sku_bom", ["sku_part_number", "component_name", "component_value"],
      [(r["pn"], r["cname"], r["component_value"]) for r in conn.execute("""
          SELECT s.part_number AS pn, ct.name AS cname, b.component_value
          FROM sku_bom b
          JOIN skus s ON s.id = b.sku_id
          JOIN component_types ct ON ct.id = b.component_type_id
          ORDER BY s.id, ct.id""")])

write("line_sku_rates", ["line_id", "sku_part_number", "ideal_rate"],
      [(r["line_id"], r["part_number"], r["ideal_rate"]) for r in conn.execute("""
          SELECT r.line_id, s.part_number, r.ideal_rate
          FROM line_sku_rates r JOIN skus s ON s.id = r.sku_id
          ORDER BY r.line_id, s.id""")])

write("co_procedures", ["line_id", "from_sku_part_number", "to_sku_part_number",
                        "name", "aggregate_standard_min"],
      [(r["line_id"], r["fpn"], r["tpn"], r["name"], r["aggregate_standard_min"])
       for r in conn.execute("""
          SELECT p.line_id, sf.part_number AS fpn, st.part_number AS tpn,
                 p.name, p.aggregate_standard_min
          FROM co_procedures_v2 p
          JOIN skus sf ON sf.id = p.from_sku_id
          JOIN skus st ON st.id = p.to_sku_id
          ORDER BY p.line_id, p.id""")])

write("co_steps", ["line_id", "from_sku_part_number", "to_sku_part_number",
                   "seq", "step_name", "station", "standard_min"],
      [(r["line_id"], r["fpn"], r["tpn"], r["seq"], r["step_name"],
        r["station"], r["standard_min"])
       for r in conn.execute("""
          SELECT p.line_id, sf.part_number AS fpn, st.part_number AS tpn,
                 s.seq, s.step_name, s.station, s.standard_min
          FROM co_steps_v2 s
          JOIN co_procedures_v2 p ON p.id = s.procedure_id
          JOIN skus sf ON sf.id = p.from_sku_id
          JOIN skus st ON st.id = p.to_sku_id
          ORDER BY p.line_id, p.id, s.seq""")])

write("jobs", ["job_number", "sku_part_number", "line_id",
               "target_quantity", "scheduled_start", "scheduled_end"],
      [(r["job_number"], r["part_number"], r["line_id"],
        r["target_quantity"], r["scheduled_start"], r["scheduled_end"])
       for r in conn.execute("""
          SELECT j.job_number, s.part_number, j.line_id,
                 j.target_quantity, j.scheduled_start, j.scheduled_end
          FROM jobs j JOIN skus s ON s.id = j.sku_id
          ORDER BY j.id""")])

write("users", ["name", "role", "line_id", "telegram_id", "active"],
      [(r["name"], r["role"], r["line_id"], r["telegram_id"], r["active"])
       for r in conn.execute("SELECT * FROM users ORDER BY id")])

write("settings", ["key", "value", "description"],
      [(r["key"], r["value"], r["description"])
       for r in conn.execute("SELECT * FROM settings ORDER BY key")])

conn.close()
print("DONE")
