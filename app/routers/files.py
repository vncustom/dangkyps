"""Buoc 1: ky thuat upload file (MD5, luu CSDL, day len storage)."""
import json
import re
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
                  units=config.UNITS,
                  qc_spec=config.QC_SPEC)


@router.post("/api/upload/init")
async def upload_init(request: Request, user: dict = Depends(ky_thuat),
                      conn: sqlite3.Connection = Depends(get_db)):
    body = await request.json()
    name = str(body.get("file_name", "")).strip()
    size = int(body.get("size", 0))
    unit = str(body.get("unit", "")).strip()
    md5 = str(body.get("md5", "")).strip()
    qc = body.get("qc") if isinstance(body.get("qc"), dict) else {}
    if not name.lower().endswith(".mp4"):
        raise HTTPException(400, "Chỉ nhận file .mp4 (HEVC hoặc H.264)")
    if size <= 0:
        raise HTTPException(400, "File rỗng")
    if not unit:
        raise HTTPException(400, "Chưa chọn đơn vị (ban phụ trách duyệt)")
    if unit not in config.UNITS:
        raise HTTPException(400, "Đơn vị không hợp lệ")
    if not re.fullmatch(r"[0-9a-fA-F]{32}", md5):
        raise HTTPException(400, "Thiếu MD5 từ bước Check file - hãy bấm Check file trước khi Upload")
    qc_result = qc.get("result") if qc.get("result") in ("PASS", "FAIL") else ""
    qc_json = json.dumps(qc.get("items") or [], ensure_ascii=False)
    if len(qc_json) > 100_000:
        raise HTTPException(400, "Báo cáo QC quá lớn")
    upload_id = upload.init_upload(conn, user["username"], name, size, unit, md5,
                                   qc_result, qc_json if qc_result else "")
    return {"upload_id": upload_id}


@router.put("/api/upload/{upload_id}")
async def upload_file(upload_id: str, request: Request, user: dict = Depends(ky_thuat),
                      conn: sqlite3.Connection = Depends(get_db)):
    """Body = nguyen file goc (mot request duy nhat), nhan theo stream."""
    try:
        received = await upload.receive(conn, upload_id, request.stream())
    except KeyError:
        raise HTTPException(404, "Upload không tồn tại")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"received": received}


@router.post("/api/upload/{upload_id}/finish")
def upload_finish(upload_id: str, user: dict = Depends(ky_thuat),
                  conn: sqlite3.Connection = Depends(get_db)):
    try:
        result = upload.finish_upload(conn, upload_id, user["username"])
    except KeyError:
        raise HTTPException(404, "Upload không tồn tại")
    except upload.Md5Mismatch as exc:
        conn.commit()  # giu thay doi xoa upload/file tam
        raise HTTPException(422, str(exc))
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
    storage = get_storage(get_settings(conn))
    for remote in (f["storage_path"], f["proxy_path"], f["thumb_path"]):
        if remote:
            try:
                storage.delete(remote)
            except Exception:
                pass
    conn.execute("DELETE FROM files WHERE file_id = ?", (file_id,))
    return RedirectResponse("/files", status_code=303)
