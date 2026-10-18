"""Hash mat khau (scrypt), phien dang nhap va phan quyen."""
import base64
import hashlib
import hmac
import os
import sqlite3
from typing import Optional

from fastapi import Depends, HTTPException, Request

from app import config
from htv_sso_fastapi import is_sso_session, sso_session_valid
from app.db import db_session, get_db

_N, _R, _P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return "scrypt${}${}${}${}${}".format(
        _N, _R, _P, base64.b64encode(salt).decode(), base64.b64encode(dk).decode()
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, dk_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(dk_b64)
        dk = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


class LoginRequired(Exception):
    def __init__(self, change_password: bool = False):
        self.change_password = change_password


def effective_roles(conn: sqlite3.Connection, row: sqlite3.Row) -> set[str]:
    roles = {r["role"] for r in conn.execute(
        "SELECT role FROM user_roles WHERE username = ?", (row["username"],))}
    if row["ds_vai_tro"] in config.BAN_PHU_TRACH_ROLES:
        roles.add("ban_phu_trach")
    return roles


def load_user(conn: sqlite3.Connection, username: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM users WHERE username = ? AND active = 1", (username,)).fetchone()
    if not row:
        return None
    user = dict(row)
    user["roles"] = effective_roles(conn, row)
    user["display_name"] = row["full_name"] or row["username"]
    return user


def resolve_sso_user(username: str) -> Optional[str]:
    """Username trong token SSO -> username local (bang users dung chung). None neu khong co / bi khoa."""
    with db_session() as conn:
        for where in ("username = ?", "username = ? COLLATE NOCASE"):  # uu tien khop chinh xac
            rows = conn.execute(f"SELECT username FROM users WHERE {where} AND active = 1", (username,)).fetchall()
            if len(rows) == 1:
                return rows[0]["username"]
    return None


def current_user(request: Request, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    username = request.session.get("u")
    user = load_user(conn, username) if username else None
    if not user:
        raise LoginRequired()
    if not sso_session_valid(request):  # da dang xuat o Dashboard SSO (SLO)
        request.session.clear()
        raise LoginRequired()
    # Phien SSO khong dung mat khau local nen khong ep doi mat khau
    if user["must_change_pw"] and not is_sso_session(request) and request.url.path not in ("/password", "/logout"):
        raise LoginRequired(change_password=True)
    return user


def has_role(user: dict, *roles: str) -> bool:
    return "admin" in user["roles"] or bool(user["roles"] & set(roles))


def require_roles(*roles: str):
    def dep(user: dict = Depends(current_user)) -> dict:
        if not has_role(user, *roles):
            raise HTTPException(status_code=403, detail="Bạn không có quyền thực hiện chức năng này")
        return user
    return dep
