"""User accounts and the query log, stored in SQLite beside the index.

Two rules from the owner, 2026-11-17: deactivating a user never removes their
history; deleting a user's log is a separate, deliberate act. Both remain
visible in the listing so neither happens by accident.
"""
import contextlib
import csv
import datetime
import hashlib
import hmac
import io
import os
import sqlite3

DB_PATH = os.environ.get("ARKIV_USERS_DB",
                        "/mnt/lake/arkiv_users.db")
ITERATIONS = 200000

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL DEFAULT 'member',
    pin_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    user_id INTEGER,
    user_name TEXT,
    matter TEXT,
    question TEXT,
    refused INTEGER NOT NULL DEFAULT 0,
    sources INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_queries_user ON queries(user_id);
CREATE INDEX IF NOT EXISTS idx_queries_ts ON queries(ts);
"""


@contextlib.contextmanager
def conn():
    directory = os.path.dirname(DB_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.executescript(_SCHEMA)
    try:
        yield c
        c.commit()
    finally:
        c.close()


def hash_pin(pin, salt=None):
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", str(pin).encode("utf-8"),
                                 bytes.fromhex(salt), ITERATIONS)
    return digest.hex(), salt


def count_users():
    with conn() as c:
        return c.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def create_user(name, pin, role="member"):
    digest, salt = hash_pin(pin)
    with conn() as c:
        c.execute("INSERT INTO users (name, role, pin_hash, salt, active, created_at)"
                  " VALUES (?,?,?,?,1,?)",
                  (name, role, digest, salt, datetime.datetime.now().isoformat()))


def list_users():
    with conn() as c:
        rows = c.execute("SELECT u.id, u.name, u.role, u.active, u.created_at,"
                         " (SELECT COUNT(*) FROM queries q WHERE q.user_id = u.id) AS q_count"
                         " FROM users u ORDER BY u.name").fetchall()
        return [dict(r) for r in rows]


def set_active(user_id, active):
    with conn() as c:
        c.execute("UPDATE users SET active = ? WHERE id = ?",
                  (1 if active else 0, user_id))


def set_pin(user_id, pin):
    digest, salt = hash_pin(pin)
    with conn() as c:
        c.execute("UPDATE users SET pin_hash = ?, salt = ? WHERE id = ?",
                  (digest, salt, user_id))


def delete_log(user_id):
    with conn() as c:
        return c.execute("DELETE FROM queries WHERE user_id = ?", (user_id,)).rowcount


def verify(name, pin):
    with conn() as c:
        row = c.execute("SELECT * FROM users WHERE name = ? AND active = 1",
                        (name,)).fetchone()
    if not row:
        return None
    digest, _ = hash_pin(pin, row["salt"])
    if hmac.compare_digest(digest, row["pin_hash"]):
        return {"id": row["id"], "name": row["name"], "role": row["role"]}
    return None


def log_query(user, matter, question, refused, sources):
    user = user or {}
    with conn() as c:
        c.execute("INSERT INTO queries (ts, user_id, user_name, matter, question, refused, sources)"
                  " VALUES (?,?,?,?,?,?,?)",
                  (datetime.datetime.now().isoformat(), user.get("id"),
                   user.get("name"), matter, question, 1 if refused else 0, sources))


def recent(limit=20):
    with conn() as c:
        rows = c.execute("SELECT * FROM queries ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


def export_csv(user_id=None):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["timestamp", "user", "user_id", "matter", "question", "refused", "sources"])
    with conn() as c:
        if user_id:
            rows = c.execute("SELECT * FROM queries WHERE user_id = ? ORDER BY id", (user_id,))
        else:
            rows = c.execute("SELECT * FROM queries ORDER BY id")
        for r in rows:
            writer.writerow([r["ts"], r["user_name"], r["user_id"], r["matter"],
                             r["question"], r["refused"], r["sources"]])
    return buf.getvalue()


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4 and sys.argv[1] == "add":
        create_user(sys.argv[2], sys.argv[3],
                    sys.argv[4] if len(sys.argv) > 4 else "member")
        print("created user " + sys.argv[2])
    elif len(sys.argv) >= 2 and sys.argv[1] == "list":
        for u in list_users():
            print(str(u["id"]).rjust(3) + "  " + u["name"].ljust(20) +
                  u["role"].ljust(10) + ("active" if u["active"] else "inactive").ljust(10) +
                  str(u["q_count"]) + " queries")
    else:
        print("usage: users.py add <name> <pin> [role] | users.py list")
