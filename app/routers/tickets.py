"""Buoc 3: thu ky tao phieu DKPS va nap file da kiem duyet vao phieu."""
import sqlite3
from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app import config
from app.db import get_db, now_str
from app.security import require_roles
from app.services import domain
from app.web import render

router = APIRouter()
thu_ky = require_roles("thu_ky")

TICKET_SELECT = """
SELECT t.*, f.file_name, f.md5, f.duration_tc, f.size_bytes, f.thumb_path, f.status AS file_status
FROM tickets t LEFT JOIN files f ON f.file_id = t.file_id
"""


def _validate(assetform_id: str, kenh: str, ten: str, ngay: str, the_loai: str, nguon: str) -> list[str]:
    errors = []
    if not assetform_id.strip():
        errors.append("Chưa nhập AssetForm ID")
    if kenh not in config.KENH_SONG:
        errors.append("Kênh sóng không hợp lệ")
    if not ten.strip():
        errors.append("Chưa nhập tên chương trình")
    try:
        datetime.strptime(ngay, "%Y-%m-%d")
    except ValueError:
        errors.append("Ngày phát sóng không hợp lệ")
    if the_loai not in config.THE_LOAI:
        errors.append("Chưa chọn thể loại")
    if nguon not in config.NGUON_CUNG_CAP:
        errors.append("Chưa chọn nguồn cung cấp")
    return errors


def _form_ctx() -> dict:
    return dict(kenh_list=config.KENH_SONG, the_loai=config.THE_LOAI, nguon_list=config.NGUON_CUNG_CAP)


def _get_ticket(conn: sqlite3.Connection, so_phieu: int) -> dict:
    row = conn.execute(TICKET_SELECT + " WHERE t.so_phieu = ?", (so_phieu,)).fetchone()
    if not row:
        raise HTTPException(404, "Không tìm thấy phiếu")
    return dict(row)


@router.get("/tickets")
def ticket_list(request: Request, q: str = "", user: dict = Depends(thu_ky),
                conn: sqlite3.Connection = Depends(get_db)):
    sql, args = TICKET_SELECT, []
    if q.strip():
        like = f"%{q.strip()}%"
        sql += (" WHERE CAST(t.so_phieu AS TEXT) LIKE ? OR t.assetform_id LIKE ?"
                " OR t.ten_chuong_trinh LIKE ? OR f.file_name LIKE ?")
        args = [like] * 4
    rows = conn.execute(sql + " ORDER BY t.so_phieu DESC LIMIT 500", args).fetchall()
    return render(request, "ticket_list.html", user, tickets=[dict(r) for r in rows], q=q)


@router.get("/tickets/new")
def ticket_new(request: Request, user: dict = Depends(thu_ky)):
    return render(request, "ticket_form.html", user, t=None, today=date.today().isoformat(),
                  errors=[], **_form_ctx())


@router.post("/tickets/new")
def ticket_create(request: Request, assetform_id: str = Form(""), kenh: str = Form(""),
                  ten_chuong_trinh: str = Form(""), ngay_phat_song: str = Form(""),
                  the_loai: str = Form(""), nguon_cung_cap: str = Form(""), ghi_chu: str = Form(""),
                  user: dict = Depends(thu_ky), conn: sqlite3.Connection = Depends(get_db)):
    errors = _validate(assetform_id, kenh, ten_chuong_trinh, ngay_phat_song, the_loai, nguon_cung_cap)
    if errors:
        t = dict(assetform_id=assetform_id, kenh=kenh, ten_chuong_trinh=ten_chuong_trinh,
                 ngay_phat_song=ngay_phat_song, the_loai=the_loai, nguon_cung_cap=nguon_cung_cap,
                 ghi_chu=ghi_chu)
        return render(request, "ticket_form.html", user, status_code=400, t=t,
                      today=date.today().isoformat(), errors=errors, **_form_ctx())
    cur = conn.execute(
        "INSERT INTO tickets(assetform_id, kenh, ten_chuong_trinh, ngay_phat_song, the_loai,"
        " nguon_cung_cap, ghi_chu, created_by, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (assetform_id.strip(), kenh, ten_chuong_trinh.strip(), ngay_phat_song, the_loai,
         nguon_cung_cap, ghi_chu.strip(), user["username"], now_str()))
    return RedirectResponse(f"/tickets/{cur.lastrowid}", status_code=303)


@router.get("/tickets/{so_phieu}")
def ticket_detail(so_phieu: int, request: Request, user: dict = Depends(thu_ky),
                  conn: sqlite3.Connection = Depends(get_db)):
    t = _get_ticket(conn, so_phieu)
    approved = []
    if not t["file_id"]:
        approved = [f for f in domain.list_files(conn, where="f.status = 'ready'")
                    if f["review_state"] == "dat" and not f["so_phieu"]]
    return render(request, "ticket_form.html", user, t=t, errors=[], approved=approved,
                  file=domain.get_file(conn, t["file_id"]) if t["file_id"] else None,
                  today=date.today().isoformat(), **_form_ctx())


@router.post("/tickets/{so_phieu}/edit")
def ticket_edit(so_phieu: int, request: Request, assetform_id: str = Form(""), kenh: str = Form(""),
                ten_chuong_trinh: str = Form(""), ngay_phat_song: str = Form(""),
                the_loai: str = Form(""), nguon_cung_cap: str = Form(""), ghi_chu: str = Form(""),
                user: dict = Depends(thu_ky), conn: sqlite3.Connection = Depends(get_db)):
    t = _get_ticket(conn, so_phieu)
    errors = _validate(assetform_id, kenh, ten_chuong_trinh, ngay_phat_song, the_loai, nguon_cung_cap)
    if errors:
        t.update(assetform_id=assetform_id, kenh=kenh, ten_chuong_trinh=ten_chuong_trinh,
                 ngay_phat_song=ngay_phat_song, the_loai=the_loai, nguon_cung_cap=nguon_cung_cap,
                 ghi_chu=ghi_chu)
        return render(request, "ticket_form.html", user, status_code=400, t=t, errors=errors,
                      approved=[], file=domain.get_file(conn, t["file_id"]) if t["file_id"] else None,
                      today=date.today().isoformat(), **_form_ctx())
    conn.execute(
        "UPDATE tickets SET assetform_id=?, kenh=?, ten_chuong_trinh=?, ngay_phat_song=?,"
        " the_loai=?, nguon_cung_cap=?, ghi_chu=? WHERE so_phieu=?",
        (assetform_id.strip(), kenh, ten_chuong_trinh.strip(), ngay_phat_song, the_loai,
         nguon_cung_cap, ghi_chu.strip(), so_phieu))
    return RedirectResponse(f"/tickets/{so_phieu}", status_code=303)


@router.post("/tickets/{so_phieu}/attach")
def ticket_attach(so_phieu: int, file_id: int = Form(...), user: dict = Depends(thu_ky),
                  conn: sqlite3.Connection = Depends(get_db)):
    t = _get_ticket(conn, so_phieu)
    if t["file_id"]:
        raise HTTPException(400, "Phiếu đã có file, hãy bỏ file ra trước khi nạp file khác")
    f = domain.get_file(conn, file_id)
    if not f or f["status"] != "ready":
        raise HTTPException(404, "Không tìm thấy file")
    if f["review_state"] != "dat":
        raise HTTPException(400, "File chưa được kiểm duyệt Đạt")
    if f["so_phieu"]:
        raise HTTPException(400, f"File đã gắn vào phiếu {f['so_phieu']}")
    conn.execute("UPDATE tickets SET file_id = ? WHERE so_phieu = ?", (file_id, so_phieu))
    return RedirectResponse(f"/tickets/{so_phieu}", status_code=303)


@router.post("/tickets/{so_phieu}/detach")
def ticket_detach(so_phieu: int, user: dict = Depends(thu_ky),
                  conn: sqlite3.Connection = Depends(get_db)):
    _get_ticket(conn, so_phieu)
    conn.execute("UPDATE tickets SET file_id = NULL WHERE so_phieu = ?", (so_phieu,))
    return RedirectResponse(f"/tickets/{so_phieu}", status_code=303)
