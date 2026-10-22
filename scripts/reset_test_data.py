"""Xoa du lieu test truoc khi chay production (GIU user, vai tro, cau hinh storage).

Xoa: file, danh gia, phieu, upload dang do trong CSDL; thumbnail, proxy, file tam (data/tmp).
Dat lai bo dem File ID / So phieu (se bat dau lai tu FILE_ID_START / TICKET_START trong .env).
KHONG xoa file video tren storage FTP (xoa tay), chi xoa data/storage neu them --with-local-storage.

Dung (DUNG app truoc):  python scripts/reset_test_data.py [--yes] [--with-local-storage]
"""
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.db import connect, init_db  # noqa: E402


def clear_dir(folder: Path) -> int:
    n = 0
    if folder.exists():
        for item in folder.iterdir():
            shutil.rmtree(item) if item.is_dir() else item.unlink()
            n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true", help="khong hoi xac nhan")
    ap.add_argument("--with-local-storage", action="store_true",
                    help=f"xoa luon thu muc storage cuc bo ({config.LOCAL_STORAGE_DIR})")
    args = ap.parse_args()

    init_db()
    conn = connect()
    counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("files", "reviews", "tickets", "uploads")}
    print(f"CSDL: {config.DB_PATH}")
    print("Se xoa:", ", ".join(f"{v} {k}" for k, v in counts.items()),
          f"| thumbnail/proxy/tmp trong {config.DATA_DIR}")
    if args.with_local_storage:
        print("      va TOAN BO", config.LOCAL_STORAGE_DIR)
    print("Se GIU: user, vai tro, cau hinh storage. Hay chac chan app DA DUNG va da backup.")
    if not args.yes and input("Go XOA de tiep tuc: ").strip() != "XOA":
        print("Da huy.")
        return

    conn.execute("PRAGMA foreign_keys = ON")
    for table in ("reviews", "tickets", "files", "uploads"):
        conn.execute(f"DELETE FROM {table}")
    conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('files', 'tickets')")
    conn.commit()
    conn.execute("VACUUM")
    conn.close()

    dirs = [config.THUMB_DIR, config.PROXY_DIR, config.TMP_DIR]
    if args.with_local_storage:
        dirs.append(config.LOCAL_STORAGE_DIR)
    for d in dirs:
        print(f"  xoa {clear_dir(d)} muc trong {d}")
    print("Xong. Khoi dong lai app: File ID / So phieu se bat dau tu FILE_ID_START / TICKET_START.")


if __name__ == "__main__":
    main()
