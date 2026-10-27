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
LOCAL_STORAGE_DIR = DATA_DIR / "storage"
# Folder rieng tren storage (cung cap voi cac folder don vi) chua thumbnail va proxy
THUMB_FOLDER = "thumbs"
PROXY_FOLDER = "proxy"

FFMPEG_DIR = _path("FFMPEG_DIR", "ffmpeg")
FFMPEG_BIN = str(FFMPEG_DIR / "ffmpeg.exe") if (FFMPEG_DIR / "ffmpeg.exe").exists() else "ffmpeg"
FFPROBE_BIN = str(FFMPEG_DIR / "ffprobe.exe") if (FFMPEG_DIR / "ffprobe.exe").exists() else "ffprobe"

USERS_CSV = _path("USERS_CSV", "tailieu chuan bi lam app/Danh sách_user.csv")
# Dang nhap SSO HTV (htv_sso_fastapi.py). Secret phai GIONG HET Dashboard SSO; de trong => tu choi moi token.
HTV_SSO_SECRET = os.environ.get("HTV_SSO_SECRET", "")
HTV_SSO_SERVER_URL = os.environ.get("HTV_SSO_SERVER_URL", "")   # vd http://10.1.1.xxx:8080
HTV_SSO_APP_URL = os.environ.get("HTV_SSO_APP_URL", "")         # URL app nguoi dung truy cap, vd http://10.1.1.5:8004 (de trong = lay tu Host)
HTV_SSO_VERIFY_SLO = os.environ.get("HTV_SSO_VERIFY_SLO", "1") == "1"
DEFAULT_PASSWORD = os.environ.get("DEFAULT_PASSWORD", "14dth@HTV")
FORCE_PASSWORD_CHANGE = os.environ.get("FORCE_PASSWORD_CHANGE", "0") == "1"
# Cho nguoi dung tu doi mat khau (trang /password). Mac dinh TAT: chi admin dat lai mat khau o trang Nguoi dung.
# Khi tat, FORCE_PASSWORD_CHANGE khong co tac dung.
ALLOW_PASSWORD_CHANGE = os.environ.get("ALLOW_PASSWORD_CHANGE", "0") == "1"

TICKET_START = int(os.environ.get("TICKET_START", "1"))
FILE_ID_START = int(os.environ.get("FILE_ID_START", "1"))

# Yeu cau thong so file (tam thoi) cho nut "Check file" (iCheck) o buoc Ky thuat.
# Chi mang tinh tham khao: ky thuat xem ket qua roi tu quyet dinh co Upload hay khong.
QC_SPEC = {
    "container": "MP4 (Base Media)",
    "video_codecs": ["h264", "hevc"],   # chap nhan H.264 va H.265/HEVC (h265 = hevc)
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
KENH_SONG = ["HTV7", "HTV9", "HTV1", "HTV2", "HTV3", "HTV4", "HTV Thể Thao"]
NGUON_CUNG_CAP = ["HTV", "Sản xuất ngoài"]
# Don vi (ban phu trach duyet) chon khi upload file; cung la ten folder tren storage.
UNITS = [
    "Ban Chương trình",
    "Trung tâm Tin tức",
    "Ban Chuyên đề - Khoa giáo",
    "Ban Văn nghệ",
    "Ban Thể dục Thể thao",
    "Hãng phim Truyền hình TFS",
    "Trung tâm Phát hình - Tư liệu",
    "Trung tâm Dịch vụ truyền thông",
    "Trung tâm Phát triển nội dung số",
    "Trung tâm HTV Bình Dương",
    "Trung tâm HTV Bà Rịa",
    "Văn phòng",
    "Ban Tổ chức - Đào tạo",
    "Ban Chiến lược - Đầu tư",
    "Ban Kế hoạch - Tài chính",
    "Ban Kỹ thuật công nghệ",
    "Trung tâm Sản xuất chương trình",
    "Trung tâm Truyền dẫn Phát sóng",
    "Công ty TMS",
    "Trung tâm HTV Côn Đảo",
]
# Gia tri cot ds_ban trong CSV user -> ten don vi chinh thuc o UNITS (dung de xac dinh Ban phu trach duoc duyet).
# Gia tri khong co o day thi so truc tiep (vd da la ten chinh thuc).
DS_BAN_TO_UNIT = {
    "Ban CT": "Ban Chương trình",
    "TT Tin Tức": "Trung tâm Tin tức",
    "Ban Chuyên Đề Khoa Giáo": "Ban Chuyên đề - Khoa giáo",
    "Ban Văn Nghệ": "Ban Văn nghệ",
    "Ban Thể Thao": "Ban Thể dục Thể thao",
    "TFS": "Hãng phim Truyền hình TFS",
    "TTPHTL": "Trung tâm Phát hình - Tư liệu",
    "TTDVTT": "Trung tâm Dịch vụ truyền thông",
    "Ban PTNDS": "Trung tâm Phát triển nội dung số",
    "HTV_BD": "Trung tâm HTV Bình Dương",
    "HTV_BR": "Trung tâm HTV Bà Rịa",
    "Văn Phòng Đài": "Văn phòng",
    "TCĐT": "Ban Tổ chức - Đào tạo",
    "Ban KHTC": "Ban Kế hoạch - Tài chính",
    "Ban KTCN": "Ban Kỹ thuật công nghệ",
    "TTSXCT": "Trung tâm Sản xuất chương trình",
    "TT TDPS": "Trung tâm Truyền dẫn Phát sóng",
    "TMS": "Công ty TMS",
}
# Ma the loai -> don vi so huu (hien thi o muc "Don vi" tren phieu in). LIVE, PT chua gan don vi nen hien ma.
THE_LOAI = {
    "PH": "Trung tâm Phát hình - Tư liệu",
    "CTKL": "Ban Chương trình",
    "TT": "Ban Thể dục Thể thao",
    "LIVE": "LIVE",
    "CD": "Ban Chuyên đề - Khoa giáo",
    "CT": "Ban Chương trình",
    "TFS": "Hãng phim Truyền hình TFS",
    "VN": "Ban Văn nghệ",
    "QC": "Trung tâm Dịch vụ truyền thông",
    "TS": "Trung tâm Dịch vụ truyền thông",
    "KG": "Trung tâm Tin tức",
    "CN": "Ban Văn nghệ",
    "PT": "PT",
}


def unit_of_ds_ban(ds_ban: str) -> str:
    ds_ban = (ds_ban or "").strip()
    return DS_BAN_TO_UNIT.get(ds_ban, ds_ban)
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
    # "1" = tao ban proxy H.264 720p de duyet (player xem proxy cho nhe bang thong); "0" = xem truc tiep file goc
    "create_proxy": os.environ.get("CREATE_PROXY", "1"),
}
