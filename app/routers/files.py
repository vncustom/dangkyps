"""Buoc 1: ky thuat upload file (MD5, luu CSDL, day len storage)."""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app import config
from app.db import get_db, get_settings
from app.security import require_roles
from app.services import domain, upload
from app.services.storage import get_storage
from app.web import render

router = APIRouter()
ky_thuat = require_roles("ky_thuat")


@router.get("/files")
def files_page(request: Request, user: dict = Depends(ky_thuat),
               conn: sqlite3.Connection = Depends(get_db)):
    return render(request, "files.html", user, files=domain.list_files(conn),
                  units=domain.units(conn), chunk_size=config.UPLOAD_CHUNK_SIZE)


@router.post("/api/upload/init")
async def upload_init(request: Request, user: dict = Depends(ky_thuat),
                      conn: sqlite3.Connection = Depends(get_db)):
    body = await request.json()
    name = str(body.get("file_name", "")).strip()
    size = int(body.get("size", 0))
    unit = str(body.get("unit", "")).strip()
    if not name.lower().endswith(".mp4"):
        raise HTTPException(400, "Chỉ nhận file .mp4 (HEVC hoặc H.264)")
    if size <= 0:
        raise HTTPException(400, "File rỗng")
    if not unit:
        raise HTTPException(400, "Chưa chọn đơn vị")
    upload_id = upload.init_upload(conn, user["username"], name, size, unit)
    return {"upload_id": upload_id, "chunk_size": config.UPLOAD_CHUNK_SIZE}


@router.put("/api/upload/{upload_id}")
async def upload_chunk(upload_id: str, offset: int, request: Request,
                       user: dict = Depends(ky_thuat), conn: sqlite3.Connection = Depends(get_db)):
    data = await request.body()
    try:
        received = upload.append_chunk(conn, upload_id, offset, data)
    except KeyError:
        raise HTTPException(404, "Upload không tồn tại")
    except ValueError as exc:
        conn.commit()
        raise HTTPException(409, str(exc))
    return {"received": received}


@router.get("/api/upload/{upload_id}")
def upload_status(upload_id: str, user: dict = Depends(ky_thuat),
                  conn: sqlite3.Connection = Depends(get_db)):
    row = conn.execute("SELECT received, size_bytes FROM uploads WHERE upload_id = ?",
                       (upload_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Upload không tồn tại")
    return {"received": row["received"], "size": row["size_bytes"]}


@router.post("/api/upload/{upload_id}/finish")
def upload_finish(upload_id: str, user: dict = Depends(ky_thuat),
                  conn: sqlite3.Connection = Depends(get_db)):
    try:
        result = upload.finish_upload(conn, upload_id, user["username"])
    except KeyError:
        raise HTTPException(404, "Upload không tồn tại")
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    except RuntimeError as exc:
        conn.commit()
        raise HTTPException(422, str(exc))
    conn.commit()  # phai commit truoc khi luong nen doc
    upload.start_processing(result["file_id"], result.pop("_tmp"), result.pop("_name"))
    return JSONResponse(result)


@router.post("/files/{file_id}/delete")
def delete_file(file_id: int, user: dict = Depends(ky_thuat),
                conn: sqlite3.Connection = Depends(get_db)):
    f = domain.get_file(conn, file_id)
    if not f:
        raise HTTPException(404, "Không tìm thấy file")
    if f["so_phieu"]:
        raise HTTPException(400, f"File đã gắn vào phiếu {f['so_phieu']}, không thể xóa")
    if f["status"] == "processing":
        raise HTTPException(400, "File đang xử lý, thử lại sau")
    if f["storage_path"]:
        try:
            get_storage(get_settings(conn)).delete(f["storage_path"])
        except Exception:
            pass
    for folder, name in ((config.PROXY_DIR, f["proxy_path"]), (config.THUMB_DIR, f["thumb_path"])):
        if name:
            (folder / name).unlink(missing_ok=True)
    conn.execute("DELETE FROM files WHERE file_id = ?", (file_id,))
    return RedirectResponse("/files", status_code=303)
