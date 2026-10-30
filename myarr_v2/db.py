"""
Myarra Database Module
Handles all SQLite connections and schema initialization.
"""
import sqlite3

DB_PATH = "/mnt/lake/metrics.db"

def get_db_connection():
    """Returns a SQLite connection with row factory enabled for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Creates the necessary tables if they don't exist (idempotent)."""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Jobs Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_number TEXT UNIQUE NOT NULL,
            customer_id INTEGER,
            sku_id INTEGER,
            line_id INTEGER,
            target_quantity INTEGER,
            status TEXT DEFAULT 'scheduled'
        )
    ''')
    
    # Hourly Runs Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS hourly_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER REFERENCES jobs(id),
            line_id INTEGER,
            shift TEXT,
            period TEXT,
            phase TEXT,
            recorded_at TEXT,
            bottles_filled INTEGER,
            operator TEXT,
            raw_text TEXT
        )
    ''')
    
    # Downtime Events Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS downtime_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER REFERENCES hourly_runs(id),
            station TEXT,
            reason TEXT,
            minutes REAL,
            note TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized.")

if __name__ == "__main__":
    init_db()

import csv
import io

def ingest_csv(file_stream, table_name):
    """
    Reads a CSV file stream and inserts rows into the specified table.
    Assumes the CSV headers match the database column names exactly.
    """
    # Read the file stream as text
    stream = io.StringIO(file_stream.stream.read().decode("UTF8"), newline=None)
    reader = csv.DictReader(stream)
    
    conn = get_db_connection()
    c = conn.cursor()
    
    success_count = 0
    try:
        for row in reader:
            # Build the dynamic SQL query
            columns = ', '.join(row.keys())
            placeholders = ', '.join(['?'] * len(row))
            sql = f"INSERT OR REPLACE INTO {table_name} ({columns}) VALUES ({placeholders})"
            
            c.execute(sql, list(row.values()))
            success_count += 1
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error ingesting {table_name}: {e}")
        return 0
    finally:
        conn.close()
        
    return success_count

def init_users_table():
    """Creates the users table for Telegram/UI authentication."""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Users Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            role TEXT DEFAULT 'Operator',
            line_id INTEGER REFERENCES lines(id),
            telegram_id TEXT UNIQUE,
            active INTEGER DEFAULT 1
        )
    ''')
    
    # Link hourly runs and changeovers to a specific user
    try:
        c.execute("ALTER TABLE hourly_runs ADD COLUMN user_id INTEGER REFERENCES users(id)")
        c.execute("ALTER TABLE co_events ADD COLUMN user_id INTEGER REFERENCES users(id)")
    except sqlite3.OperationalError:
        pass # Columns already exist
        
    conn.commit()
    conn.close()
    print("Users table initialized.")

if __name__ == "__main__":
    init_db()
    init_users_table()
