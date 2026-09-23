"""SQLite repository for patients, medicines, gait readings and alerts."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.security import hash_password

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    display_name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    age INTEGER NOT NULL,
    pharmacist TEXT NOT NULL,
    consent_share INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS medicines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    name TEXT NOT NULL,
    dose TEXT NOT NULL,
    start_date TEXT NOT NULL,
    falls_risk INTEGER NOT NULL,
    drug_class TEXT
);
CREATE TABLE IF NOT EXISTS gait_readings (
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    day TEXT NOT NULL,
    cadence_spm REAL NOT NULL,
    step_variability_pct REAL NOT NULL,
    steps INTEGER NOT NULL,
    night_walks INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (patient_id, day)
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    medicine_id INTEGER REFERENCES medicines(id),
    risk TEXT NOT NULL,
    score REAL NOT NULL,
    reasons TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN',
    created_at TEXT NOT NULL,
    reviewed_by TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT NOT NULL
);
"""


class Database:
    """Thread-safe wrapper around one SQLite connection."""

    def __init__(self, path: str = ":memory:") -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Run one write statement and commit it."""
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        """Run a read query and return plain dictionaries."""
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def ping(self) -> bool:
        """Return True when the database answers a trivial query."""
        try:
            self.query("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    def audit(self, actor: str, action: str, detail: dict) -> None:
        """Append an entry to the audit log."""
        self.execute(
            "INSERT INTO audit_log (at, actor, action, detail) VALUES (?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), actor, action,
             json.dumps(detail)))


DEMO_USERS = (
    ("daniel", "Pharmacist!2026", "pharmacist", "Daniel N"),
    ("priya", "Carer!2026", "carer", "Priya C"),
)


def seed_demo_data(db: Database) -> None:
    """Load illustrative demo data that matches the SteadyRx prototype.

    The people are fictional. Margaret has a new opioid and a clear drop in
    walking steadiness so the risk queue has a realistic HIGH alert to show.
    """
    if db.query("SELECT username FROM users LIMIT 1"):
        return
    for username, password, role, name in DEMO_USERS:
        db.execute("INSERT INTO users VALUES (?,?,?,?)",
                   (username, hash_password(password), role, name))
    db.execute("INSERT INTO patients (name, age, pharmacist) VALUES (?,?,?)",
               ("Margaret Collins", 78, "daniel"))
    db.execute("INSERT INTO patients (name, age, pharmacist) VALUES (?,?,?)",
               ("Joan K", 71, "daniel"))
    change = date.today() - timedelta(days=9)
    for offset in range(-14, 9):
        day = change + timedelta(days=offset)
        after = offset >= 0
        db.execute(
            "INSERT INTO gait_readings VALUES (?,?,?,?,?,?)",
            (1, day.isoformat(), 94.0 if after else 104.0,
             5.9 if after else 5.0, 2900 if after else 3400,
             1 if after and offset % 3 == 0 else 0))
        db.execute(
            "INSERT INTO gait_readings VALUES (?,?,?,?,?,?)",
            (2, day.isoformat(), 101.0, 4.8, 4100, 0))
