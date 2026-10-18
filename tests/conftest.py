import os
import pathlib
import subprocess
import tempfile

# Phai dat env TRUOC khi import app (config doc env luc import)
_TMP = pathlib.Path(tempfile.mkdtemp(prefix="dkps_test_"))
os.environ["DB_PATH"] = str(_TMP / "data" / "dkps.db")
os.environ["STORAGE_TYPE"] = "local"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["FORCE_PASSWORD_CHANGE"] = "0"
SSO_SECRET = "test-sso-shared-secret-0123456789abcdef"
os.environ["HTV_SSO_SECRET"] = SSO_SECRET
os.environ["HTV_SSO_SERVER_URL"] = "http://dashboard.test:8080"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import config  # noqa: E402
from app.db import db_session, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.importer import import_users_csv  # noqa: E402

PASSWORD = config.DEFAULT_PASSWORD

TEST_CSV = """username,full_name,ds_ban,ds_phong,ds_to,bac_vtvl,ds_vai_tro,JobTitles,Email,phone
admin,,,,,,,,,
tech1,Ky Thuat Mot,Ban A,,,,nhan_vien,,,
btv1,Bien Tap Mot,Ban A,,,,nhan_vien,,,
bpA,Truong Ban A,Ban A,,,,truong_ban,,,
bpB,Truong Ban B,Ban B,,,,truong_ban,,,
sec1,Thu Ky Mot,Ban A,,,,nhan_vien,,,
nobody,Khong Vai Tro,Ban A,,,,nhan_vien,,,
"""

ROLES = {"tech1": "ky_thuat", "btv1": "bien_tap_vien", "sec1": "thu_ky"}


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    init_db()
    csv_path = _TMP / "users.csv"
    csv_path.write_text(TEST_CSV, encoding="utf-8")
    with db_session() as conn:
        import_users_csv(conn, csv_path)
        for user, role in ROLES.items():
            conn.execute("INSERT OR IGNORE INTO user_roles(username, role) VALUES (?, ?)", (user, role))
    yield


@pytest.fixture(scope="session")
def sample_videos():
    out = {}
    for codec, lib in (("h264", "libx264"), ("hevc", "libx265")):
        path = _TMP / f"sample_{codec}.mp4"
        cmd = [config.FFMPEG_BIN, "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=25",
               "-f", "lavfi", "-i", "sine=duration=2", "-c:v", lib, "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-shortest", str(path)]
        subprocess.run(cmd, check=True, capture_output=True)
        out[codec] = path
    return out


def make_client(username: str | None = None, password: str = PASSWORD) -> TestClient:
    c = TestClient(app, follow_redirects=False)
    if username:
        r = c.post("/login", data={"username": username, "password": password})
        assert r.status_code == 303, r.text
    return c


@pytest.fixture()
def login():
    return make_client
