"""Upload chunked: ghep chunk vao file tam, tinh MD5 tang dan; sau do xu ly nen."""
import hashlib
import re
import sqlite3
import threading
import traceback
import uuid
from pathlib import Path

from app import config
from app.db import db_session, get_settings, now_str
from app.services import media
from app.services.storage import get_storage

_md5_states: dict[str, "hashlib._Hash"] = {}
_lock = threading.Lock()


def safe_name(name: str) -> str:
    name = Path(name.replace("\\", "/")).name
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip() or "file.mp4"


def tmp_path(upload_id: str) -> Path:
    return config.TMP_DIR / f"{upload_id}.part"


class Md5Mismatch(Exception):
    """MD5 server nhan duoc khac MD5 tinh tu file goc luc Check."""


def init_upload(conn: sqlite3.Connection, username: str, file_name: str, size: int, unit: str,
                md5: str, qc_result: str = "", qc_json: str = "") -> str:
    """md5 la MD5 tinh tu file goc luc Check file (iCheck) tren may ky thuat."""
    upload_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO uploads(upload_id, file_name, size_bytes, unit, received, username, created_at,"
        " md5, qc_result, qc_json) VALUES (?,?,?,?,0,?,?,?,?,?)",
        (upload_id, safe_name(file_name), size, unit, username, now_str(),
         md5.upper(), qc_result, qc_json))
    tmp_path(upload_id).write_bytes(b"")
    with _lock:
        _md5_states[upload_id] = hashlib.md5()
    return upload_id


def _rebuild_md5(upload_id: str, upto: int) -> "hashlib._Hash":
    h = hashlib.md5()
    remaining = upto
    with open(tmp_path(upload_id), "rb") as f:
        while remaining > 0:
            data = f.read(min(8 * 1024 * 1024, remaining))
            if not data:
                break
            h.update(data)
            remaining -= len(data)
    return h


def append_chunk(conn: sqlite3.Connection, upload_id: str, offset: int, data: bytes) -> int:
    """Ghi chunk tai offset (phai dung bang so byte da nhan). Tra ve so byte da nhan."""
    row = conn.execute("SELECT * FROM uploads WHERE upload_id = ?", (upload_id,)).fetchone()
    if not row:
        raise KeyError("upload không tồn tại")
    if offset != row["received"]:
        raise ValueError(f"offset sai: server đã nhận {row['received']} byte")
    if offset + len(data) > row["size_bytes"]:
        raise ValueError("Dữ liệu vượt quá dung lượng khai báo")
    with _lock:
        h = _md5_states.get(upload_id)
    if h is None:  # server restart giua chung: tinh lai tu file tam
        h = _rebuild_md5(upload_id, offset)
    with open(tmp_path(upload_id), "ab") as f:
        f.write(data)
    h.update(data)
    with _lock:
        _md5_states[upload_id] = h
    received = offset + len(data)
    conn.execute("UPDATE uploads SET received = ? WHERE upload_id = ?", (received, upload_id))
    return received


def finish_upload(conn: sqlite3.Connection, upload_id: str, username: str) -> dict:
    row = conn.execute("SELECT * FROM uploads WHERE upload_id = ?", (upload_id,)).fetchone()
    if not row:
        raise KeyError("upload không tồn tại")
    if row["received"] != row["size_bytes"]:
        raise ValueError(f"Chưa nhận đủ file ({row['received']}/{row['size_bytes']} byte)")
    with _lock:
        h = _md5_states.pop(upload_id, None)
    received_md5 = (h or _rebuild_md5(upload_id, row["size_bytes"])).hexdigest().upper()
    path = tmp_path(upload_id)
    if received_md5 != row["md5"]:
        # file bi loi khi truyen, hoac bi thay doi tren may ky thuat sau khi Check
        path.unlink(missing_ok=True)
        conn.execute("DELETE FROM uploads WHERE upload_id = ?", (upload_id,))
        raise Md5Mismatch(
            f"MD5 không khớp: lúc Check {row['md5']}, server nhận được {received_md5}. "
            "File bị lỗi khi truyền hoặc đã bị thay đổi sau khi Check - hãy Check và Upload lại.")
    md5 = row["md5"]
    try:
        info = media.probe(path)
    except Exception:
        path.unlink(missing_ok=True)
        conn.execute("DELETE FROM uploads WHERE upload_id = ?", (upload_id,))
        raise
    duplicate = conn.execute(
        "SELECT file_id FROM files WHERE md5 = ? LIMIT 1", (md5,)).fetchone()
    now = now_str()
    cur = conn.execute(
        "INSERT INTO files(file_name, md5, size_bytes, duration_sec, duration_tc, fps, width, height,"
        " codec, unit, uploaded_by, uploaded_at, tech_checked_by, tech_checked_at, status,"
        " qc_result, qc_json)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'processing', ?, ?)",
        (row["file_name"], md5, row["size_bytes"], info["duration_sec"], info["duration_tc"],
         info["fps"], info["width"], info["height"], info["codec"], row["unit"],
         username, now, username, now, row["qc_result"], row["qc_json"]))
    file_id = cur.lastrowid
    conn.execute("DELETE FROM uploads WHERE upload_id = ?", (upload_id,))
    conn.execute("INSERT INTO reviews(file_id, reviewer_kind) VALUES (?, 'ban_phu_trach')", (file_id,))
    conn.execute("INSERT INTO reviews(file_id, reviewer_kind) VALUES (?, 'bien_tap_vien')", (file_id,))
    return {"file_id": file_id, "md5": md5, "duplicate_of": duplicate["file_id"] if duplicate else None,
            "_tmp": str(path), "_name": row["file_name"]}


def start_processing(file_id: int, tmp_file: str, file_name: str) -> None:
    threading.Thread(target=process_file, args=(file_id, Path(tmp_file), file_name), daemon=True).start()


def _set_status(file_id: int, status: str, msg: str = "", **cols) -> None:
    sets = ["status = ?", "status_msg = ?"] + [f"{k} = ?" for k in cols]
    with db_session() as conn:
        conn.execute(f"UPDATE files SET {', '.join(sets)} WHERE file_id = ?",
                     (status, msg, *cols.values(), file_id))


def process_file(file_id: int, tmp_file: Path, file_name: str) -> None:
    """Thumbnail -> (proxy, neu bat) -> day file goc len storage -> xoa file tam."""
    try:
        with db_session() as conn:
            settings = get_settings(conn)
        thumb = config.THUMB_DIR / f"{file_id}.jpg"
        proxy = config.PROXY_DIR / f"{file_id}.mp4"
        thumb_ok = True
        try:
            media.make_thumbnail(tmp_file, thumb)
        except Exception:
            thumb_ok = False
        make_proxy = settings.get("create_proxy") == "1"
        if make_proxy:
            media.make_proxy(tmp_file, proxy)
        remote = f"files/{file_id}/{safe_name(file_name)}"
        get_storage(settings).put(tmp_file, remote)
        _set_status(file_id, "ready", "", storage_path=remote,
                    proxy_path=proxy.name if make_proxy else "",
                    thumb_path=thumb.name if thumb_ok else "")
        tmp_file.unlink(missing_ok=True)
    except Exception as exc:  # giu file tam de co the xu ly lai
        traceback.print_exc()
        _set_status(file_id, "error", str(exc)[:500])
