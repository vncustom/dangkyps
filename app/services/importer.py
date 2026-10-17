"""Import danh sach user tu CSV."""
import csv
import sqlite3
from pathlib import Path

from app import config
from app.security import hash_password


def ensure_admins(conn: sqlite3.Connection) -> list[str]:
    """Cap quyen admin cho cac user trong config.ADMIN_USERS (khong phan biet hoa thuong). Tra ve danh sach da cap."""
    granted = []
    for name in config.ADMIN_USERS:
        row = conn.execute("SELECT username FROM users WHERE lower(username) = lower(?)", (name,)).fetchone()
        if row:
            conn.execute("INSERT OR IGNORE INTO user_roles(username, role) VALUES (?, 'admin')", (row["username"],))
            granted.append(row["username"])
    return granted


def import_users_csv(conn: sqlite3.Connection, csv_path: Path = None,
                     default_password: str = None, reset_existing: bool = False) -> dict:
    """Nap CSV vao bang users. Mat khau mac dinh duoc hash (khong luu plaintext).

    User da ton tai: cap nhat thong tin, giu nguyen mat khau (tru khi reset_existing).
    """
    csv_path = Path(csv_path or config.USERS_CSV)
    default_password = default_password or config.DEFAULT_PASSWORD
    pw_hash = hash_password(default_password)  # cung hash cho moi user mac dinh -> nhanh
    created = updated = 0
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            username = (row.get("username") or "").strip()
            if not username:
                continue
            existing = conn.execute(
                "SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
            fields = (
                (row.get("full_name") or "").strip(),
                (row.get("ds_ban") or "").strip(),
                (row.get("ds_phong") or "").strip(),
                (row.get("ds_to") or "").strip(),
                (row.get("ds_vai_tro") or "").strip(),
                (row.get("JobTitles") or "").strip(),
                (row.get("Email") or "").strip(),
                (row.get("phone") or "").strip(),
            )
            if existing:
                conn.execute(
                    "UPDATE users SET full_name=?, ds_ban=?, ds_phong=?, ds_to=?, ds_vai_tro=?,"
                    " job_title=?, email=?, phone=? WHERE username=?", fields + (username,))
                if reset_existing:
                    conn.execute("UPDATE users SET pw_hash=?, must_change_pw=? WHERE username=?",
                                 (pw_hash, int(config.FORCE_PASSWORD_CHANGE), username))
                updated += 1
            else:
                conn.execute(
                    "INSERT INTO users(username, full_name, ds_ban, ds_phong, ds_to, ds_vai_tro,"
                    " job_title, email, phone, pw_hash, must_change_pw)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (username,) + fields + (pw_hash, int(config.FORCE_PASSWORD_CHANGE)))
                created += 1
    ensure_admins(conn)
    return {"created": created, "updated": updated}
