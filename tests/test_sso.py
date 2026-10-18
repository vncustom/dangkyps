import time

import jwt
from fastapi.testclient import TestClient

from app.db import db_session
from app.main import app
from tests.conftest import PASSWORD, SSO_SECRET, make_client


def _token(username="tech1", secret=SSO_SECRET, **extra):
    payload = {"username": username, "sver": 1, "exp": int(time.time()) + 300, **extra}
    return jwt.encode(payload, secret, algorithm="HS256")


def _client():
    return TestClient(app, follow_redirects=False)


def test_login_page_has_sso_button():
    r = _client().get("/login")
    assert r.status_code == 200 and "/login/sso" in r.text


def test_sso_start_redirects_to_dashboard():
    r = _client().get("/login/sso")
    assert r.status_code == 303
    assert r.headers["location"].startswith("http://dashboard.test:8080/login?next=")
    assert r.headers["location"].endswith("/login?next=http%3A//testserver/api/auth/sso")


def test_sso_login_ok():
    c = _client()
    r = c.post("/api/auth/sso", data={"token": _token("tech1")})
    assert (r.status_code, r.headers["location"]) == (303, "/")
    assert c.get("/files").status_code == 200


def test_sso_session_not_forced_to_change_password():
    with db_session() as conn:
        conn.execute("UPDATE users SET must_change_pw = 1 WHERE username = 'tech1'")
    try:
        c = _client()
        c.post("/api/auth/sso", data={"token": _token("tech1")})
        assert c.get("/files").status_code == 200
        local = make_client()  # dang nhap local thi van bi ep
        local.post("/login", data={"username": "tech1", "password": PASSWORD})
        assert local.get("/files").headers["location"] == "/password"
    finally:
        with db_session() as conn:
            conn.execute("UPDATE users SET must_change_pw = 0 WHERE username = 'tech1'")


def test_sso_username_case_insensitive():
    c = _client()
    c.post("/api/auth/sso", data={"token": _token("TECH1")})
    assert c.get("/files").status_code == 200


def test_sso_rejects_bad_tokens():
    for token, code in [(_token(secret="sai-secret-sai-secret-sai-secret-xx"), "invalid"),
                        (_token(exp=int(time.time()) - 3600), "expired"),
                        (_token("khong_ton_tai"), "no_user"),
                        ("", "no_token")]:
        c = _client()
        r = c.post("/api/auth/sso", data={"token": token})
        assert r.headers["location"] == f"/login?sso_error={code}", code
        assert c.get("/files").status_code == 303  # van chua dang nhap


def test_sso_error_shown_on_login_page():
    assert "hết hạn" in _client().get("/login?sso_error=expired").text


def test_sso_slo_logout_when_dashboard_says_invalid(monkeypatch):
    import htv_sso_fastapi as sso
    c = _client()
    c.post("/api/auth/sso", data={"token": _token("tech1")})
    monkeypatch.setattr(app.state, "sso_interval", -1)  # ep check moi request
    monkeypatch.setattr(sso, "_check_slo", lambda *a: False)
    assert c.get("/files").status_code == 303
    monkeypatch.setattr(sso, "_check_slo", lambda *a: True)
    assert c.get("/files").status_code == 303  # session da bi clear, phai dang nhap lai


def test_sso_multiple_dashboard_urls(monkeypatch):
    import htv_sso_fastapi as sso
    monkeypatch.setattr(app.state, "sso_servers", ["http://10.1.1.215", "http://ttphtl.htv.com.vn"])
    r = _client().get("/login/sso")
    assert r.headers["location"].startswith("http://10.1.1.215/login?next=")  # URL dau tien dung de chuyen huong

    called = []

    def fake_get(url, **kw):
        called.append(url)
        if "10.1.1.215" in url:
            raise sso.httpx.ConnectError("down")

        class R:
            is_success = True
            def json(self): return {"valid": True}
        return R()

    monkeypatch.setattr(sso.httpx, "get", fake_get)
    c = _client()
    c.post("/api/auth/sso", data={"token": _token("tech1")})
    monkeypatch.setattr(app.state, "sso_interval", -1)
    assert c.get("/files").status_code == 200
    assert called == ["http://10.1.1.215/sso/session", "http://ttphtl.htv.com.vn/sso/session"]
