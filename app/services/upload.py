"""Upload nguyen file mot lan: nhan stream ghi vao file tam, tinh MD5 tren duong di; sau do xu ly nen."""
import hashlib
import re
import sqlite3
import threading
import traceback
import unicodedata
import uuid
from pathlib import Path

from starlette.concurrency import run_in_threadpool

from app import config
from app.db import db_session, get_settings, now_str
from app.services import media
from app.services.storage import get_storage

_md5_states: dict[str, tuple["hashlib._Hash", int]] = {}   # upload_id -> (md5 cua file da nhan, so byte)
RECV_BUFFER = 4 * 1024 * 1024
_lock = threading.Lock()


def safe_name(name: str) -> str:
    name = Path(name.replace("\\", "/")).name
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip() or "file.mp4"


def folder_name(unit: str) -> str:
    """Ten don vi -> ten folder ASCII, viet lien, bo dau tieng Viet va dau '-' (vd BanChuyendeKhoagiao)."""
    s = unicodedata.normalize("NFD", unit.replace("đ", "d").replace("Đ", "D"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^A-Za-z0-9]", "", s) or "Khac"


def storage_path(unit: str, file_name: str, file_id: int, storage) -> str:
    """Duong dan tren storage: <TenDonViLienKhongDau>/<ten file>. Neu trung ten trong folder thi them _<file_id>."""
    folder = folder_name(unit)
    name = safe_name(file_name)
    remote = f"{folder}/{name}"
    if storage.exists(remote):
        stem, dot, ext = name.rpartition(".")
        remote = f"{folder}/{stem}_{file_id}.{ext}" if dot else f"{folder}/{name}_{file_id}"
    return remote


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
        _md5_states[upload_id] = (hashlib.md5(), 0)
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


def _write(f, h, data: bytes) -> None:
    f.write(data)
    h.update(data)


def _discard(conn: sqlite3.Connection, upload_id: str) -> None:
    tmp_path(upload_id).unlink(missing_ok=True)
    with _lock:
        _md5_states.pop(upload_id, None)
    conn.execute("DELETE FROM uploads WHERE upload_id = ?", (upload_id,))
    conn.commit()


async def receive(conn: sqlite3.Connection, upload_id: str, stream) -> int:
    """Nhan nguyen file tu stream (body request) vao file tam, vua ghi vua tinh MD5.
    Loi giua chung (dut ket noi, sai dung luong...) -> xoa file tam va upload; client phai Init lai."""
    row = conn.execute("SELECT * FROM uploads WHERE upload_id = ?", (upload_id,)).fetchone()
    if not row:
        raise KeyError("upload không tồn tại")
    if row["received"]:
        raise ValueError("Upload này đã nhận file rồi")
    expected = row["size_bytes"]
    h, total, buf = hashlib.md5(), 0, bytearray()
    try:
        with open(tmp_path(upload_id), "wb") as f:
            async for piece in stream:
                total += len(piece)
                if total > expected:
                    raise ValueError("Dữ liệu vượt quá dung lượng khai báo")
                buf += piece
                if len(buf) >= RECV_BUFFER:
                    await run_in_threadpool(_write, f, h, bytes(buf))
                    buf.clear()
            if buf:
                await run_in_threadpool(_write, f, h, bytes(buf))
        if total != expected:
            raise ValueError(f"Chưa nhận đủ file ({total}/{expected} byte)")
    except BaseException:
        _discard(conn, upload_id)
        raise
    conn.execute("UPDATE uploads SET received = ? WHERE upload_id = ?", (total, upload_id))
    conn.commit()
    with _lock:
        _md5_states[upload_id] = (h, total)
    return total


def cleanup_incomplete() -> int:
    """Luc khoi dong: moi upload dang do deu da dut (khong tiep tuc duoc) -> xoa file tam va dong trong bang uploads."""
    with db_session() as conn:
        ids = [r[0] for r in conn.execute("SELECT upload_id FROM uploads")]
        for upload_id in ids:
            tmp_path(upload_id).unlink(missing_ok=True)
        conn.execute("DELETE FROM uploads")
    return len(ids)


def finish_upload(conn: sqlite3.Connection, upload_id: str, username: str) -> dict:
    row = conn.execute("SELECT * FROM uploads WHERE upload_id = ?", (upload_id,)).fetchone()
    if not row:
        raise KeyError("upload không tồn tại")
    if row["received"] != row["size_bytes"]:
        raise ValueError(f"Chưa nhận đủ file ({row['received']}/{row['size_bytes']} byte)")
    with _lock:
        state = _md5_states.pop(upload_id, None)
    h = state[0] if state and state[1] == row["size_bytes"] else _rebuild_md5(upload_id, row["size_bytes"])
    received_md5 = h.hexdigest().upper()
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
        with db_session() as conn:
            unit = conn.execute("SELECT unit FROM files WHERE file_id = ?", (file_id,)).fetchone()["unit"]
        storage = get_storage(settings)
        remote = storage_path(unit, file_name, file_id, storage)
        storage.put(tmp_file, remote)
        _set_status(file_id, "ready", "", storage_path=remote,
                    proxy_path=proxy.name if make_proxy else "",
                    thumb_path=thumb.name if thumb_ok else "")
        tmp_file.unlink(missing_ok=True)
    except Exception as exc:  # giu file tam de co the xu ly lai
        traceback.print_exc()
        _set_status(file_id, "error", str(exc)[:500])
