# -*- coding: utf-8 -*-
"""
htv_sso_fastapi.py - SSO Client (HTV Dashboard) cho app FastAPI "Đăng ký phát sóng"
===================================================================================
Dựa trên file mẫu htv_sso_fastapi.py của app khác, chỉnh lại để chạy song song với
đăng nhập local (bảng users dùng chung username):

  - KHÔNG tự add SessionMiddleware: dùng luôn session của app (cookie dkps_session).
  - KHÔNG đăng ký /logout: app đã có /logout riêng.
  - Token hợp lệ -> map username sang user local (resolve_user) -> request.session["u"],
    nên toàn bộ phân quyền/role phía sau giữ nguyên như đăng nhập local.

Luồng:
    /login/sso  --302-->  {SSO}/login?next={app}/api/auth/sso
    Dashboard đăng nhập xong  --POST token-->  /api/auth/sso  -> set session -> về "/"

Cách dùng (xem app/main.py):
    init_sso(app, secret_key=..., sso_server_url=..., resolve_user=ham_tra_user_local)

    # trong dependency kiểm tra đăng nhập:
    if not sso_session_valid(request): ...   # Single Log-Out

Dependencies:  pip install fastapi PyJWT httpx itsdangerous
"""
import logging
import time
from typing import Callable, Optional
from urllib.parse import quote

import httpx
import jwt
from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse

log = logging.getLogger("htv_sso")

SESSION_KEY = "sso"  # request.session["sso"] = {"sver": ..., "checked": <ts>} -> đánh dấu phiên đăng nhập qua SSO


def _extract_username(payload: dict) -> str:
    """Lấy username từ payload JWT (chịu được vài kiểu đặt tên/lồng khác nhau của Dashboard)."""
    if not isinstance(payload, dict):
        return ""
    sources = [payload]
    for key in ("user", "data", "userInfo", "user_info"):
        val = payload.get(key)
        if isinstance(val, dict):
            sources.append(val)
    for src in sources:
        for key in ("username", "sub", "user_name", "preferred_username"):
            val = src.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return ""


def init_sso(app: FastAPI, secret_key: str, sso_server_url: str,
             resolve_user: Callable[[str], Optional[str]],
             app_public_url: str = "",
             verify_slo: bool = True, slo_check_interval: int = 30,
             login_path: str = "/login", sso_login_path: str = "/login/sso"):
    """
    Gắn SSO Client vào FastAPI app (app phải có sẵn SessionMiddleware).

    Tham số:
      secret_key         : khóa bí mật CHUNG với Dashboard (giống hệt). Rỗng => từ chối mọi token.
      sso_server_url     : URL Dashboard, vd "http://10.1.1.xxx:8080". Có thể nhiều URL cách nhau dấu phẩy
                           (cùng một Dashboard, truy cập bằng IP hoặc tên miền): URL đầu tiên dùng để chuyển
                           hướng đăng nhập, check SLO sẽ thử lần lượt các URL. Rỗng => nút SSO báo chưa cấu hình.
      resolve_user       : username trong token -> username local (None nếu không có/không active).
                           Hàm sync (sẽ chạy trong threadpool).
      app_public_url     : URL app mà trình duyệt người dùng truy cập (vd "http://10.1.1.5:8004").
                           Bỏ trống => lấy từ Host của request.
      verify_slo         : True = hỏi Dashboard mỗi (interval) giây xem phiên SSO còn hiệu lực (Single Log-Out)
      slo_check_interval : giây giữa 2 lần check SLO
      login_path         : trang đăng nhập của app (nơi báo lỗi SSO: ?sso_error=<mã>)
      sso_login_path     : route bắt đầu đăng nhập SSO (nút "Đăng nhập bằng HTV SSO")
    """
    app.state.sso_secret = secret_key
    app.state.sso_servers = [u.strip().rstrip("/") for u in (sso_server_url or "").split(",") if u.strip()]
    app.state.sso_public_url = (app_public_url or "").rstrip("/")
    app.state.sso_verify_slo = verify_slo
    app.state.sso_interval = slo_check_interval

    def _fail(code: str) -> RedirectResponse:
        return RedirectResponse(url=f"{login_path}?sso_error={code}", status_code=303)

    # ---- Bắt đầu đăng nhập: chuyển sang Dashboard ----
    @app.get(sso_login_path)
    async def sso_start(request: Request):
        if not request.app.state.sso_servers or not request.app.state.sso_secret:
            return _fail("not_configured")
        return RedirectResponse(url=_login_url(request), status_code=303)

    # ---- Route nhận token từ Dashboard (POST body, hoặc GET ?token= tương thích mẫu) ----
    @app.post("/api/auth/sso")
    @app.get("/api/auth/sso")
    @app.post("/sso")
    @app.get("/sso")
    async def sso_callback(request: Request):
        token = None
        if request.method == "POST":
            token = (await request.form()).get("token")
        token = token or request.query_params.get("token")
        if not token:
            log.warning("SSO: request khong co token")
            return _fail("no_token")
        if not request.app.state.sso_secret:
            return _fail("not_configured")

        try:
            # leeway=300 bù lệch đồng hồ giữa server SSO và server app; bỏ qua lỗi "iat" do lệch giờ
            payload = jwt.decode(token, request.app.state.sso_secret, algorithms=["HS256"],
                                 leeway=300, options={"verify_iat": False})
        except jwt.ExpiredSignatureError:
            log.warning("SSO: token het han")
            return _fail("expired")
        except jwt.InvalidTokenError as e:
            log.warning("SSO: token khong hop le (%s)", e)
            return _fail("invalid")

        sso_username = _extract_username(payload)
        username = await run_in_threadpool(resolve_user, sso_username) if sso_username else None
        if not username:
            log.warning("SSO: user '%s' khong co trong he thong hoac bi khoa", sso_username)
            return _fail("no_user")

        request.session.clear()
        request.session["u"] = username
        request.session[SESSION_KEY] = {"sver": payload.get("sver"), "checked": time.time()}
        log.info("SSO: dang nhap thanh cong user '%s'", username)
        return RedirectResponse(url="/", status_code=303)


def _login_url(request: Request) -> str:
    """URL login Dashboard kèm ?next= callback (chính là /api/auth/sso của app này)."""
    state = request.app.state
    base = state.sso_public_url or str(request.base_url).rstrip("/")
    return f"{state.sso_servers[0]}/login?next={quote(base + '/api/auth/sso')}"


def is_sso_session(request: Request) -> bool:
    return bool(request.session.get(SESSION_KEY))


def _check_slo(request: Request, info: dict, username: str) -> bool:
    """Gọi Dashboard kiểm tra session_version còn hợp lệ (SLO)."""
    for server in request.app.state.sso_servers:
        try:
            resp = httpx.get(f"{server}/sso/session",
                             params={"username": username, "sver": info["sver"]}, timeout=3)
            return resp.is_success and bool(resp.json().get("valid", False))
        except (httpx.HTTPError, ValueError):
            continue  # URL này không gọi được => thử URL tiếp theo
    return True  # Không gọi được Dashboard nào => tạm tin phiên hiện tại


def sso_session_valid(request: Request) -> bool:
    """
    Dùng trong dependency đăng nhập. Phiên local luôn True.
    Phiên SSO: cứ mỗi slo_check_interval giây hỏi Dashboard; False nghĩa là đã bị đăng xuất ở Dashboard.
    Hàm này gọi mạng (blocking) nên chỉ gọi từ dependency sync (chạy trong threadpool).
    """
    info = request.session.get(SESSION_KEY)
    state = request.app.state
    if not info or not getattr(state, "sso_verify_slo", False) or info.get("sver") is None:
        return True
    if time.time() - info.get("checked", 0) <= getattr(state, "sso_interval", 30):
        return True
    if not _check_slo(request, info, request.session.get("u", "")):
        return False
    request.session[SESSION_KEY] = {**info, "checked": time.time()}
    return True
