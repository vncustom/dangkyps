import csv
import hashlib
import json
import os
import sqlite3
import time

from app import config
from app.db import SCHEMA, db_session
from app.services.importer import import_users_csv
from app.security import verify_password

from tests.conftest import PASSWORD, make_client


def md5_upper(path):
    return hashlib.md5(path.read_bytes()).hexdigest().upper()


QC_ITEMS = [{"n": 1, "param": "File name", "expected": "Display only", "actual": "x.mp4", "status": "INFO"}]


def upload(client, path, unit="Ban Chương trình"):
    data = path.read_bytes()
    md5 = hashlib.md5(data).hexdigest().upper()  # nhu buoc Check file tinh tren file goc
    r = client.post("/api/upload/init", json={
        "file_name": path.name, "size": len(data), "unit": unit, "md5": md5,
        "qc": {"result": "PASS", "items": QC_ITEMS}})
    assert r.status_code == 200, r.text
    uid = r.json()["upload_id"]
    r = client.put(f"/api/upload/{uid}", content=data)   # nguyen file, mot request
    assert r.status_code == 200 and r.json()["received"] == len(data), r.text
    r = client.post(f"/api/upload/{uid}/finish")
    assert r.status_code == 200, r.text
    return r.json()


def wait_ready(file_id, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        with db_session() as conn:
            row = conn.execute("SELECT status, status_msg FROM files WHERE file_id = ?", (file_id,)).fetchone()
        if row["status"] != "processing":
            assert row["status"] == "ready", row["status_msg"]
            return
        time.sleep(0.5)
    raise AssertionError("xử lý file quá lâu")


def approve(file_id, bp="bpA", btv="btv1"):
    for user, kind in ((bp, "ban_phu_trach"), (btv, "bien_tap_vien")):
        r = make_client(user).post("/login", data={"username": user, "password": PASSWORD})
        c = make_client(user)
        r = c.post(f"/review/{file_id}", data={"kind": kind, "result": "dat"})
        assert r.status_code == 303, r.text


def new_ticket(sec, **over):
    data = dict(assetform_id="458959", kenh="HTV7", ten_chuong_trinh="Teaser Ai đúng ai sai",
                ngay_phat_song="2026-10-14", the_loai="CT", nguon_cung_cap="HTV", ghi_chu="")
    data.update(over)
    return sec.post("/tickets/new", data=data)


# ---- auth / import --------------------------------------------------------

def test_import_real_csv_hashes_default_password(tmp_path):
    assert config.USERS_CSV.exists()
    with open(config.USERS_CSV, newline="", encoding="utf-8-sig") as f:
        expected = sum(1 for r in csv.DictReader(f) if (r["username"] or "").strip())
    mem = sqlite3.connect(":memory:")  # DB rieng, khong anh huong user test
    mem.row_factory = sqlite3.Row
    mem.executescript(SCHEMA)
    result = import_users_csv(mem, config.USERS_CSV)
    assert result["created"] == expected and expected > 400
    row = mem.execute("SELECT pw_hash FROM users WHERE username = 'admin'").fetchone()
    assert PASSWORD not in row["pw_hash"] and verify_password(PASSWORD, row["pw_hash"])
    assert mem.execute("SELECT 1 FROM user_roles WHERE username='admin' AND role='admin'").fetchone()


def test_admin_users_from_config_get_admin_role():
    from app.services.importer import ensure_admins
    assert config.ADMIN_USERS == ["admin", "adminxe"]
    mem = sqlite3.connect(":memory:")
    mem.row_factory = sqlite3.Row
    mem.executescript(SCHEMA)
    import_users_csv(mem, config.USERS_CSV)       # CSV that co ca admin va adminxe
    roles = {r[0] for r in mem.execute("SELECT username FROM user_roles WHERE role = 'admin'")}
    assert roles == {"admin", "adminxe"}
    mem.execute("DELETE FROM user_roles")          # khoi dong lai phai cap lai
    assert sorted(ensure_admins(mem)) == ["admin", "adminxe"]
    assert {r[0] for r in mem.execute("SELECT username FROM user_roles WHERE role = 'admin'")} == {"admin", "adminxe"}


def test_login_and_protection(login):
    anon = login()
    r = anon.get("/files")
    assert r.status_code == 303 and r.headers["location"] == "/login"
    assert anon.put("/api/upload/xyz", content=b"x").status_code == 401
    bad = anon.post("/login", data={"username": "tech1", "password": "sai"})
    assert bad.status_code == 401
    assert login("tech1").get("/").status_code == 200


def test_role_enforcement(login):
    tech, sec, nobody = login("tech1"), login("sec1"), login("nobody")
    assert tech.get("/tickets").status_code == 403
    assert sec.get("/files").status_code == 403
    assert sec.post("/api/upload/init", json={"file_name": "a.mp4", "size": 1, "unit": "Ban Chương trình"}).status_code == 403
    assert nobody.get("/review").status_code == 403
    assert login("btv1").get("/admin/users").status_code == 403
    assert login("admin").get("/admin/users").status_code == 200


# ---- upload / MD5 ---------------------------------------------------------

def test_upload_md5_matches_and_rejects_non_mp4(login, sample_videos):
    tech = login("tech1")
    path = sample_videos["h264"]
    res = upload(tech, path)
    assert res["md5"] == md5_upper(path)
    wait_ready(res["file_id"])
    with db_session() as conn:
        f = conn.execute("SELECT * FROM files WHERE file_id = ?", (res["file_id"],)).fetchone()
    assert f["md5"] == md5_upper(path) and f["fps"] == 25 and f["width"] == 320
    assert f["duration_tc"].startswith("00:00:02") and f["storage_path"]
    assert f["proxy_path"] == ""  # mac dinh khong tao proxy, xem truc tiep file goc
    assert (config.LOCAL_STORAGE_DIR / f["storage_path"]).stat().st_size == path.stat().st_size
    r = tech.post("/api/upload/init", json={"file_name": "x.mxf", "size": 10, "unit": "Ban Chương trình", "md5": "0" * 32})
    assert r.status_code == 400
    # gui thieu / thua byte so voi dung luong khai bao bi tu choi, file tam va dong upload bi xoa
    for body in (b"x" * 50, b"x" * 150):
        uid = tech.post("/api/upload/init", json={"file_name": "a.mp4", "size": 100, "unit": "Ban Chương trình",
                                                  "md5": "0" * 32}).json()["upload_id"]
        assert tech.put(f"/api/upload/{uid}", content=body).status_code == 400
        assert not (config.TMP_DIR / f"{uid}.part").exists()
        assert tech.put(f"/api/upload/{uid}", content=b"x" * 100).status_code == 404
    # moi upload chi nhan file mot lan
    uid = tech.post("/api/upload/init", json={"file_name": "a.mp4", "size": 100, "unit": "Ban Chương trình",
                                              "md5": "0" * 32}).json()["upload_id"]
    assert tech.put(f"/api/upload/{uid}", content=b"x" * 100).status_code == 200
    assert tech.put(f"/api/upload/{uid}", content=b"x" * 100).status_code == 400


def test_upload_unit_required_and_must_be_in_list(login):
    tech = login("tech1")
    base = {"file_name": "a.mp4", "size": 10, "md5": "0" * 32}
    assert tech.post("/api/upload/init", json=base).status_code == 400                       # chua chon
    assert tech.post("/api/upload/init", json={**base, "unit": "Ban Linh Tinh"}).status_code == 400
    assert tech.post("/api/upload/init", json={**base, "unit": config.UNITS[0]}).status_code == 200


def test_storage_folder_is_unit_name(login, sample_videos):
    tech = login("tech1")
    unit = "Ban Chuyên đề - Khoa giáo"
    r1, r2 = upload(tech, sample_videos["h264"], unit=unit), upload(tech, sample_videos["h264"], unit=unit)
    wait_ready(r1["file_id"]); wait_ready(r2["file_id"])
    with db_session() as conn:
        p1, p2 = [conn.execute("SELECT storage_path FROM files WHERE file_id = ?", (r["file_id"],)).fetchone()[0]
                  for r in (r1, r2)]
    name, folder = sample_videos["h264"].name, "BanChuyendeKhoagiao"          # bo dau, viet lien, bo "-"
    assert p1 == f"{folder}/{name}" and p2 != p1 and p2.startswith(f"{folder}/")   # trung ten -> them _file_id
    assert (config.LOCAL_STORAGE_DIR / folder / name).exists()
    assert (config.LOCAL_STORAGE_DIR / p2).stat().st_size == sample_videos["h264"].stat().st_size


def test_large_body_streamed_in_one_request(login, tmp_path):
    """File lon hon bo dem nhan (RECV_BUFFER): ghi nhieu dot nhung MD5/dung luong van dung."""
    from app.services import upload as up
    tech = login("tech1")
    data = os.urandom(up.RECV_BUFFER * 2 + 12345)
    md5 = hashlib.md5(data).hexdigest().upper()
    uid = tech.post("/api/upload/init", json={"file_name": "big.mp4", "size": len(data), "unit": config.UNITS[0],
                                              "md5": md5}).json()["upload_id"]
    assert tech.put(f"/api/upload/{uid}", content=data).status_code == 200
    assert (config.TMP_DIR / f"{uid}.part").read_bytes() == data
    assert up._md5_states[uid][0].hexdigest().upper() == md5


def test_cleanup_incomplete_uploads_on_startup(login):
    from app.services import upload as up
    tech = login("tech1")
    uid = tech.post("/api/upload/init", json={"file_name": "a.mp4", "size": 10, "unit": config.UNITS[0],
                                              "md5": "0" * 32}).json()["upload_id"]
    assert (config.TMP_DIR / f"{uid}.part").exists()
    assert up.cleanup_incomplete() >= 1
    assert not (config.TMP_DIR / f"{uid}.part").exists()
    with db_session() as conn:
        assert conn.execute("SELECT COUNT(*) FROM uploads").fetchone()[0] == 0


def test_folder_name_ascii_no_separators():
    from app.services.upload import folder_name
    assert folder_name("Trung tâm Phát hình - Tư liệu") == "TrungtamPhathinhTulieu"
    assert [folder_name(u) for u in config.UNITS[:3]] == ["BanChuongtrinh", "TrungtamTintuc", "BanChuyendeKhoagiao"]
    assert len({folder_name(u) for u in config.UNITS}) == len(config.UNITS)      # khong dung folder
    assert all(folder_name(u).isascii() and folder_name(u).isalnum() for u in config.UNITS)


def test_upload_requires_md5_from_check(login, sample_videos):
    tech = login("tech1")
    base = {"file_name": "a.mp4", "size": 10, "unit": "Ban Chương trình"}
    assert tech.post("/api/upload/init", json=base).status_code == 400            # thieu md5
    assert tech.post("/api/upload/init", json={**base, "md5": "xyz"}).status_code == 400  # md5 sai dinh dang


def test_md5_stored_is_the_one_from_check_and_mismatch_rejected(login, sample_videos):
    tech = login("tech1")
    path = sample_videos["h264"]
    data = path.read_bytes()
    # 1) MD5 luc Check KHAC noi dung gui len (file doi sau khi Check / loi truyen) -> tu choi, khong tao file
    with db_session() as conn:
        before = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    wrong = "A" * 32
    uid = tech.post("/api/upload/init", json={"file_name": path.name, "size": len(data), "unit": "Ban Chương trình",
                                              "md5": wrong}).json()["upload_id"]
    assert tech.put(f"/api/upload/{uid}", content=data).status_code == 200
    r = tech.post(f"/api/upload/{uid}/finish")
    assert r.status_code == 422 and "MD5 không khớp" in r.json()["detail"]
    with db_session() as conn:
        assert conn.execute("SELECT COUNT(*) FROM files").fetchone()[0] == before
        assert conn.execute("SELECT 1 FROM uploads WHERE upload_id = ?", (uid,)).fetchone() is None
    assert not (config.TMP_DIR / f"{uid}.part").exists()
    # 2) MD5 dung -> luu dung gia tri tu Check (chu hoa) + ket qua QC
    lower = hashlib.md5(data).hexdigest()  # Check gui chu thuong van duoc chap nhan
    uid = tech.post("/api/upload/init", json={"file_name": path.name, "size": len(data), "unit": "Ban Chương trình",
                                              "md5": lower, "qc": {"result": "FAIL", "items": QC_ITEMS}}).json()["upload_id"]
    tech.put(f"/api/upload/{uid}", content=data)
    res = tech.post(f"/api/upload/{uid}/finish").json()
    assert res["md5"] == lower.upper()
    with db_session() as conn:
        row = conn.execute("SELECT md5, qc_result, qc_json FROM files WHERE file_id = ?", (res["file_id"],)).fetchone()
    assert row["md5"] == lower.upper() and row["qc_result"] == "FAIL" and json.loads(row["qc_json"]) == QC_ITEMS
    wait_ready(res["file_id"])
    page = make_client("admin")
    page = page.get(f"/review/{res['file_id']}")
    assert page.status_code == 200 and "Báo cáo QC" in page.text


def test_hevc_upload(login, sample_videos):
    res = upload(login("tech1"), sample_videos["hevc"])
    wait_ready(res["file_id"])
    with db_session() as conn:
        assert conn.execute("SELECT codec FROM files WHERE file_id = ?", (res["file_id"],)).fetchone()[0] == "hevc"


def test_media_range_requests(login, sample_videos):
    tech = login("tech1")
    res = upload(tech, sample_videos["h264"])
    wait_ready(res["file_id"])
    fid = res["file_id"]
    r = tech.get(f"/media/{fid}/original", headers={"Range": "bytes=0-9"})
    assert r.status_code == 206 and len(r.content) == 10
    assert r.headers["content-range"].startswith("bytes 0-9/")
    size = sample_videos["h264"].stat().st_size
    r = tech.get(f"/media/{fid}/original", headers={"Range": f"bytes={size - 5}-"})
    assert r.status_code == 206 and r.content == sample_videos["h264"].read_bytes()[-5:]
    r = tech.get(f"/media/{fid}/original")
    assert r.status_code == 200 and len(r.content) == size
    assert tech.get(f"/media/{fid}/thumb").status_code == 200
    assert tech.get(f"/media/{fid}/proxy").status_code == 404  # khong co proxy


def test_player_uses_original_unless_proxy_enabled(login, sample_videos):
    admin, tech = login("admin"), login("tech1")
    res = upload(tech, sample_videos["h264"])
    wait_ready(res["file_id"])
    fid = res["file_id"]
    page = admin.get(f"/review/{fid}").text
    assert f'src="/media/{fid}/original"' in page and "data-original" not in page
    # bat tao proxy -> file moi co proxy va player dung proxy
    r = admin.post("/admin/settings", data={"storage_type": "local", "create_proxy": "1"})
    assert r.status_code == 303
    try:
        res2 = upload(tech, sample_videos["h264"])
        wait_ready(res2["file_id"])
        fid2 = res2["file_id"]
        page2 = admin.get(f"/review/{fid2}").text
        assert f'src="/media/{fid2}/proxy"' in page2 and f'data-original="/media/{fid2}/original"' in page2
        r = tech.get(f"/media/{fid2}/proxy", headers={"Range": "bytes=0-9"})
        assert r.status_code == 206 and len(r.content) == 10
    finally:
        admin.post("/admin/settings", data={"storage_type": "local"})  # tat lai


# ---- review rules / tickets ------------------------------------------------

def test_review_permissions_and_rules(login, sample_videos):
    tech = login("tech1")
    res = upload(tech, sample_videos["h264"], unit="Ban Chương trình")
    fid = res["file_id"]
    wait_ready(fid)
    bpB, bpA, btv = login("bpB"), login("bpA"), login("btv1")
    # TT Tin Tuc khong duyet duoc file cua Ban Chuong trinh
    assert bpB.post(f"/review/{fid}", data={"kind": "ban_phu_trach", "result": "dat"}).status_code == 403
    assert bpB.get(f"/review/{fid}").status_code == 403
    # BTV khong duyet thay Ban phu trach
    assert btv.post(f"/review/{fid}", data={"kind": "ban_phu_trach", "result": "dat"}).status_code == 403
    # Khong dat bat buoc nhan xet
    assert bpA.post(f"/review/{fid}", data={"kind": "ban_phu_trach", "result": "khong_dat"}).status_code == 400
    assert bpA.post(f"/review/{fid}", data={"kind": "ban_phu_trach", "result": "khong_dat",
                                            "comment": "Sai loudness"}).status_code == 303
    assert btv.post(f"/review/{fid}", data={"kind": "bien_tap_vien", "result": "dat"}).status_code == 303
    sec = login("sec1")
    t = new_ticket(sec)
    assert t.status_code == 303
    so = t.headers["location"].rsplit("/", 1)[1]
    # 1 ben Khong dat -> khong duoc nap
    assert sec.post(f"/tickets/{so}/attach", data={"file_id": fid}).status_code == 400
    # sua thanh Dat -> duoc nap
    assert bpA.post(f"/review/{fid}", data={"kind": "ban_phu_trach", "result": "dat"}).status_code == 303
    assert sec.post(f"/tickets/{so}/attach", data={"file_id": fid}).status_code == 303
    # da gan phieu -> khong doi ket qua duyet, khong xoa, khong gan phieu khac
    assert bpA.post(f"/review/{fid}", data={"kind": "ban_phu_trach", "result": "chua"}).status_code == 400
    assert tech.post(f"/files/{fid}/delete").status_code == 400
    so2 = new_ticket(sec, assetform_id="1").headers["location"].rsplit("/", 1)[1]
    assert sec.post(f"/tickets/{so2}/attach", data={"file_id": fid}).status_code == 400
    # bo file ra -> gan lai duoc
    assert sec.post(f"/tickets/{so}/detach").status_code == 303
    assert sec.post(f"/tickets/{so2}/attach", data={"file_id": fid}).status_code == 303


def test_ticket_validation_and_autoincrement(login):
    sec = login("sec1")
    assert new_ticket(sec, assetform_id="").status_code == 400
    assert new_ticket(sec, kenh="HTV5").status_code == 400
    assert new_ticket(sec, the_loai="XX").status_code == 400
    assert new_ticket(sec, nguon_cung_cap="Khac").status_code == 400
    assert new_ticket(sec, ngay_phat_song="14/10/2026").status_code == 400
    a = int(new_ticket(sec).headers["location"].rsplit("/", 1)[1])
    b = int(new_ticket(sec).headers["location"].rsplit("/", 1)[1])
    assert b == a + 1
    page = sec.get(f"/tickets/{a}")
    assert page.status_code == 200 and "458959" in page.text


def test_print_ticket(login, sample_videos):
    res = upload(login("tech1"), sample_videos["h264"], unit="Ban Chương trình")
    fid = res["file_id"]
    wait_ready(fid)
    approve(fid)
    sec = login("sec1")
    so = new_ticket(sec, assetform_id="464277", ten_chuong_trinh="Teaser Ai đúng ai sai") \
        .headers["location"].rsplit("/", 1)[1]
    sec.post(f"/tickets/{so}/attach", data={"file_id": fid})
    r = sec.get(f"/print/{so}")
    assert r.status_code == 200
    body = r.text
    for expected in (f"Số phiếu:</b> {so}", "Ngày phát sóng:</b> 14/10/2026", "Kênh:</b> HTV7",
                     "Ban Chương trình", "Teaser Ai đúng ai sai", res["md5"], sample_videos["h264"].name,
                     "464277", "Time code in", "Time code out", "Ban phụ trách duyệt:</b> Truong Ban A",
                     "Biên tập viên duyệt:</b> Bien Tap Mot", "Kiểm tra kỹ thuật:</b> Ky Thuat Mot",
                     "Phát lần", "Ngày hoàn chỉnh file", "Đơn vị hậu kỳ", "Phát Hình"):
        assert expected in body, expected
    assert sec.get("/print/999999").status_code == 404


def test_password_change_and_admin_roles(login):
    admin = login("admin")
    r = admin.post("/admin/users/nobody/roles", data={"role": "thu_ky"})
    assert r.status_code == 303
    nobody = login("nobody")
    assert nobody.get("/tickets").status_code == 200
    # doi mat khau
    r = nobody.post("/password", data={"old_password": PASSWORD, "new_password": "matkhau-moi1",
                                       "confirm_password": "matkhau-moi1"})
    assert r.status_code == 200
    assert make_client().post("/login", data={"username": "nobody", "password": PASSWORD}).status_code == 401
    assert make_client("nobody", "matkhau-moi1").get("/").status_code == 200
    # admin dat lai mat khau mac dinh
    assert admin.post("/admin/users/nobody/reset-password").status_code == 303
    assert make_client("nobody").get("/").status_code == 200


def test_static_assets_are_versioned_and_not_cached(login):
    tech = login("tech1")
    page = tech.get("/files").text
    for name in ("js/upload.js", "css/app.css"):
        assert f"/static/{name}?v=" in page
    assert "/static/js/qc-worker.js?v=" in page          # URL worker cung co version
    r = tech.get("/static/js/upload.js")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-cache"
    assert 'id="check-btn"' in page and page.index('id="check-btn"') < page.index('id="upload-btn"')


def test_admin_storage_settings(login):
    admin = login("admin")
    page = admin.get("/admin/settings")
    assert page.status_code == 200
    r = admin.post("/admin/settings", data={"storage_type": "local", "action": "test"})
    assert r.status_code == 200 and "thành công" in r.text
    r = admin.post("/admin/settings", data={"storage_type": "ftp", "ftp_host": "127.0.0.1", "ftp_port": "1",
                                            "ftp_user": "a", "ftp_pass": "b", "action": "test"})
    assert "thất bại" in r.text
