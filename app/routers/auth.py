import sqlite3

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.db import get_db
from app.security import current_user, hash_password, verify_password
from app.web import render

router = APIRouter()


@router.get("/login")
def login_page(request: Request):
    return render(request, "login.html")


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...),
          conn: sqlite3.Connection = Depends(get_db)):
    row = conn.execute("SELECT * FROM users WHERE username = ? AND active = 1",
                       (username.strip(),)).fetchone()
    if not row or not verify_password(password, row["pw_hash"]):
        return render(request, "login.html", status_code=401, error="Sai tên đăng nhập hoặc mật khẩu",
                      username=username)
    request.session.clear()
    request.session["u"] = row["username"]
    return RedirectResponse("/password" if row["must_change_pw"] else "/", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/")
def home(request: Request, user: dict = Depends(current_user)):
    return render(request, "home.html", user)


@router.get("/password")
def password_page(request: Request, user: dict = Depends(current_user)):
    return render(request, "password.html", user)


@router.post("/password")
def change_password(request: Request, old_password: str = Form(...), new_password: str = Form(...),
                    confirm_password: str = Form(...), user: dict = Depends(current_user),
                    conn: sqlite3.Connection = Depends(get_db)):
    error = None
    if not verify_password(old_password, user["pw_hash"]):
        error = "Mật khẩu hiện tại không đúng"
    elif len(new_password) < 6:
        error = "Mật khẩu mới tối thiểu 6 ký tự"
    elif new_password != confirm_password:
        error = "Xác nhận mật khẩu không khớp"
    elif new_password == old_password:
        error = "Mật khẩu mới phải khác mật khẩu cũ"
    if error:
        return render(request, "password.html", user, status_code=400, error=error)
    conn.execute("UPDATE users SET pw_hash = ?, must_change_pw = 0 WHERE username = ?",
                 (hash_password(new_password), user["username"]))
    return render(request, "password.html", user, ok="Đã đổi mật khẩu")
