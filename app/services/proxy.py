"""Ten va vi tri file proxy tren storage.

Luc upload:      proxy/<ten file>_proxy.mp4
Sau khi nap phieu: proxy/<AssetFormID>_<ten file>_proxy.mp4  (bo file ra khoi phieu thi tra ve ten cu)
"""
import posixpath
import re
import sqlite3
import threading
from pathlib import Path

from app import config
from app.db import get_settings
from app.services.storage import StorageBackend, get_storage

SUFFIX = "_proxy.mp4"
_lock = threading.Lock()   # chon ten + ghi/doi ten tren storage phai tuan tu de khong de len nhau


def _clean(text: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f\s]', "_", text.strip())


def base_name(file_name: str) -> str:
    stem = Path(file_name).stem
    return f"{stem}{SUFFIX}"


def _candidates(base: str, file_id: int, prefix: str = "") -> list[str]:
    """Ten uu tien, roi ten co them file_id neu bi trung."""
    pre = f"{_clean(prefix)}_" if prefix.strip() else ""
    stem = base[:-len(SUFFIX)] if base.endswith(SUFFIX) else base
    return [f"{pre}{base}", f"{pre}{stem}_{file_id}{SUFFIX}"]


def _free(storage: StorageBackend, names: list[str], current: str = "") -> tuple[str, str]:
    for name in names:
        remote = f"{config.PROXY_FOLDER}/{name}"
        if remote == current or not storage.exists(remote):
            return name, remote
    raise RuntimeError(f"Trùng tên file proxy: {names[-1]}")


def store_new(storage: StorageBackend, local_file: Path, file_name: str, file_id: int) -> dict:
    """Day proxy vua tao len proxy/. Tra ve {path, base, size} de luu vao bang files."""
    with _lock:
        base, remote = _free(storage, _candidates(base_name(file_name), file_id))
        storage.put(local_file, remote)
    return {"path": remote, "base": base, "size": local_file.stat().st_size}


def set_prefix(conn: sqlite3.Connection, file_id: int, assetform_id: str | None) -> None:
    """Gan (hoac bo, khi assetform_id rong/None) prefix AssetForm ID vao ten proxy tren storage."""
    row = conn.execute("SELECT proxy_path, proxy_base FROM files WHERE file_id = ?", (file_id,)).fetchone()
    if not row or not row["proxy_path"]:
        return
    base = row["proxy_base"] or posixpath.basename(row["proxy_path"])
    storage = get_storage(get_settings(conn))
    with _lock:
        _, remote = _free(storage, _candidates(base, file_id, assetform_id or ""), row["proxy_path"])
        if remote == row["proxy_path"]:
            return
        storage.rename(row["proxy_path"], remote)
    conn.execute("UPDATE files SET proxy_path = ?, proxy_base = ? WHERE file_id = ?", (remote, base, file_id))
