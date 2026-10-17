"""Phat video / thumbnail (ho tro HTTP Range)."""
import re
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from app import config
from app.db import get_db, get_settings
from app.security import current_user
from app.services.storage import get_storage

router = APIRouter(prefix="/media")


def _file_row(conn: sqlite3.Connection, file_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM files WHERE file_id = ?", (file_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Không tìm thấy file")
    return row


@router.get("/{file_id}/thumb")
def thumb(file_id: int, user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    row = _file_row(conn, file_id)
    path = config.THUMB_DIR / row["thumb_path"] if row["thumb_path"] else None
    if not path or not path.exists():
        raise HTTPException(404, "Chưa có thumbnail")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "max-age=3600"})


@router.get("/{file_id}/proxy")
def proxy(file_id: int, user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    row = _file_row(conn, file_id)
    path = config.PROXY_DIR / row["proxy_path"] if row["proxy_path"] else None
    if not path or not path.exists():
        raise HTTPException(404, "Chưa có bản proxy")
    return FileResponse(path, media_type="video/mp4")  # starlette tu xu ly Range


@router.get("/{file_id}/original")
def original(file_id: int, request: Request, user: dict = Depends(current_user),
             conn: sqlite3.Connection = Depends(get_db)):
    row = _file_row(conn, file_id)
    if not row["storage_path"]:
        raise HTTPException(404, "File chưa lên storage")
    storage = get_storage(get_settings(conn))
    total = row["size_bytes"]
    start, end, status = 0, total - 1, 200
    m = re.match(r"bytes=(\d*)-(\d*)$", request.headers.get("range", "").strip())
    if m and (m.group(1) or m.group(2)):
        if m.group(1):
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else total - 1
        else:  # suffix range
            start = max(total - int(m.group(2)), 0)
        end = min(end, total - 1)
        if start > end:
            raise HTTPException(416, "Range không hợp lệ")
        status = 206
    headers = {"Accept-Ranges": "bytes", "Content-Length": str(end - start + 1)}
    if status == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{total}"
    return StreamingResponse(storage.open_range(row["storage_path"], start, end),
                             status_code=status, media_type="video/mp4", headers=headers)
