@echo off
rem ============================================================
rem  CAI DAT APP DANG KY PHAT SONG TREN MAY MOI
rem  Chi can bam dup file nay (hoac chuot phai - Run as administrator).
rem  Chay lai nhieu lan duoc: phan nao da co thi bo qua.
rem
rem  setup.bat [port]     mac dinh port 8004
rem  setup.bat /user      che do khong can quyen Administrator: chi cai Python/thu vien/ffmpeg/.env,
rem                       KHONG mo firewall, KHONG tao tu dong chay khi bat may
rem ============================================================
setlocal EnableExtensions
title Cai dat Dang ky phat song
cd /d "%~dp0"

set "PORT=8004"
set "NOADMIN="
for %%A in (%*) do call :arg %%A
goto :begin

:arg
if /i "%~1"=="/user" (set "NOADMIN=1") else set "PORT=%~1"
goto :eof

:begin
if defined NOADMIN goto :start
net session >nul 2>&1
if not errorlevel 1 goto :start
echo Dang xin quyen Administrator ^(bam Yes o cua so hien ra^)...
powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '%PORT%' -Verb RunAs"
exit /b

:start
echo.
echo ============================================================
echo   CAI DAT APP DANG KY PHAT SONG
echo   Thu muc: %~dp0
echo ============================================================
echo.

rem ---------- 1. Python ----------
echo [1/7] Kiem tra Python 3.11 tro len...
set "PY="
for /d %%D in ("%ProgramFiles%\Python3*") do call :try_python "%%D\python.exe"
if not defined PY for /f "delims=" %%P in ('where python 2^>nul') do call :try_python "%%P"
if defined PY goto :py_ok
if defined NOADMIN goto :nopython
echo       Chua co Python - dang tai va cai Python 3.12 ^(can ket noi mang, mat vai phut^)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_python.ps1"
if errorlevel 1 goto :nopython
for /d %%D in ("%ProgramFiles%\Python3*") do call :try_python "%%D\python.exe"
if not defined PY goto :nopython
:py_ok
echo       OK: %PY%

rem ---------- 2. Moi truong ao .venv ----------
echo [2/7] Tao moi truong Python ^(.venv^)...
set "VPY=.venv\Scripts\python.exe"
if not exist "%VPY%" goto :mkvenv
"%VPY%" -c "import sys" >nul 2>&1
if errorlevel 1 goto :rmvenv
if defined NOADMIN goto :venv_ok
findstr /i /c:"\Users\" ".venv\pyvenv.cfg" >nul 2>&1
if not errorlevel 1 goto :rmvenv
goto :venv_ok
:rmvenv
echo       .venv cu khong dung duoc tren may nay - tao lai.
rmdir /s /q ".venv"
:mkvenv
"%PY%" -m venv .venv
if errorlevel 1 goto :fail_venv
:venv_ok
echo       OK

rem ---------- 3. Thu vien ----------
echo [3/7] Cai thu vien Python ^(can mang, hoac thu muc wheels neu may khong co mang^)...
if exist "wheels" goto :pip_offline
"%VPY%" -m pip install -r requirements.txt
goto :pip_done
:pip_offline
"%VPY%" -m pip install --no-index --find-links wheels -r requirements.txt
:pip_done
if errorlevel 1 goto :fail_pip
echo       OK

rem ---------- 4. ffmpeg ----------
echo [4/7] Kiem tra ffmpeg...
"%VPY%" scripts\setup_helper.py ffmpeg

rem ---------- 5. .env va du lieu ----------
echo [5/7] Tao file cau hinh .env...
"%VPY%" scripts\setup_helper.py env
"%VPY%" scripts\setup_helper.py check
if errorlevel 1 goto :fail_check

if defined NOADMIN goto :skip_admin

rem ---------- 6. Firewall ----------
echo [6/7] Mo cong %PORT% tren Windows Firewall...
netsh advfirewall firewall delete rule name="DangKyPhatSong" >nul 2>&1
netsh advfirewall firewall add rule name="DangKyPhatSong" dir=in action=allow protocol=TCP localport=%PORT% >nul
if errorlevel 1 (echo       [canh bao] Khong mo duoc firewall - hay mo cong %PORT% thu cong.) else echo       OK

rem ---------- 7. Tu chay khi bat may ----------
echo [7/7] Dat app tu chay khi bat may ^(Task Scheduler: DangKyPhatSong^)...
schtasks /end /tn "DangKyPhatSong" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\register_task.ps1" -Port %PORT% -Dir "%~dp0"
if errorlevel 1 goto :fail_task
schtasks /run /tn "DangKyPhatSong" >nul 2>&1
echo       OK - app dang khoi dong.
goto :done

:skip_admin
echo [6/7] Bo qua firewall ^(che do /user^)
echo [7/7] Bo qua tu chay khi bat may ^(che do /user^). De chay thu: run.bat

:done
echo.
echo ============================================================
echo   CAI DAT XONG
echo ============================================================
echo   Dia chi app:  http://localhost:%PORT%
for /f "tokens=2 delims=: " %%a in ('ipconfig ^| findstr /c:"IPv4"') do echo   Tu may khac:  http://%%a:%PORT%
echo.
echo   Viec con lai ^(lam tren web, dang nhap admin^):
echo     - Trang Storage: nhap FTP that, bam Kiem tra ket noi, bam Luu
echo     - Trang Nguoi dung: gan vai tro ky_thuat / bien_tap_vien / thu_ky
echo   Chi tiet: docs\van hanh.md
echo   Log app: logs\app.log     Dung app: schtasks /end /tn DangKyPhatSong
echo ============================================================
echo.
pause
exit /b 0

:try_python
if defined PY goto :eof
if not exist "%~1" goto :eof
if not defined NOADMIN echo %~1| findstr /i /c:"\Users\" >nul && goto :eof
echo %~1| findstr /i /c:"WindowsApps" >nul && goto :eof
"%~1" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 goto :eof
set "PY=%~1"
goto :eof

:nopython
echo.
echo [LOI] Khong tim thay / khong cai duoc Python 3.11 tro len.
echo       Hay cai tay tu https://www.python.org/downloads/ ^(chon "Install for all users"
echo       va tick "Add python.exe to PATH"^), roi chay lai setup.bat.
goto :fail

:fail_venv
echo [LOI] Khong tao duoc moi truong .venv.
goto :fail

:fail_pip
echo [LOI] Cai thu vien that bai. Kiem tra ket noi mang. May khong co mang: xem docs\van hanh.md muc 2.4 ^(thu muc wheels^).
goto :fail

:fail_check
echo [LOI] App khong khoi dong duoc ^(xem thong bao phia tren^).
goto :fail

:fail_task
echo [LOI] Khong tao duoc tac vu tu chay khi bat may. Co the chay thu cong bang run.bat.
goto :fail

:fail
echo.
echo CAI DAT CHUA HOAN TAT. Chup man hinh nay gui nguoi ho tro neu can.
pause
exit /b 1
