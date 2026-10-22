"""Ho tro setup.bat:  python scripts/setup_helper.py env | ffmpeg | check"""
import secrets
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


def cmd_env() -> int:
    """Tao .env tu .env.example voi SECRET_KEY ngau nhien (khong ghi de neu da co)."""
    env = ROOT / ".env"
    if env.exists():
        print("      .env da co - giu nguyen")
        return 0
    example = ROOT / ".env.example"
    lines = example.read_text(encoding="utf-8").splitlines() if example.exists() else []
    key = f"SECRET_KEY={secrets.token_urlsafe(48)}"
    if any(line.startswith("SECRET_KEY=") for line in lines):
        lines = [key if line.startswith("SECRET_KEY=") else line for line in lines]
    else:
        lines.insert(0, key)
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("      Da tao .env (SECRET_KEY ngau nhien). FTP / SSO co the nhap sau o trang Storage tren web.")
    return 0


def _have_ffmpeg() -> bool:
    if (ROOT / "ffmpeg" / "ffprobe.exe").exists() and (ROOT / "ffmpeg" / "ffmpeg.exe").exists():
        return True
    return bool(shutil.which("ffprobe") and shutil.which("ffmpeg"))


def cmd_ffmpeg() -> int:
    """Neu thieu ffmpeg thi tai ban build san va giai nen ffmpeg.exe, ffprobe.exe vao ffmpeg/. Loi khong dung setup."""
    if _have_ffmpeg():
        print("      OK: da co ffmpeg")
        return 0
    print("      Chua co ffmpeg - dang tai (~90 MB, vai phut)...")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "ffmpeg.zip"
            with urllib.request.urlopen(FFMPEG_URL, timeout=60) as resp, open(zip_path, "wb") as out:
                total = 0
                while chunk := resp.read(1024 * 1024):
                    out.write(chunk)
                    total += len(chunk)
                    if total % (20 * 1024 * 1024) < 1024 * 1024:
                        print(f"      ...{total // 1048576} MB", flush=True)
            dest = ROOT / "ffmpeg"
            dest.mkdir(exist_ok=True)
            with zipfile.ZipFile(zip_path) as z:
                found = 0
                for name in z.namelist():
                    base = name.rsplit("/", 1)[-1].lower()
                    if "/bin/" in name and base in ("ffmpeg.exe", "ffprobe.exe"):
                        (dest / base).write_bytes(z.read(name))
                        found += 1
            if found != 2:
                raise RuntimeError("goi tai ve khong co ffmpeg.exe / ffprobe.exe")
        print("      OK: da cai ffmpeg vao thu muc ffmpeg\\")
    except Exception as exc:  # noqa: BLE001
        print(f"      [canh bao] Khong tai duoc ffmpeg tu dong: {exc}")
        print("      Hay chep thu muc ffmpeg\\ (ffmpeg.exe, ffprobe.exe) tu may cu vao thu muc app, roi chay lai setup.bat.")
    return 0


def cmd_check() -> int:
    """Kiem tra app nap duoc, ffprobe chay duoc, co file CSV user."""
    sys.path.insert(0, str(ROOT))
    try:
        from app import config
        import app.main  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        print(f"      [loi] Khong nap duoc app: {exc!r}")
        return 1
    try:
        subprocess.run([config.FFPROBE_BIN, "-version"], capture_output=True, check=True)
        print("      OK: ffprobe chay duoc")
    except Exception:  # noqa: BLE001
        print("      [canh bao] ffprobe khong chay duoc - upload se loi cho den khi co ffmpeg.")
    if config.USERS_CSV.exists():
        print(f"      OK: co file user {config.USERS_CSV.name}")
    else:
        print(f"      [canh bao] THIEU file danh sach user: {config.USERS_CSV}")
        print("      Hay chep file CSV vao dung duong dan tren (neu khong se khong ai dang nhap duoc), roi khoi dong lai app.")
    return 0


def main() -> int:
    handlers = {"env": cmd_env, "ffmpeg": cmd_ffmpeg, "check": cmd_check}
    if len(sys.argv) != 2 or sys.argv[1] not in handlers:
        print(__doc__)
        return 2
    return handlers[sys.argv[1]]()


if __name__ == "__main__":
    sys.exit(main())
