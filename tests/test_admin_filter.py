import re


def _usernames(html: str) -> set[str]:
    return set(re.findall(r'action="/admin/users/([^/"]+)/roles"', html))


def _get(login, **params):
    r = login("admin").get("/admin/users", params=params)
    assert r.status_code == 200
    return r.text


def test_filter_by_ban(login):
    assert {"tech1", "btv1", "bpA", "sec1", "nobody"} <= _usernames(_get(login, ban="Ban CT"))
    names = _usernames(_get(login, ban="TT Tin Tức"))
    assert names == {"bpB"}
    assert _usernames(_get(login, ban="__none__")) == {"admin"}  # admin khong co ban


def test_filter_by_role(login):
    assert _usernames(_get(login, role="ky_thuat")) == {"tech1"}
    assert _usernames(_get(login, role="admin")) == {"admin"}
    assert _usernames(_get(login, role="ban_phu_trach")) == {"bpA", "bpB"}
    none_role = _usernames(_get(login, role="__none__"))
    assert "nobody" in none_role and not (none_role & {"admin", "tech1", "btv1", "sec1", "bpA", "bpB"})


def test_filter_combined_and_options(login):
    html = _get(login, ban="Ban CT", role="ban_phu_trach")
    assert _usernames(html) == {"bpA"}
    assert '<option value="Ban CT" selected>' in html and '<option value="TT Tin Tức" >' in html


def _roles(username):
    from app.db import db_session
    with db_session() as conn:
        return {r["role"] for r in conn.execute("SELECT role FROM user_roles WHERE username = ?", (username,))}


def test_bulk_save_roles(login):
    import json
    c = login("admin")
    try:
        r = c.post("/admin/users/roles-bulk", data={
            "changes": json.dumps({"btv1": ["bien_tap_vien", "thu_ky", "hack"], "sec1": [], "admin": [], "ghost": ["thu_ky"]}),
            "back": "ban=Ban+A&role=thu_ky&msg=x&evil=1"})
        assert r.status_code == 303
        loc = r.headers["location"]
        assert loc.startswith("/admin/users?ban=Ban+A&role=thu_ky&msg=") and "evil" not in loc and "x&" not in loc
        assert _roles("btv1") == {"bien_tap_vien", "thu_ky"}  # role la bi bo
        assert _roles("sec1") == set()
        assert "admin" in _roles("admin")  # khong tu go quyen admin cua minh
        assert c.post("/admin/users/roles-bulk", data={"changes": "khong-phai-json"}).status_code == 400
    finally:
        from app.db import db_session
        with db_session() as conn:
            conn.execute("DELETE FROM user_roles WHERE username IN ('btv1','sec1')")
            conn.executemany("INSERT INTO user_roles(username, role) VALUES (?, ?)",
                             [("btv1", "bien_tap_vien"), ("sec1", "thu_ky")])


def test_bulk_save_requires_admin(login):
    assert login("tech1").post("/admin/users/roles-bulk", data={"changes": "{}"}).status_code == 403
