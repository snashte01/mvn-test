import sqlite3
import os
import datetime

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH   = os.path.join(_BASE_DIR, 'db', 'audit.db')


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT    NOT NULL,
                action    TEXT    NOT NULL,
                target    TEXT,
                success   INTEGER,
                details   TEXT
            )
        """)
        conn.commit()


def log_action(action, target, success, details=''):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO audit_log (timestamp, action, target, success, details) "
            "VALUES (?,?,?,?,?)",
            (datetime.datetime.now().isoformat(), action, target,
             1 if success else 0, details),
        )
        conn.commit()
