"""Jinja2 templates, filters va render helper."""
from datetime import datetime

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app import config
from app.security import has_role

templates = Jinja2Templates(directory=str(config.BASE_DIR / "app" / "templates"))

STATE_LABELS = {"chua": "Chưa duyệt", "dat": "Đạt", "khong_dat": "Không đạt"}


def _dt(value: str) -> str:
    """'2026-10-13 20:50:00' -> '20:50 13/10/2026'."""
    if not value:
        return ""
    try:
        return datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S").strftime("%H:%M %d/%m/%Y")
    except ValueError:
        return value


def _d(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return value


def _size_mb(size_bytes) -> str:
    return f"{(size_bytes or 0) / 1024 / 1024:,.2f} MB"


def asset(path: str, *also: str) -> str:
    """URL file tinh kem ?v=<mtime> de trinh duyet khong dung ban JS/CSS cu trong cache.
    Truyen them `also` khi file nay import cac file khac (vd worker)."""
    static = config.BASE_DIR / "app" / "static"
    mtimes = []
    for p in (path, *also):
        try:
            mtimes.append(int((static / p).stat().st_mtime))
        except OSError:
            pass
    return f"/static/{path}?v={max(mtimes, default=0)}"


templates.env.filters.update(dt=_dt, d=_d, size_mb=_size_mb)
templates.env.globals.update(
    has_role=has_role, STATE_LABELS=STATE_LABELS, ROLE_LABELS=config.ROLE_LABELS, asset=asset,
    password_change_enabled=lambda: config.ALLOW_PASSWORD_CHANGE,
)


def render(request: Request, name: str, user: dict | None = None, status_code: int = 200, **ctx):
    ctx.setdefault("user", user)
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)
