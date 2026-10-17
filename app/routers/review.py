"""Buoc 2: Ban phu trach va Bien tap vien duyet file."""
import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.db import get_db, now_str
from app.security import has_role, require_roles
from app.services import domain
from app.web import render

router = APIRouter()
reviewer = require_roles("ban_phu_trach", "bien_tap_vien")

KIND_LABELS = {"ban_phu_trach": "Ban phụ trách", "bien_tap_vien": "Biên tập viên"}


def allowed_kinds(user: dict, f: dict) -> list[str]:
    """Cac vai tro duyet user duoc phep thuc hien tren file f."""
    kinds = []
    is_admin = "admin" in user["roles"]
    if is_admin or ("ban_phu_trach" in user["roles"] and user["ds_ban"] == f["unit"]):
        kinds.append("ban_phu_trach")
    if is_admin or "bien_tap_vien" in user["roles"]:
        kinds.append("bien_tap_vien")
    return kinds


@router.get("/review")
def review_list(request: Request, show: str = "pending", user: dict = Depends(reviewer),
                conn: sqlite3.Connection = Depends(get_db)):
    files = [f for f in domain.list_files(conn, where="f.status = 'ready'")
             if allowed_kinds(user, f)]
    if show == "pending":
        files = [f for f in files if any(
            f["bp_result" if k == "ban_phu_trach" else "btv_result"] == "chua"
            for k in allowed_kinds(user, f))]
    elif show == "done":
        files = [f for f in files if f["review_state"] != "chua"]
    return render(request, "review_list.html", user, files=files, show=show)


@router.get("/review/{file_id}")
def review_detail(file_id: int, request: Request, user: dict = Depends(reviewer),
                  conn: sqlite3.Connection = Depends(get_db)):
    f = domain.get_file(conn, file_id)
    if not f or f["status"] != "ready":
        raise HTTPException(404, "Không tìm thấy file hoặc file chưa xử lý xong")
    kinds = allowed_kinds(user, f)
    if not kinds:
        raise HTTPException(403, "File không thuộc đơn vị của bạn")
    reviews = {r["reviewer_kind"]: dict(r) for r in conn.execute(
        "SELECT r.*, COALESCE(NULLIF(u.full_name, ''), r.reviewer) AS reviewer_name"
        " FROM reviews r LEFT JOIN users u ON u.username = r.reviewer WHERE r.file_id = ?", (file_id,))}
    tech = conn.execute("SELECT COALESCE(NULLIF(full_name, ''), username) AS n FROM users"
                        " WHERE username = ?", (f["tech_checked_by"],)).fetchone()
    return render(request, "review_detail.html", user, f=f, kinds=kinds, reviews=reviews,
                  kind_labels=KIND_LABELS, tech_name=tech["n"] if tech else f["tech_checked_by"],
                  locked=bool(f["so_phieu"]))


@router.post("/review/{file_id}")
def review_submit(file_id: int, kind: str = Form(...), result: str = Form(...),
                  comment: str = Form(""), user: dict = Depends(reviewer),
                  conn: sqlite3.Connection = Depends(get_db)):
    f = domain.get_file(conn, file_id)
    if not f or f["status"] != "ready":
        raise HTTPException(404, "Không tìm thấy file")
    if kind not in allowed_kinds(user, f):
        raise HTTPException(403, "Bạn không có quyền duyệt với vai trò này")
    if result not in ("chua", "dat", "khong_dat"):
        raise HTTPException(400, "Kết quả không hợp lệ")
    if f["so_phieu"]:
        raise HTTPException(400, f"File đã gắn vào phiếu {f['so_phieu']}, không thể đổi kết quả duyệt")
    if result == "khong_dat" and not comment.strip():
        raise HTTPException(400, "Vui lòng nhập nhận xét khi đánh giá Không đạt")
    reviewed_at = "" if result == "chua" else now_str()
    reviewer_name = "" if result == "chua" else user["username"]
    conn.execute(
        "UPDATE reviews SET reviewer = ?, result = ?, comment = ?, reviewed_at = ?"
        " WHERE file_id = ? AND reviewer_kind = ?",
        (reviewer_name, result, comment.strip(), reviewed_at, file_id, kind))
    return RedirectResponse(f"/review/{file_id}", status_code=303)
