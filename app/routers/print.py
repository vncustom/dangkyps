"""Buoc 4: in phieu phat song."""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request

from app import config
from app.db import get_db
from app.security import require_roles
from app.web import render

router = APIRouter()
thu_ky = require_roles("thu_ky")


def _name(conn: sqlite3.Connection, username: str) -> str:
    if not username:
        return ""
    row = conn.execute("SELECT full_name FROM users WHERE username = ?", (username,)).fetchone()
    return (row["full_name"] if row and row["full_name"] else username)


@router.get("/print/{so_phieu}")
def print_ticket(so_phieu: int, request: Request, user: dict = Depends(thu_ky),
                 conn: sqlite3.Connection = Depends(get_db)):
    t = conn.execute("SELECT * FROM tickets WHERE so_phieu = ?", (so_phieu,)).fetchone()
    if not t:
        raise HTTPException(404, "Không tìm thấy phiếu")
    f = conn.execute("SELECT * FROM files WHERE file_id = ?", (t["file_id"],)).fetchone() if t["file_id"] else None
    reviews = {}
    if f:
        for r in conn.execute("SELECT * FROM reviews WHERE file_id = ?", (f["file_id"],)):
            reviews[r["reviewer_kind"]] = {"name": _name(conn, r["reviewer"]), "at": r["reviewed_at"]}
    return render(request, "print.html", user, t=dict(t), f=dict(f) if f else None,
                  bp=reviews.get("ban_phu_trach"), btv=reviews.get("bien_tap_vien"),
                  tech={"name": _name(conn, f["tech_checked_by"]), "at": f["tech_checked_at"]} if f else None,
                  don_vi=config.THE_LOAI.get(t["the_loai"], t["the_loai"]), segment_rows=6)
