"""SQLite: ket noi va schema."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from app import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    full_name TEXT NOT NULL DEFAULT '',
    ds_ban TEXT NOT NULL DEFAULT '',
    ds_phong TEXT NOT NULL DEFAULT '',
    ds_to TEXT NOT NULL DEFAULT '',
    ds_vai_tro TEXT NOT NULL DEFAULT '',
    job_title TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    pw_hash TEXT NOT NULL,
    must_change_pw INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS user_roles (
    username TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    role TEXT NOT NULL,
    PRIMARY KEY (username, role)
);

CREATE TABLE IF NOT EXISTS files (
    file_id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT NOT NULL,
    md5 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    duration_sec REAL NOT NULL DEFAULT 0,
    duration_tc TEXT NOT NULL DEFAULT '',
    fps REAL NOT NULL DEFAULT 25,
    width INTEGER NOT NULL DEFAULT 0,
    height INTEGER NOT NULL DEFAULT 0,
    codec TEXT NOT NULL DEFAULT '',
    unit TEXT NOT NULL DEFAULT '',
    storage_path TEXT NOT NULL DEFAULT '',
    proxy_path TEXT NOT NULL DEFAULT '',
    thumb_path TEXT NOT NULL DEFAULT '',
    uploaded_by TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    tech_checked_by TEXT NOT NULL DEFAULT '',
    tech_checked_at TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'processing',
    status_msg TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_files_md5 ON files(md5);

CREATE TABLE IF NOT EXISTS uploads (
    upload_id TEXT PRIMARY KEY,
    file_name TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    unit TEXT NOT NULL DEFAULT '',
    received INTEGER NOT NULL DEFAULT 0,
    username TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    file_id INTEGER NOT NULL REFERENCES files(file_id) ON DELETE CASCADE,
    reviewer_kind TEXT NOT NULL,          -- ban_phu_trach | bien_tap_vien
    reviewer TEXT NOT NULL DEFAULT '',
    result TEXT NOT NULL DEFAULT 'chua',  -- chua | dat | khong_dat
    comment TEXT NOT NULL DEFAULT '',
    reviewed_at TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (file_id, reviewer_kind)
);

CREATE TABLE IF NOT EXISTS tickets (
    so_phieu INTEGER PRIMARY KEY AUTOINCREMENT,
    assetform_id TEXT NOT NULL,
    kenh TEXT NOT NULL,
    ten_chuong_trinh TEXT NOT NULL,
    ngay_phat_song TEXT NOT NULL,
    the_loai TEXT NOT NULL,
    nguon_cung_cap TEXT NOT NULL,
    ghi_chu TEXT NOT NULL DEFAULT '',
    file_id INTEGER REFERENCES files(file_id),
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(config.DB_PATH), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_session():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_db():
    """FastAPI dependency."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _seed_sequence(conn: sqlite3.Connection, table: str, start: int) -> None:
    if start <= 1:
        return
    has_rows = conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
    has_seq = conn.execute("SELECT 1 FROM sqlite_sequence WHERE name = ?", (table,)).fetchone()
    if not has_rows and not has_seq:
        conn.execute("INSERT INTO sqlite_sequence(name, seq) VALUES (?, ?)", (table, start - 1))


def init_db() -> None:
    for d in (config.DATA_DIR, config.TMP_DIR, config.PROXY_DIR, config.THUMB_DIR):
        d.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        _seed_sequence(conn, "tickets", config.TICKET_START)
        _seed_sequence(conn, "files", config.FILE_ID_START)
        conn.commit()
    finally:
        conn.close()


# ---- settings -------------------------------------------------------------

def get_settings(conn: sqlite3.Connection) -> dict:
    values = dict(config.STORAGE_DEFAULTS)
    for row in conn.execute("SELECT key, value FROM settings"):
        values[row["key"]] = row["value"]
    return values


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
