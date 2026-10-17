"""FTP server local de dev/test: python scripts/dev_ftp.py  (mac dinh 127.0.0.1:2121, user dkps/dkps)."""
import argparse
import sys
from pathlib import Path

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2121)
    ap.add_argument("--user", default="dkps")
    ap.add_argument("--password", default="dkps")
    ap.add_argument("--root", default=str(ROOT / "data" / "ftp_root"))
    args = ap.parse_args()
    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)
    authorizer = DummyAuthorizer()
    authorizer.add_user(args.user, args.password, str(root), perm="elradfmw")
    handler = FTPHandler
    handler.authorizer = authorizer
    print(f"FTP server: ftp://{args.user}:***@{args.host}:{args.port}  root={root}", file=sys.stderr)
    FTPServer((args.host, args.port), handler).serve_forever()


if __name__ == "__main__":
    main()
