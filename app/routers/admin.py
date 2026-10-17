"""Quan tri: gan vai tro, dat lai mat khau, cau hinh storage."""
import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app import config
from app.db import get_db, get_settings, set_setting
from app.security import hash_password, require_roles
from app.services.importer import import_users_csv
from app.services.storage import get_storage
from app.web import render

router = APIRouter(prefix="/admin")
admin_only = require_roles()  # chi admin (has_role luon cho phep admin)

STORAGE_KEYS = ["storage_type", "ftp_host", "ftp_port", "ftp_user", "ftp_pass", "ftp_base_dir",
                "create_proxy"]


@router.get("/users")
def users_page(request: Request, q: str = "", user: dict = Depends(admin_only),
               conn: sqlite3.Connection = Depends(get_db), msg: str = ""):
    sql, args = "SELECT * FROM users", []
    if q.strip():
        sql += " WHERE username LIKE ? OR full_name LIKE ? OR ds_ban LIKE ?"
        args = [f"%{q.strip()}%"] * 3
    rows = conn.execute(sql + " ORDER BY ds_ban, username LIMIT 300", args).fetchall()
    roles: dict[str, set] = {}
    for r in conn.execute("SELECT username, role FROM user_roles"):
        roles.setdefault(r["username"], set()).add(r["role"])
    users = [dict(r, roles=roles.get(r["username"], set()),
                  is_bpt=r["ds_vai_tro"] in config.BAN_PHU_TRACH_ROLES) for r in rows]
    return render(request, "admin_users.html", user, users=users, q=q, app_roles=config.APP_ROLES,
                  total=conn.execute("SELECT COUNT(*) FROM users").fetchone()[0], msg=msg)


@router.post("/users/{username}/roles")
async def set_roles(username: str, request: Request, user: dict = Depends(admin_only),
                    conn: sqlite3.Connection = Depends(get_db)):
    if not conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        raise HTTPException(404, "Không tìm thấy user")
    form = await request.form()
    chosen = {r for r in form.getlist("role") if r in config.APP_ROLES}
    if username == user["username"]:
        chosen.add("admin")  # khong tu go quyen admin cua chinh minh
    conn.execute("DELETE FROM user_roles WHERE username = ?", (username,))
    conn.executemany("INSERT INTO user_roles(username, role) VALUES (?, ?)",
                     [(username, r) for r in chosen])
    return RedirectResponse(f"/admin/users?q={username}&msg=Đã lưu vai trò cho {username}", status_code=303)


@router.post("/users/{username}/reset-password")
def reset_password(username: str, user: dict = Depends(admin_only),
                   conn: sqlite3.Connection = Depends(get_db)):
    cur = conn.execute("UPDATE users SET pw_hash = ?, must_change_pw = ? WHERE username = ?",
                       (hash_password(config.DEFAULT_PASSWORD), int(config.FORCE_PASSWORD_CHANGE), username))
    if cur.rowcount == 0:
        raise HTTPException(404, "Không tìm thấy user")
    return RedirectResponse(f"/admin/users?q={username}&msg=Đã đặt lại mật khẩu mặc định cho {username}",
                            status_code=303)


@router.post("/users/{username}/active")
def toggle_active(username: str, user: dict = Depends(admin_only),
                  conn: sqlite3.Connection = Depends(get_db)):
    if username == user["username"]:
        raise HTTPException(400, "Không thể khóa chính mình")
    conn.execute("UPDATE users SET active = 1 - active WHERE username = ?", (username,))
    return RedirectResponse(f"/admin/users?q={username}", status_code=303)


@router.post("/users/import")
def reimport(user: dict = Depends(admin_only), conn: sqlite3.Connection = Depends(get_db)):
    result = import_users_csv(conn)
    return RedirectResponse(
        f"/admin/users?msg=Import CSV: tạo mới {result['created']}, cập nhật {result['updated']}", status_code=303)


@router.get("/settings")
def settings_page(request: Request, user: dict = Depends(admin_only),
                  conn: sqlite3.Connection = Depends(get_db), msg: str = ""):
    return render(request, "admin_settings.html", user, s=get_settings(conn), msg=msg)


@router.post("/settings")
def save_settings(request: Request, storage_type: str = Form(...), ftp_host: str = Form(""),
                  ftp_port: str = Form("21"), ftp_user: str = Form(""), ftp_pass: str = Form(""),
                  ftp_base_dir: str = Form("/"), create_proxy: str = Form(""),
                  action: str = Form("save"),
                  user: dict = Depends(admin_only), conn: sqlite3.Connection = Depends(get_db)):
    if storage_type not in ("ftp", "local"):
        raise HTTPException(400, "Loại storage không hợp lệ")
    values = dict(storage_type=storage_type, ftp_host=ftp_host.strip(), ftp_port=ftp_port.strip() or "21",
                  ftp_user=ftp_user.strip(), ftp_pass=ftp_pass, ftp_base_dir=ftp_base_dir.strip() or "/",
                  create_proxy="1" if create_proxy else "0")
    if action == "test":
        try:
            storage = get_storage(values)
            storage.exists("__ping__")
            return render(request, "admin_settings.html", user, s=values, msg="Kết nối storage thành công")
        except Exception as exc:
            return render(request, "admin_settings.html", user, s=values, error=f"Kết nối thất bại: {exc}")
    for k in STORAGE_KEYS:
        set_setting(conn, k, values[k])
    return RedirectResponse("/admin/settings?msg=Đã lưu cấu hình storage", status_code=303)
