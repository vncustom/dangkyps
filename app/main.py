from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app import config
from app.db import db_session, init_db
from app.routers import admin, auth, files, media_stream, review, tickets
from app.routers import print as print_router
from app.security import LoginRequired
from app.services.importer import ensure_admins, import_users_csv
from app.web import render


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with db_session() as conn:  # lan chay dau: tu nap user tu CSV
        if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is None and config.USERS_CSV.exists():
            import_users_csv(conn)
        ensure_admins(conn)  # moi lan khoi dong: dam bao cac tai khoan trong ADMIN_USERS co quyen admin
    yield


class NoCacheStaticFiles(StaticFiles):
    """Luon hoi lai server (ETag/304) nen sua JS/CSS la trinh duyet nhan ban moi ngay."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


app = FastAPI(title="Đăng ký phát sóng", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY, same_site="lax",
                   max_age=12 * 3600, session_cookie="dkps_session")
app.mount("/static", NoCacheStaticFiles(directory=str(config.BASE_DIR / "app" / "static")), name="static")

for module in (auth, files, review, tickets, print_router, media_stream, admin):
    app.include_router(module.router)


@app.exception_handler(LoginRequired)
async def login_required_handler(request: Request, exc: LoginRequired):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Chưa đăng nhập"}, status_code=401)
    return RedirectResponse("/password" if exc.change_password else "/login", status_code=303)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/") or request.url.path.startswith("/media/"):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    return render(request, "error.html", status_code=exc.status_code,
                  code=exc.status_code, message=exc.detail)
