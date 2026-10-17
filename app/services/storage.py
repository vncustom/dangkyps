"""Storage luu file video goc. Doi backend chi can sua cau hinh (bang settings)."""
import posixpath
import shutil
from abc import ABC, abstractmethod
from ftplib import FTP, error_perm
from pathlib import Path
from typing import Iterator

from app import config

CHUNK = 1024 * 1024


class StorageBackend(ABC):
    @abstractmethod
    def put(self, local_path: Path, remote_path: str) -> None: ...

    @abstractmethod
    def size(self, remote_path: str) -> int: ...

    @abstractmethod
    def open_range(self, remote_path: str, start: int, end: int) -> Iterator[bytes]:
        """Doc byte [start, end] (inclusive)."""

    @abstractmethod
    def delete(self, remote_path: str) -> None: ...

    @abstractmethod
    def exists(self, remote_path: str) -> bool: ...


class LocalStorage(StorageBackend):
    def __init__(self, base_dir: Path):
        self.base = Path(base_dir)

    def _p(self, remote_path: str) -> Path:
        return self.base / remote_path

    def put(self, local_path, remote_path):
        dest = self._p(remote_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local_path, dest)

    def size(self, remote_path):
        return self._p(remote_path).stat().st_size

    def open_range(self, remote_path, start, end):
        remaining = end - start + 1
        with open(self._p(remote_path), "rb") as f:
            f.seek(start)
            while remaining > 0:
                data = f.read(min(CHUNK, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    def delete(self, remote_path):
        self._p(remote_path).unlink(missing_ok=True)

    def exists(self, remote_path):
        return self._p(remote_path).exists()


class FtpStorage(StorageBackend):
    def __init__(self, host: str, port: int, user: str, password: str, base_dir: str = "/"):
        self.host, self.port, self.user, self.password = host, port, user, password
        self.base_dir = base_dir if base_dir.startswith("/") else "/" + base_dir

    def _connect(self) -> FTP:
        ftp = FTP()
        ftp.connect(self.host, self.port, timeout=30)
        ftp.login(self.user, self.password)
        ftp.voidcmd("TYPE I")
        return ftp

    def _full(self, remote_path: str) -> str:
        return posixpath.join(self.base_dir, remote_path.lstrip("/"))

    @staticmethod
    def _ensure_dir(ftp: FTP, directory: str) -> None:
        ftp.cwd("/")
        for part in [p for p in directory.split("/") if p]:
            try:
                ftp.cwd(part)
            except error_perm:
                ftp.mkd(part)
                ftp.cwd(part)
        ftp.cwd("/")

    def put(self, local_path, remote_path):
        full = self._full(remote_path)
        ftp = self._connect()
        try:
            self._ensure_dir(ftp, posixpath.dirname(full))
            with open(local_path, "rb") as f:
                ftp.storbinary(f"STOR {full}", f, blocksize=CHUNK)
        finally:
            try:
                ftp.quit()
            except Exception:
                ftp.close()

    def size(self, remote_path):
        ftp = self._connect()
        try:
            return ftp.size(self._full(remote_path)) or 0
        finally:
            ftp.close()

    def open_range(self, remote_path, start, end):
        ftp = self._connect()
        conn = None
        try:
            conn = ftp.transfercmd(f"RETR {self._full(remote_path)}", rest=start if start else None)
            remaining = end - start + 1
            while remaining > 0:
                data = conn.recv(min(CHUNK, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data
        finally:
            if conn:
                conn.close()
            ftp.close()

    def delete(self, remote_path):
        ftp = self._connect()
        try:
            try:
                ftp.delete(self._full(remote_path))
            except error_perm:
                pass
        finally:
            ftp.close()

    def exists(self, remote_path):
        ftp = self._connect()
        try:
            try:
                ftp.size(self._full(remote_path))
                return True
            except error_perm:
                return False
        finally:
            ftp.close()


def get_storage(settings: dict) -> StorageBackend:
    kind = settings.get("storage_type", "ftp")
    if kind == "local":
        return LocalStorage(config.LOCAL_STORAGE_DIR)
    if kind == "ftp":
        return FtpStorage(
            settings["ftp_host"], int(settings["ftp_port"]),
            settings["ftp_user"], settings["ftp_pass"], settings["ftp_base_dir"],
        )
    raise ValueError(f"storage_type không hợp lệ: {kind}")
