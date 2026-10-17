"""Nap danh sach user tu CSV: python scripts/import_users.py [--csv FILE] [--reset]"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.db import db_session, init_db  # noqa: E402
from app.services.importer import import_users_csv  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(config.USERS_CSV))
    ap.add_argument("--reset", action="store_true",
                    help="dat lai mat khau mac dinh cho user da ton tai")
    args = ap.parse_args()
    init_db()
    with db_session() as conn:
        result = import_users_csv(conn, Path(args.csv), reset_existing=args.reset)
    print(f"Import xong: tao moi {result['created']}, cap nhat {result['updated']}")


if __name__ == "__main__":
    main()
