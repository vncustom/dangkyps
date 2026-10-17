"""Cau hinh ung dung: doc .env (neu co) va bien moi truong."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_env_file()


def _path(name: str, default: str) -> Path:
    p = Path(os.environ.get(name, default))
    return p if p.is_absolute() else BASE_DIR / p


SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
DB_PATH = _path("DB_PATH", "data/dkps.db")
DATA_DIR = DB_PATH.parent
TMP_DIR = DATA_DIR / "tmp"
PROXY_DIR = DATA_DIR / "proxy"
THUMB_DIR = DATA_DIR / "thumbs"
LOCAL_STORAGE_DIR = DATA_DIR / "storage"

FFMPEG_DIR = _path("FFMPEG_DIR", "ffmpeg")
FFMPEG_BIN = str(FFMPEG_DIR / "ffmpeg.exe") if (FFMPEG_DIR / "ffmpeg.exe").exists() else "ffmpeg"
FFPROBE_BIN = str(FFMPEG_DIR / "ffprobe.exe") if (FFMPEG_DIR / "ffprobe.exe").exists() else "ffprobe"

USERS_CSV = _path("USERS_CSV", "tailieu chuan bi lam app/Danh sách_user.csv")
DEFAULT_PASSWORD = os.environ.get("DEFAULT_PASSWORD", "14dth@HTV")
FORCE_PASSWORD_CHANGE = os.environ.get("FORCE_PASSWORD_CHANGE", "0") == "1"

TICKET_START = int(os.environ.get("TICKET_START", "1"))
FILE_ID_START = int(os.environ.get("FILE_ID_START", "1"))

UPLOAD_CHUNK_SIZE = 16 * 1024 * 1024

# Yeu cau thong so file (tam thoi) cho nut "Check file" (iCheck) o buoc Ky thuat.
# Chi mang tinh tham khao: ky thuat xem ket qua roi tu quyet dinh co Upload hay khong.
QC_SPEC = {
    "container": "MP4 (Base Media)",
    "video_codec": "h264",          # h264 | hevc
    "video_profiles": ["Main", "Main 10", "High"],   # dat khi profile nam trong danh sach
    "video_level_min": 4.0,         # dat khi level >= gia tri nay
    "width": 3840,
    "height": 2160,
    "aspect": "16:9",
    "fps": 50.0,
    "cadence": "constant",
    "scan": "progressive",
    "chroma": "4:2:0",
    "bit_depth": 8,
    # audio: "aac" = nen (chi nhan profile audio_aac_profile), "pcm" = khong nen (moi dinh dang PCM)
    "audio_formats": ["aac", "pcm"],
    "audio_aac_profile": "LC",
    "audio_rate": 48000,
    "audio_channels": 2,
    "start_tc": "00:00:00:00",
}

# Danh muc
KENH_SONG = ["HTV7", "HTV9", "HTV1", "HTV2", "HTV3", "HTV4"]
NGUON_CUNG_CAP = ["HTV", "Sản xuất ngoài"]
# Ma the loai -> ten day du (hien thi o muc "Don vi" tren phieu in). Chinh sua tai day.
THE_LOAI = {
    "CT": "CHƯƠNG TRÌNH",
    "CD": "CD",
    "TFS": "TFS",
    "PT": "PT",
    "VN": "VN",
    "TT": "TT",
    "TTDV": "TTDV",
    "TS": "TS",
}
# Tai khoan admin cua app (tu dong cap quyen admin moi lan khoi dong, neu user ton tai trong CSV/DB).
# Co the doi bang bien moi truong ADMIN_USERS=admin,adminxe
ADMIN_USERS = [u.strip() for u in os.environ.get("ADMIN_USERS", "admin,adminxe").split(",") if u.strip()]
# Vai tro trong CSV (ds_vai_tro) duoc xem la "Ban phu trach"
BAN_PHU_TRACH_ROLES = {"truong_ban", "pho_ban", "truong_phong", "pho_phong"}
# Vai tro chuc nang gan trong app
APP_ROLES = ["admin", "ky_thuat", "bien_tap_vien", "thu_ky"]
ROLE_LABELS = {
    "admin": "Quản trị",
    "ky_thuat": "Kỹ thuật",
    "bien_tap_vien": "Biên tập viên",
    "thu_ky": "Thư ký",
    "ban_phu_trach": "Ban phụ trách",
}

# Gia tri mac dinh cua cau hinh storage (luu o bang settings, sua duoc tren trang admin)
STORAGE_DEFAULTS = {
    "storage_type": os.environ.get("STORAGE_TYPE", "ftp"),
    "ftp_host": os.environ.get("FTP_HOST", "127.0.0.1"),
    "ftp_port": os.environ.get("FTP_PORT", "2121"),
    "ftp_user": os.environ.get("FTP_USER", "dkps"),
    "ftp_pass": os.environ.get("FTP_PASS", "dkps"),
    "ftp_base_dir": os.environ.get("FTP_BASE_DIR", "/dkps"),
    # "1" = tao them ban proxy H.264 720p de duyet; "0" = xem truc tiep file goc tu storage
    "create_proxy": os.environ.get("CREATE_PROXY", "0"),
}
