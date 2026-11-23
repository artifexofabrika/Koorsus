#!/usr/bin/env python3
"""Generate 90 days of Myarra history ending today.

Two delivery routes, deliberately different:

  1. Master data goes through the onboarding import route. This script builds the
     same CSV text /setup hands to onboarding, and passes each one to
     myarr_v2.onboarding.ingest_template in INGEST_ORDER: settings,
     component_types, lines, skus, sku_bom, line_sku_rates, co_procedures,
     co_steps, jobs, users. The text is built in memory, so no CSV is written to
     disk and the only file this script touches is the database.

  2. Event history has no CSV template, because the application writes those
     rows and nothing imports them. hourly_runs, downtime_events, line_events,
     co_events and their children are written here with sqlite3.

Invariants (tools/schema.sql is the only source of truth for the tables):
  * hourly_runs.units_filled INCLUDES scrap; good units are never stored.
  * shift is the string '1'/'2'/'3', matching settings shift_N_start.
  * every timestamp is naive local ISO 8601, no UTC, no offset.
  * zero-production hours exist, with a note saying why.
  * superseded=1 rows carry override_reason and have a replacement row.
  * exactly one open line_events row per line, no overlaps.
  * two SKU/line pairs have no rate row on purpose; the open job on one of them
    is what makes the reporting pages print "no rate loaded".
  * three or four completed jobs miss target with a NULL
    completion_variance_reason, so the variance gate has something to refuse.

Re-runnable: it deletes only the rows it owns, then rewrites them. Owned rows are
hourly_runs.source='gen90', line_events.source='gen90', co_events.source='gen90'
(and their children), downtime_events whose run_id points at one of those, and
jobs numbered WO-2026-41NNN.

On the Jetson:
    python3 tools/gen_myarra_90d.py
"""
import argparse
import csv
import io
import os
import random
import sqlite3
import sys
from datetime import datetime, timedelta

SOURCE = "gen90"
JOB_PREFIX = "WO-2026-4"
JOB_GLOB = "WO-2026-4[0-9][0-9][0-9][0-9]"
DAYS = 90
SEED = 20261123

# The two pairs with no rate row, on purpose. Both are pairs the line really
# runs (their changeover procedures exist), so this is a rate gap, not a
# scheduling impossibility. Do not fill these in.
GAPS = [(2, "COS-FDN-NA"), (5, "JWL-CLN-UN")]

# Today's floor state, so every tile renders on first load:
#   line 2 production, running the job on the unrated pair
#   line 3 production on a rated job
#   line 4 lunch
#   lines 1 and 5 idle
TODAY_PRODUCTION = {2: (1, None), 3: (0, None), 4: (1, "lunch")}


def iso(dt):
    return dt.replace(second=0, microsecond=0).isoformat(timespec="seconds")


def read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def csv_text(headers, rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(headers)
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


class _Upload:
    """What /setup hands to ingest_template: a file object with a .stream."""

    def __init__(self, text):
        self.stream = io.BytesIO(text.encode("utf-8"))


def load_reference(client_dir):
    dd = os.path.join(client_dir, "demo-data")
    ref = {k: read_csv(os.path.join(dd, k + ".csv")) for k in
           ("lines", "skus", "component_types", "sku_bom", "line_sku_rates",
            "co_procedures", "co_steps", "settings", "users")}
    pairs = {}
    for r in ref["line_sku_rates"]:
        pairs.setdefault(int(r["line_id"]), []).append(r["sku_part_number"])
    ref["pairs"] = {k: sorted(v) for k, v in pairs.items()}
    ref["rates"] = {(int(r["line_id"]), r["sku_part_number"]): float(r["ideal_rate"])
                    for r in ref["line_sku_rates"]}
    ref["procs"] = {(int(r["line_id"]), r["from_sku_part_number"], r["to_sku_part_number"]):
                    float(r["aggregate_standard_min"]) for r in ref["co_procedures"]}
    ref["shift_start"] = {}
    for r in ref["settings"]:
        if r["key"].startswith("shift_") and r["key"].endswith("_start"):
            ref["shift_start"][int(r["key"].split("_")[1])] = int(r["value"].split(":")[0])
    ref["shift_start"] = ref["shift_start"] or {1: 7, 2: 15, 3: 23}
    ref["desc"] = {r["part_number"]: r["description"] for r in ref["skus"]}
    ref["line_ids"] = sorted(int(r["id"]) for r in ref["lines"])
    return ref


def line_leads():
    """One lead per line, plus the admin from demo-data. Invented people."""
    rows = [["Randy Wolf", "Admin", 1, "7451582244", 1]]
    for lid, (name, tg) in {1: ("Dana Whitlock", "5510224817"),
                            2: ("Marcus Ordaz", "5510224818"),
                            3: ("Priya Raghunath", "5510224819"),
                            4: ("Tobias Fern", "5510224820"),
                            5: ("Ivy Okonkwo", "5510224821")}.items():
        rows.append([name, "Lead", lid, tg, 1])
    return rows


# ---------------------------------------------------------------- scheduling

def shift_bounds(day, sh, shift_start):
    start = datetime(day.year, day.month, day.day, shift_start[sh])
    return start, start + timedelta(hours=8)


def pick_plan(rng, line_id, day):
    """Shifts a line runs on a day. Lines 3 and 4 run three shifts most weekdays."""
    dow = day.weekday()
    if line_id in (3, 4):
        if dow <= 4:
            if rng.random() >= 0.99:
                return []
            n = 3 if rng.random() < 0.95 else 2
        elif dow == 5:
            if rng.random() >= 0.95:
                return []
            n = 3 if rng.random() < 0.55 else 2
        else:
            if rng.random() >= 0.92:
                return []
            n = 3 if rng.random() < 0.30 else 2
    else:
        if dow <= 4:
            if rng.random() >= (0.96 if line_id == 1 else 0.98):
                return []
            n = 2 if rng.random() < 0.97 else 1
        elif dow == 5:
            if rng.random() >= 0.90:
                return []
            n = 2 if rng.random() < 0.85 else 1
        else:
            if rng.random() >= 0.55:
                return []
            n = 1
    return list(range(1, n + 1))


def off_minutes_in(start, end, offs):
    total = 0.0
    for (_state, s, e, _reason) in offs:
        lo, hi = max(s, start), min(e, end)
        if hi > lo:
            total += (hi - lo).total_seconds() / 60.0
    return total


def production_segments(window_start, window_end, offs):
    segs = [(window_start, window_end)]
    for (_state, s, e, _reason) in sorted(offs, key=lambda x: x[1]):
        out = []
        for a, b in segs:
            if e <= a or s >= b:
                out.append((a, b))
                continue
            if s > a:
                out.append((a, s))
            if e < b:
                out.append((e, b))
        segs = out
    return [(a, b) for a, b in segs if b > a]


def slot_starts(window_start, window_end, shift_start):
    """Hour slots on the shift grid that begin inside the window."""
    out = []
    day = (window_start - timedelta(days=1)).date()
    last = (window_end + timedelta(days=1)).date()
    while day <= last:
        for sh in (1, 2, 3):
            s0, s1 = shift_bounds(day, sh, shift_start)
            for i in range(8):
                t = s0 + timedelta(hours=i)
                if window_start <= t < window_end:
                    out.append((t, sh, i + 1, min(t + timedelta(hours=1), s1)))
        day += timedelta(days=1)
    return out


def build_jobs(rng, ref, today):
    """Every historical job, with its window, its off-time and its changeover."""
    ss = ref["shift_start"]
    start_day = today - timedelta(days=DAYS - 1)
    jobs = []
    seq = 0
    prev_sku = {}
    day = start_day
    while day <= today:
        for lid in ref["line_ids"]:
            if day == today:
                continue
            shifts = pick_plan(rng, lid, day)
            if not shifts:
                continue
            span_start = shift_bounds(day, shifts[0], ss)[0]
            span_end = shift_bounds(day, shifts[-1], ss)[1]
            pair = ref["pairs"][lid]

            r = rng.random()
            if len(shifts) == 3 and r < 0.08:
                n_jobs = 3
            elif len(shifts) >= 2 and r < 0.42:
                n_jobs = 2
            else:
                n_jobs = 1

            first = 0 if prev_sku.get(lid) != pair[0] else 1
            skus = [pair[(first + i) % len(pair)] for i in range(n_jobs)]

            span_min = (span_end - span_start).total_seconds() / 60.0
            cuts = sorted(rng.uniform(0.30, 0.72) for _ in range(n_jobs - 1))

            cursor = span_start
            day_jobs = []
            for i in range(n_jobs):
                sku = skus[i]
                from_sku = day_jobs[-1]["sku"] if day_jobs else prev_sku.get(lid)
                co = None
                if from_sku and from_sku != sku:
                    std = ref["procs"].get((lid, from_sku, sku))
                    if std:
                        m = max(12, int(round(std * rng.uniform(0.78, 1.35))))
                        co = (cursor, cursor + timedelta(minutes=m), (lid, from_sku, sku))
                        cursor = co[1]

                if i < n_jobs - 1:
                    w_end = span_start + timedelta(minutes=span_min * cuts[i])
                    w_end = max(w_end, cursor + timedelta(minutes=60))
                    w_end = min(w_end, span_end)
                else:
                    w_end = span_end
                if w_end <= cursor:
                    w_end = min(cursor + timedelta(minutes=60), span_end)
                # A window too short to run is not a job. Fold it into the one
                # before it rather than leaving a stub that produces nothing and
                # reads as a -100% variance nobody can explain.
                if (w_end - cursor) < timedelta(minutes=120):
                    if day_jobs:
                        day_jobs[-1]["window_end"] = w_end
                        cursor = w_end
                        continue
                    w_end = min(span_end, cursor + timedelta(minutes=120))

                offs = []
                for sh in shifts:
                    s0, _s1 = shift_bounds(day, sh, ss)
                    at = s0 + timedelta(minutes=rng.choice([240, 240, 270, 300]))
                    if cursor <= at < w_end - timedelta(minutes=45) and rng.random() < 0.80:
                        dur = 30 if rng.random() < 0.75 else 45
                        offs.append(("lunch", at, at + timedelta(minutes=dur), "shift lunch"))
                if rng.random() < 0.13:
                    span = (w_end - cursor).total_seconds() / 60.0
                    if span > 150:
                        at = cursor + timedelta(minutes=rng.uniform(40, span - 70))
                        dur = rng.choice([25, 30, 45, 60, 75, 90])
                        if at + timedelta(minutes=dur) < w_end:
                            offs.append(("maintenance", at, at + timedelta(minutes=dur),
                                         rng.choice(["filler nozzle clog", "conveyor jam",
                                                     "capper torque fault",
                                                     "label roll splice",
                                                     "air pressure drop"])))
                cip_p = 0.16 if lid in (3, 4) else 0.05
                if i == n_jobs - 1 and rng.random() < cip_p:
                    dur = rng.choice([45, 50, 60, 70])
                    at = w_end - timedelta(minutes=dur)
                    if at > cursor + timedelta(minutes=90):
                        offs.append(("cip", at, w_end, "end of run CIP"))

                offs.sort(key=lambda x: x[1])
                clean, last_end = [], None
                for st, s, e, rs in offs:
                    if last_end and s < last_end:
                        s = last_end
                        if e <= s:
                            continue
                    clean.append((st, s, e, rs))
                    last_end = e

                jobs.append({
                    "line_id": lid, "sku": sku, "sku_id": None,
                    "window_start": cursor, "window_end": w_end,
                    "offs": clean, "co": co,
                    "rate": ref["rates"].get((lid, sku)),
                    "sibling_rate": ref["rates"].get(
                        (lid, pair[0] if sku != pair[0] else pair[-1])),
                    "number": JOB_PREFIX + "%04d" % (1001 + seq),
                    "status": "completed", "id": None,
                })
                day_jobs.append(jobs[-1])
                seq += 1
                cursor = w_end
                if i < n_jobs - 1:
                    std = ref["procs"].get((lid, sku, skus[i + 1]))
                    if std:
                        m = max(12, int(round(std * rng.uniform(0.78, 1.35))))
                        cursor = cursor + timedelta(minutes=m)
            prev_sku[lid] = day_jobs[-1]["sku"] if day_jobs else prev_sku.get(lid)
        day += timedelta(days=1)
    return jobs


def build_today(rng, ref, now):
    """Today's jobs, built so the floor page shows production, lunch and idle."""
    ss = ref["shift_start"]
    day = now.date()
    jobs = []
    for n, lid in enumerate(sorted(TODAY_PRODUCTION)):
        idx, lunch = TODAY_PRODUCTION[lid]
        pair = ref["pairs"][lid]
        sku = pair[idx % len(pair)]
        # The job occupies the shift the clock is in now, whatever hour this
        # script is run at. A run at 00:30 belongs to shift 3, not to a shift
        # that has not started yet.
        shift_now = 3
        for sh in (1, 2, 3):
            s0, s1 = shift_bounds(day, sh, ss)
            if s0 <= now < s1 or (sh == 3 and now < shift_bounds(day, 1, ss)[0]):
                shift_now = sh if s0 <= now < s1 else 3
                break
        if now < shift_bounds(day, 1, ss)[0]:
            shift_now = 3
            w_start, w_end = shift_bounds(day - timedelta(days=1), 3, ss)
        else:
            w_start, w_end = shift_bounds(day, shift_now, ss)
        if lunch and shift_now != 3:
            w_end = shift_bounds(day, shift_now + 1, ss)[1] if shift_now < 3 else w_end

        # The layout change finished at the bell, so the job starts clean and
        # the floor is not left with a changeover that never happened.
        other = pair[0] if sku != pair[0] else pair[-1]
        std = ref["procs"].get((lid, other, sku))
        co = None
        if std:
            co_end = w_start
            co_start = co_end - timedelta(minutes=max(12, int(round(std * 0.95))))
            co = (co_start, co_end, (lid, other, sku))
        offs = []
        if lunch:
            at = now - timedelta(minutes=18)
            offs.append((lunch, at, at + timedelta(minutes=30), "shift lunch"))
        jobs.append({
            "line_id": lid, "sku": sku, "sku_id": None,
            "window_start": w_start, "window_end": w_end,
            "offs": offs, "co": co,
            "rate": ref["rates"].get((lid, sku)),
            "sibling_rate": ref["rates"].get((lid, pair[0] if sku != pair[0] else pair[-1])),
            "number": JOB_PREFIX + "%04d" % (9001 + n),
            "status": "running", "id": None,
        })
    return jobs


# ---------------------------------------------------------------- writing

class Writer:
    def __init__(self, cur, now, leads, rng):
        self.cur, self.now, self.leads, self.rng = cur, now, leads, rng
        self.events = self.co = self.runs = 0

    def emit(self, line_id, state, start, end, job_id=None, co_event_id=None,
             reason=None, notes=None):
        if end is not None and end <= start:
            return
        self.cur.execute(
            """INSERT INTO line_events
               (line_id,state,started_at,ended_at,job_id,co_event_id,reason,notes,
                user_id,source) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (line_id, state, iso(start), iso(end) if end else None, job_id,
             co_event_id, reason, notes, self.leads.get(line_id), SOURCE))
        self.events += 1

    def idle_fill(self, line_id, start, end, reason):
        """Idle time on the shift grid. end=None leaves the last piece open."""
        cursor = start
        guard = 0
        while guard < 200:
            guard += 1
            midnight = cursor.replace(hour=0, minute=0, second=0, microsecond=0)
            nxt = None
            for h in (7, 15, 23):
                cand = midnight + timedelta(hours=h)
                if cand > cursor:
                    nxt = cand
                    break
            if nxt is None:
                nxt = midnight + timedelta(days=1, hours=7)
            if end is None:
                # chunk up to a day at a time, last chunk open
                chunk_end = min(nxt, cursor + timedelta(hours=24))
                if (self.now - chunk_end) <= timedelta(hours=8):
                    self.emit(line_id, "idle", cursor, None, reason=reason)
                    return
                self.emit(line_id, "idle", cursor, chunk_end, reason=reason)
                cursor = chunk_end
                continue
            if nxt >= end:
                self.emit(line_id, "idle", cursor, end, reason=reason)
                return
            self.emit(line_id, "idle", cursor, nxt, reason=reason)
            cursor = nxt

    def changeover(self, job, prev):
        co_start, co_end, (line_id, _f, _t) = job["co"]
        actual = int((co_end - co_start).total_seconds() / 60.0)
        proc = self.cur.execute(
            "SELECT id FROM co_procedures_v2 WHERE line_id=? AND from_sku_id=? AND to_sku_id=?",
            (line_id, prev["sku_id"], job["sku_id"])).fetchone()
        if not proc:
            return None
        self.cur.execute(
            """INSERT INTO co_events
               (procedure_id,line_id,started_at,ended_at,aggregate_actual_min,operator,
                source,from_job_number,to_job_number,from_job_id,to_job_id,user_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (proc[0], line_id, iso(co_start), iso(co_end), actual,
             None, SOURCE, prev["number"], job["number"], prev["id"], job["id"],
             self.leads.get(line_id)))
        co_id = self.cur.lastrowid
        self.co += 1

        a = {r[0]: r[1] for r in self.cur.execute(
            "SELECT component_type_id, component_value FROM sku_bom WHERE sku_id=?",
            (prev["sku_id"],))}
        b = {r[0]: r[1] for r in self.cur.execute(
            "SELECT component_type_id, component_value FROM sku_bom WHERE sku_id=?",
            (job["sku_id"],))}
        for cid in sorted(set(a) | set(b)):
            if a.get(cid) != b.get(cid):
                self.cur.execute(
                    "INSERT INTO co_event_changes (event_id,component_type_id,from_value,"
                    "to_value,created_at) VALUES (?,?,?,?,?)",
                    (co_id, cid, a.get(cid), b.get(cid), iso(co_end)))

        # per-station actuals against co_steps_v2 standards
        for step_id, std in self.cur.execute(
                "SELECT id, standard_min FROM co_steps_v2 WHERE procedure_id=? ORDER BY seq",
                (proc[0],)).fetchall():
            self.cur.execute(
                "INSERT INTO co_event_steps (event_id,step_id,actual_min,note) VALUES (?,?,?,?)",
                (co_id, step_id, round(std * self.rng.uniform(0.72, 1.38), 1), None))

        self.emit(line_id, "changeover", co_start, co_end, co_event_id=co_id)
        return co_id

    def job_runs(self, job, shift_start):
        w_start, w_end = job["window_start"], job["window_end"]
        running = job["status"] == "running"
        eff_end = min(w_end, self.now) if running else w_end
        segs = production_segments(w_start, eff_end, job["offs"])
        base = job["rate"] or job["sibling_rate"] or 6000.0
        total = 0
        hour_idx = 0.0
        for (slot, sh, period, slot_cap) in slot_starts(w_start, eff_end, shift_start):
            slot_cap = min(slot_cap, eff_end)
            if (slot_cap - slot).total_seconds() < 1800:
                continue  # the hour is still running; the operator has not closed it
            prod = 0.0
            for a, b in segs:
                lo, hi = max(slot, a), min(slot_cap, b)
                if hi > lo:
                    prod += (hi - lo).total_seconds() / 60.0
            if prod <= 0:
                continue
            span_min = (slot_cap - slot).total_seconds() / 60.0
            off = span_min - prod
            if self.rng.random() < 0.055:
                f = self.rng.uniform(0.38, 0.72)      # a trouble hour
            else:
                f = min(1.06, max(0.42, self.rng.gauss(0.965, 0.075)))
            units = int(base * f * prod / 60.0)
            scrap = 0
            note = None
            if prod < 20:
                # An hour the line spent down is worth recording as a zero with
                # the reason attached. An hour clipped by a lunch is not: the
                # operator would log it when it closes.
                down = next(((o[0], o[3]) for o in job["offs"]
                             if o[0] in ("maintenance", "cip")
                             and o[1] < slot_cap and o[2] > slot), None)
                if down and off >= 45:
                    units, scrap = 0, 0
                    note = "%s took the hour, no units run" % down[1]
                else:
                    continue
            elif units > 0:
                scrap = int(units * self.rng.uniform(0.004, 0.045))
                if self.rng.random() < 0.04:
                    scrap = int(units * self.rng.uniform(0.06, 0.10))
                if prod < 55:
                    why = next((o[3] for o in job["offs"] if o[1] < slot_cap and o[2] > slot), None)
                    note = ("started late after %s, %d minutes running" % (why, prod)
                            if why else "%d minutes running this hour" % prod)
                elif self.rng.random() < 0.20:
                    note = self.rng.choice([
                        "ran clean", "startup, first fifteen minutes slow",
                        "short stops on the packer", "waiting on QA release",
                        "steady", "two stops, both cleared at the station",
                        "case erector tripped, reset by the lead"])

            self.cur.execute(
                """INSERT INTO hourly_runs
                   (job_id,line_id,sku_id,shift,period,phase,recorded_at,units_filled,
                    scrap_units,duration_min,operator,raw_text,source,job_hour_start,
                    job_hour_end,user_id,notes,flagged,superseded,override_reason)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (job["id"], job["line_id"], job["sku_id"], str(sh), "H%d" % period,
                 "run", iso(slot), units, scrap, int(round(prod)), None, None, SOURCE,
                 round(hour_idx, 2), round(hour_idx + prod / 60.0, 2),
                 self.leads.get(job["line_id"]), note, 0, 0, None))
            run_id = self.cur.lastrowid
            self.runs += 1
            total += units

            # poor hours carry a downtime record
            if units and units < 0.85 * base * prod / 60.0 and self.rng.random() < 0.70:
                self.cur.execute(
                    "INSERT INTO downtime_events (run_id,station,reason,minutes,note)"
                    " VALUES (?,?,?,?,?)",
                    (run_id,
                     self.rng.choice(["filler", "capper", "labeler", "packer", "depalletizer"]),
                     self.rng.choice(["jam", "no stock", "fault", "waiting on upstream",
                                      "speed loss"]),
                     round(self.rng.uniform(8, 34), 0), note))
            hour_idx += prod / 60.0
        return total


def build_line_history(w, lid, lst):
    """Emit events for one line, in order, contiguous, ending in one open event."""
    last_end = None
    prev = None
    for j in lst:
        if j["co"] and prev is not None:
            co_start, co_end = j["co"][0], j["co"][1]
            dur = co_end - co_start
            if last_end and co_start < last_end:
                # the plan never overlaps, but a job that ran long must not be
                # overrun by the next one's changeover
                co_start = last_end
                co_end = co_start + dur
                j["co"] = (co_start, co_end, j["co"][2])
            if last_end and co_start > last_end:
                w.idle_fill(lid, last_end, co_start, "between jobs")
            if w.changeover(j, prev) is None:
                w.idle_fill(lid, co_start, co_end, "between jobs")
            cursor = co_end
            if j["window_start"] > cursor:
                # today's changeover ran overnight; the job starts at the bell
                w.idle_fill(lid, cursor, j["window_start"], "set up, waiting for shift start")
                cursor = j["window_start"]
        else:
            cursor = j["window_start"]
            if last_end and cursor < last_end:
                cursor = last_end
            if last_end and cursor > last_end:
                w.idle_fill(lid, last_end, cursor, "no work order by planning cut-off")

        running = j["status"] == "running"
        eff_end = min(j["window_end"], w.now) if running else j["window_end"]
        pos = cursor
        for (st, s, e, rs) in j["offs"]:
            s2, e2 = max(s, pos), min(e, eff_end)
            if e2 <= s2:
                continue
            if s2 > pos:
                w.emit(lid, "production", pos, s2, job_id=j["id"])
            still_open = running and e2 >= eff_end
            w.emit(lid, st, s2, None if still_open else e2, job_id=j["id"], reason=rs)
            pos = e2
        if eff_end > pos:
            w.emit(lid, "production", pos, None if running else eff_end, job_id=j["id"])
        last_end = eff_end
        prev = j

    cur_ev = w.cur.execute(
        "SELECT id FROM line_events WHERE line_id=? AND ended_at IS NULL", (lid,)).fetchone()
    if not cur_ev:
        w.idle_fill(lid, last_end or (w.now - timedelta(hours=8)), None,
                    "no work order by planning cut-off")


# ---------------------------------------------------------------- verify

def app_variance(conn_cur, job):
    cur = conn_cur.connection.cursor()
    """deploy/floor-start jobs.py variance_allowance, reimplemented for checking."""
    actual = cur.execute(
        "SELECT SUM(units_filled) FROM hourly_runs WHERE job_id=? AND "
        "(superseded IS NULL OR superseded=0)", (job["id"],)).fetchone()[0] or 0
    target = job["target_quantity"] or 0
    try:
        s = datetime.fromisoformat(job["scheduled_start"])
        e = datetime.fromisoformat(job["scheduled_end"])
    except (TypeError, ValueError):
        return target, target, actual, None
    window = int(round((e - s).total_seconds() / 60.0))
    end = min(e, datetime.now() if job["actual_end"] is None
              else datetime.fromisoformat(job["actual_end"]))
    off = 0.0
    for r in cur.execute("""SELECT started_at, ended_at FROM line_events
                            WHERE line_id=? AND state IN ('lunch','maintenance','cip')
                            AND started_at<? AND (ended_at IS NULL OR ended_at>?)""",
                         (job["line_id"], end.isoformat(), s.isoformat())):
        lo = max(datetime.fromisoformat(r[0]), s)
        hi = min(datetime.fromisoformat(r[1]) if r[1] else end, end)
        if hi > lo:
            off += (hi - lo).total_seconds() / 60.0
    if not window:
        allowed = target
    elif off >= window:
        allowed = 0
    else:
        allowed = int(round(target * (window - off) / float(window)))
    v = None if allowed <= 0 else (actual - allowed) / float(allowed)
    return target, allowed, actual, v


def verify(cur, gaps_with_ids, shift_start):
    print()
    print("checks")
    ok = True

    def line(label, good, detail=""):
        nonlocal ok
        ok = ok and good
        print("  [%s] %-52s %s" % ("ok" if good else "FAIL", label, detail))

    n_open = cur.execute("SELECT COUNT(*) FROM line_events WHERE ended_at IS NULL").fetchone()[0]
    per_line = cur.execute("""SELECT line_id, COUNT(*) n FROM line_events
                              WHERE ended_at IS NULL GROUP BY line_id""").fetchall()
    line("one open line event per line", n_open == 5 and all(r[1] == 1 for r in per_line),
         "%d open across %d lines" % (n_open, len(per_line)))

    ov = cur.execute("""SELECT COUNT(*) FROM line_events a JOIN line_events b
                        ON a.line_id=b.line_id AND a.id<b.id
                        AND a.started_at < COALESCE(b.ended_at,'9999')
                        AND b.started_at < COALESCE(a.ended_at,'9999')""").fetchone()[0]
    line("no overlapping line events", ov == 0, "%d overlaps" % ov)

    bad_shift = cur.execute("SELECT COUNT(*) FROM hourly_runs WHERE shift NOT IN ('1','2','3')").fetchone()[0]
    line("shift is the string 1/2/3", bad_shift == 0, "%d bad" % bad_shift)

    tz = cur.execute("""SELECT COUNT(*) FROM hourly_runs WHERE recorded_at LIKE '%+%'
                        OR recorded_at LIKE '%Z' OR recorded_at LIKE '%,%'""").fetchone()[0]
    tz += cur.execute("""SELECT COUNT(*) FROM line_events WHERE started_at LIKE '%+%'
                        OR started_at LIKE '%Z'""").fetchone()[0]
    line("timestamps naive local ISO", tz == 0, "%d with an offset" % tz)

    bad_good = cur.execute("SELECT COUNT(*) FROM hourly_runs WHERE scrap_units>units_filled").fetchone()[0]
    line("scrap never exceeds units_filled", bad_good == 0, "%d rows" % bad_good)

    zeros = cur.execute("SELECT COUNT(*) FROM hourly_runs WHERE units_filled=0 AND notes IS NOT NULL").fetchone()[0]
    line("zero-production hours with a note", zeros >= 10, "%d rows" % zeros)

    sup = cur.execute("""SELECT COUNT(*) FROM hourly_runs s WHERE s.superseded=1
        AND s.override_reason IS NOT NULL AND EXISTS (
          SELECT 1 FROM hourly_runs r WHERE r.job_id=s.job_id AND r.period=s.period
          AND r.recorded_at=s.recorded_at AND COALESCE(r.superseded,0)=0)""").fetchone()[0]
    sup_all = cur.execute("SELECT COUNT(*) FROM hourly_runs WHERE superseded=1").fetchone()[0]
    line("superseded rows have a replacement", sup == sup_all and sup_all > 0,
         "%d superseded, %d replaced" % (sup_all, sup))

    miss = []
    for j in cur.execute("""SELECT * FROM jobs WHERE completion_flagged=0
                            AND completion_variance_reason IS NULL
                            AND status='completed'""").fetchall():
        _t, _a, _u, v = app_variance(cur, j)
        if v is not None and abs(v) > 0.05:
            miss.append((j["job_number"], round(v * 100, 1)))
    line("jobs outside 5% with no reason to refuse", 3 <= len(miss) <= 4,
         ", ".join("%s %+.1f%%" % m for m in miss) or "none")

    prod_days = set(map(tuple, cur.execute(
        """SELECT DISTINCT line_id, date(started_at) FROM line_events
           WHERE state='production'""").fetchall()))
    co_days = set(map(tuple, cur.execute(
        "SELECT DISTINCT line_id, date(started_at) FROM line_events "
        "WHERE state='changeover'").fetchall()))
    first_job_day = {tuple(r) for r in cur.execute(
        "SELECT line_id, MIN(date(scheduled_start)) FROM jobs GROUP BY line_id")}
    uncovered = []
    for (lid, d) in sorted(prod_days):
        if (lid, d) in first_job_day:
            continue
        day = datetime.fromisoformat(d).date()
        near = {(lid, (day + timedelta(days=k)).isoformat()) for k in (-1, 0, 1)}
        if not (near & co_days):
            uncovered.append((lid, d))

    missing_co = 0
    prev = {}
    for j in cur.execute("SELECT id, line_id, sku_id, scheduled_start FROM jobs "
                         "ORDER BY line_id, scheduled_start").fetchall():
        p = prev.get(j["line_id"])
        if p is not None and p["sku_id"] != j["sku_id"]:
            n = cur.execute("SELECT COUNT(*) FROM co_events WHERE to_job_id=?",
                            (j["id"],)).fetchone()[0]
            if not n:
                missing_co += 1
        prev[j["line_id"]] = j
    line("a changeover between every pair of jobs", missing_co == 0, "%d missing" % missing_co)
    line("a changeover on every production line-day", not uncovered,
         "%d of %d line-days without one" % (len(uncovered), len(prod_days)))

    steps = cur.execute("""SELECT COUNT(*) FROM co_events e WHERE NOT EXISTS (
                           SELECT 1 FROM co_event_steps s WHERE s.event_id=e.id)""").fetchone()[0]
    line("every changeover has step actuals", steps == 0, "%d without" % steps)

    missing_pairs = []
    for lid, pn in GAPS:
        sid = gaps_with_ids[pn]
        n = cur.execute("SELECT COUNT(*) FROM line_sku_rates WHERE line_id=? AND sku_id=?",
                        (lid, sid)).fetchone()[0]
        if n:
            missing_pairs.append((lid, pn))
    total_pairs = cur.execute("SELECT COUNT(*) FROM line_sku_rates").fetchone()[0]
    line("exactly two rate gaps, both empty", not missing_pairs and total_pairs == 8,
         "%d rate rows" % total_pairs)

    open_on_gap = cur.execute("""SELECT COUNT(*) FROM jobs WHERE status IN ('running','scheduled')
                                  AND (line_id, sku_id) IN (%s)""" %
                              ",".join("(%d,%d)" % (l, gaps_with_ids[p]) for l, p in GAPS)).fetchone()[0]
    line("one open job sits on a gap pair", open_on_gap == 1, "%d open" % open_on_gap)

    states = {r[0]: r[1] for r in cur.execute(
        "SELECT state, COUNT(*) FROM line_events WHERE ended_at IS NULL GROUP BY state")}
    line("tiles: two production, one lunch, idle",
         states.get("production", 0) == 2 and states.get("lunch", 0) == 1
         and states.get("idle", 0) >= 1, str(states))

    n_runs = cur.execute("SELECT COUNT(*) FROM hourly_runs").fetchone()[0]
    line("hourly_runs in the 6000-9000 band", 6000 <= n_runs <= 9000, str(n_runs))
    n_ev = cur.execute("SELECT COUNT(*) FROM line_events").fetchone()[0]
    line("line_events in the 2000-4000 band", 2000 <= n_ev <= 4000, str(n_ev))
    n_jobs = cur.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    line("about 500 jobs", 420 <= n_jobs <= 620, str(n_jobs))

    days = cur.execute("SELECT MIN(recorded_at), MAX(recorded_at) FROM hourly_runs").fetchone()
    span = (datetime.fromisoformat(days[1][:10]) - datetime.fromisoformat(days[0][:10])).days
    line("90 consecutive days covered", span >= 87, "%s .. %s (%d days)"
         % (days[0][:10], days[1][:10], span))
    return ok


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/mnt/lake/myarra.db")
    ap.add_argument("--client-dir", default="/home/jeeves/Client-Demo")
    ap.add_argument("--now", default=None, help="override the clock, ISO local")
    ap.add_argument("--no-backup", action="store_true")
    ap.add_argument("--init-schema", action="store_true")
    args = ap.parse_args()

    now = datetime.fromisoformat(args.now) if args.now else datetime.now()
    now = now.replace(second=0, microsecond=0)

    if not os.path.exists(args.db):
        if not args.init_schema:
            print("DB NOT FOUND: %s" % args.db)
            return 2
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if not cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='hourly_runs'").fetchone():
        if not args.init_schema:
            print("SCHEMA MISSING in %s. Apply tools/schema.sql first." % args.db)
            return 2
        with open(os.path.join(args.client_dir, "tools", "schema.sql"), encoding="utf-8") as fh:
            conn.executescript(fh.read())
        conn.commit()
        print("schema applied from tools/schema.sql")

    if not args.no_backup:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        bak = os.path.abspath("%s.bak-%s" % (args.db, stamp))
        dst = sqlite3.connect(bak)
        with dst:
            conn.backup(dst)
        dst.close()
        print("backup: %s" % bak)

    ref = load_reference(args.client_dir)
    rng = random.Random(SEED)

    # delete only the rows this script owns
    cur.execute("DELETE FROM downtime_events WHERE run_id IN (SELECT id FROM hourly_runs WHERE source=?)", (SOURCE,))
    cur.execute("DELETE FROM co_event_steps WHERE event_id IN (SELECT id FROM co_events WHERE source=?)", (SOURCE,))
    cur.execute("DELETE FROM co_event_changes WHERE event_id IN (SELECT id FROM co_events WHERE source=?)", (SOURCE,))
    cur.execute("DELETE FROM co_events WHERE source=?", (SOURCE,))
    cur.execute("DELETE FROM line_events WHERE source=?", (SOURCE,))
    cur.execute("DELETE FROM hourly_runs WHERE source=?", (SOURCE,))
    cur.execute("DELETE FROM jobs WHERE job_number GLOB ?", (JOB_GLOB,))
    conn.commit()

    hist = build_jobs(rng, ref, now.date())
    todays = build_today(rng, ref, now)

    def overlaps(a, b):
        return a["window_start"] < b["window_end"] and b["window_start"] < a["window_end"]

    keep = []
    for j in hist:
        clash = [t for t in todays if t["line_id"] == j["line_id"] and overlaps(j, t)]
        if not clash:
            keep.append(j)
    jobs = keep + todays
    done = [j["number"] for j in jobs if j["status"] == "completed"]
    OUTLIERS = dict(zip(rng.sample(done, 4), [-0.22, -0.14, -0.11, 0.12]))
    jobs.sort(key=lambda j: (j["line_id"], j["window_start"]))

    # ---- master data through the onboarding import route
    sys.path.insert(0, args.client_dir)
    from myarr_v2 import onboarding  # noqa: E402

    settings = [[r["key"], r["value"], r["description"]] for r in ref["settings"]]
    settings.append(["job_variance_tolerance", "0.05",
                     "Fraction off target that demands a completion reason"])
    bundle = {
        "settings": csv_text(["key", "value", "description"], settings),
        "component_types": csv_text(["name", "is_serial", "default_swap_min"],
                                    [[r["name"], r["is_serial"], r["default_swap_min"]]
                                     for r in ref["component_types"]]),
        "lines": csv_text(["id", "name", "format_type"],
                          [[r["id"], r["name"], r["format_type"]] for r in ref["lines"]]),
        "skus": csv_text(["part_number", "description", "case_pack", "active"],
                         [[r["part_number"], r["description"], r["case_pack"], r["active"]]
                          for r in ref["skus"]]),
        "sku_bom": csv_text(["sku_part_number", "component_name", "component_value"],
                            [[r["sku_part_number"], r["component_name"], r["component_value"]]
                             for r in ref["sku_bom"]]),
        "line_sku_rates": csv_text(["line_id", "sku_part_number", "ideal_rate"],
                                   [[r["line_id"], r["sku_part_number"], r["ideal_rate"]]
                                    for r in ref["line_sku_rates"]
                                    if (int(r["line_id"]), r["sku_part_number"]) not in GAPS]),
        "co_procedures": csv_text(["line_id", "from_sku_part_number", "to_sku_part_number",
                                   "name", "aggregate_standard_min"],
                                  [[r["line_id"], r["from_sku_part_number"],
                                    r["to_sku_part_number"], r["name"],
                                    r["aggregate_standard_min"]]
                                   for r in ref["co_procedures"]]),
        "co_steps": csv_text(["line_id", "from_sku_part_number", "to_sku_part_number", "seq",
                              "step_name", "station", "standard_min"],
                             [[r["line_id"], r["from_sku_part_number"],
                               r["to_sku_part_number"], r["seq"], r["step_name"],
                               r["station"], r["standard_min"]] for r in ref["co_steps"]]),
        "jobs": csv_text(["job_number", "sku_part_number", "line_id", "target_quantity",
                          "scheduled_start", "scheduled_end"],
                         [[j["number"], j["sku"], j["line_id"], 1,
                           iso(j["window_start"]), iso(j["window_end"])] for j in jobs]),
        "users": csv_text(["name", "role", "line_id", "telegram_id", "active"], line_leads()),
    }

    for name in onboarding.INGEST_ORDER:
        if name not in bundle:
            continue
        res = onboarding.ingest_template(conn, name, _Upload(bundle[name]))
        print("ingest %-15s uploaded %4d  ok %4d  failed %d"
              % (name, res["uploaded"], res["succeeded"], res["failed"]))
        for e in res["errors"][:5]:
            print("    line %s: %s" % (e["line"], e["message"]))

    removed = 0
    ids = {r["part_number"]: r["id"] for r in cur.execute("SELECT id, part_number FROM skus")}
    for lid, pn in GAPS:
        if pn in ids:
            cur.execute("DELETE FROM line_sku_rates WHERE line_id=? AND sku_id=?", (lid, ids[pn]))
            removed += cur.rowcount
    conn.commit()
    if removed:
        print("removed %d rate row(s) that had been loaded for the gap pairs" % removed)

    leads = {}
    for r in cur.execute("SELECT id, line_id, role FROM users WHERE line_id IS NOT NULL ORDER BY id"):
        if r["role"] in ("Lead", "Operator") and r["line_id"] not in leads:
            leads[r["line_id"]] = r["id"]
    known = {r["job_number"]: r["id"] for r in cur.execute(
        "SELECT id, job_number FROM jobs WHERE job_number GLOB ?", (JOB_GLOB,))}
    for j in jobs:
        j["sku_id"] = ids[j["sku"]]
        j["id"] = known[j["number"]]

    # ---- phase B: history
    w = Writer(cur, now, leads, rng)
    by_line = {}
    for j in jobs:
        by_line.setdefault(j["line_id"], []).append(j)
    for lid in sorted(by_line):
        build_line_history(w, lid, sorted(by_line[lid], key=lambda j: j["window_start"]))
    conn.commit()

    # ---- runs, then the target each job implies
    for j in jobs:
        total = w.job_runs(j, ref["shift_start"])
        window_min = (j["window_end"] - j["window_start"]).total_seconds() / 60.0
        eff_end = min(j["window_end"], now) if j["status"] == "running" else j["window_end"]
        allowed = max(1.0, window_min - off_minutes_in(j["window_start"], eff_end, j["offs"]))
        if j["number"] in OUTLIERS:
            v = OUTLIERS[j["number"]]
        else:
            v = rng.uniform(-0.038, 0.038)
        target = int(round((total / (1.0 + v)) * window_min / allowed))
        cur.execute("""UPDATE jobs SET target_quantity=?, status=?, actual_start=?,
                       actual_end=?, completion_variance_reason=NULL, completion_flagged=0
                       WHERE id=?""",
                    (max(1, target), j["status"], iso(j["window_start"]),
                     None if j["status"] == "running" else iso(eff_end), j["id"]))
    conn.commit()

    # ---- a few re-entered hours
    picks = cur.execute("""SELECT id, job_id, line_id, sku_id, shift, period, recorded_at,
                                  units_filled, duration_min, user_id
                           FROM hourly_runs WHERE source=? AND units_filled>0
                           ORDER BY id""", (SOURCE,)).fetchall()
    step = max(1, len(picks) // 14)
    for r in picks[::step][:14]:
        cur.execute("""INSERT INTO hourly_runs
                       (job_id,line_id,sku_id,shift,period,phase,recorded_at,units_filled,
                        scrap_units,duration_min,user_id,notes,flagged,superseded,
                        override_reason,source)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (r["job_id"], r["line_id"], r["sku_id"], r["shift"], r["period"], "run",
                     r["recorded_at"], int(r["units_filled"] * rng.uniform(0.55, 0.85)), 0,
                     r["duration_min"], r["user_id"], "entry withdrawn, see the replacement row",
                     0, 1,
                     rng.choice(["Keyed the case count instead of the unit count",
                                 "Re-entered: operator read the pallet, not the line",
                                 "Wrong hour: this count belonged to the next period"]),
                     SOURCE))
    conn.commit()

    print()
    print("window %s .. %s, generated at %s"
          % ((now - timedelta(days=DAYS - 1)).date(), now.date(), now.strftime("%H:%M")))
    print("jobs %d   changeovers %d   runs %d   line events %d"
          % (len(jobs), w.co, w.runs, w.events))
    print()
    print("row counts")
    for t in ("settings", "component_types", "lines", "skus", "sku_bom", "line_sku_rates",
              "co_procedures_v2", "co_steps_v2", "users", "jobs", "hourly_runs",
              "line_events", "downtime_events", "co_events", "co_event_steps",
              "co_event_changes"):
        print("  %-18s %6d" % (t, cur.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]))

    print()
    print("the two rate gaps")
    for lid, pn in GAPS:
        sid = ids[pn]
        print("  line_id %d  sku_id %d  %s  %s"
              % (lid, sid, pn,
                 cur.execute("SELECT description FROM skus WHERE id=?", (sid,)).fetchone()[0]))
        for o in cur.execute("""SELECT job_number, status FROM jobs
                                WHERE line_id=? AND sku_id=? AND status IN ('running','scheduled')""",
                             (lid, sid)):
            print("      open job %s (%s)" % (o["job_number"], o["status"]))

    print()
    print("floor tiles now")
    for r in cur.execute("""SELECT line_id, state, started_at, job_id FROM line_events
                            WHERE ended_at IS NULL ORDER BY line_id"""):
        print("  line %d  %-10s since %s  job %s"
              % (r["line_id"], r["state"], r["started_at"], r["job_id"] or "-"))

    good = verify(cur, ids, ref["shift_start"])
    conn.close()
    print()
    print("RESULT: %s" % ("all checks passed" if good else "see FAIL lines above"))
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
