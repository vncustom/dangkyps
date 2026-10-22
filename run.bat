@echo off
rem Chay web Dang ky phat song.
rem   run.bat [port] [auto]      mac dinh port 8004
rem   auto = che do chay nen (Task Scheduler): khong pause, ghi log vao logs\app.log,
rem          tu chay lai sau 10 giay neu app dung bat ngo.
setlocal
cd /d "%~dp0"

set "PORT=8004"
set "AUTO="
for %%A in (%*) do call :arg %%A
goto :begin

:arg
if /i "%~1"=="auto" (set "AUTO=1") else set "PORT=%~1"
goto :eof

:begin
if not exist ".venv\Scripts\python.exe" goto :setup
goto :check

:setup
if defined AUTO (
  echo [loi] Chua co .venv - hay chay setup.bat truoc.
  exit /b 1
)
echo [setup] Chua co .venv - dang tao va cai thu vien. Khuyen dung setup.bat de cai day du.
python -m venv .venv
if errorlevel 1 goto :novenv
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :nopip
goto :check

:novenv
echo [loi] Khong tao duoc .venv. Hay chay setup.bat (tu cai Python) hoac cai Python 3.11 tro len va them vao PATH.
pause
exit /b 1

:nopip
echo [loi] Cai thu vien that bai.
pause
exit /b 1

:check
if defined AUTO goto :auto
if not exist ".env" echo [canh bao] Chua co file .env - dang dung SECRET_KEY mac dinh. Hay chay setup.bat hoac copy .env.example thanh .env va doi SECRET_KEY.
if not exist "ffmpeg\ffprobe.exe" echo [canh bao] Khong thay ffmpeg\ffprobe.exe - upload se loi neu may khong co ffmpeg trong PATH.

echo.
echo App dang chay tai http://localhost:%PORT%   Nhan Ctrl+C de dung.
echo.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port %PORT%

echo.
echo App da dung.
pause
endlocal
goto :eof

:auto
if not exist "logs" mkdir "logs"
:autoloop
for %%F in ("logs\app.log") do if exist "%%~F" if %%~zF GTR 20000000 move /y "logs\app.log" "logs\app.old.log" >nul
echo [%date% %time%] Khoi dong app, cong %PORT% >> "logs\app.log"
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port %PORT% >> "logs\app.log" 2>&1
echo [%date% %time%] App dung (ma %errorlevel%), chay lai sau 10 giay >> "logs\app.log"
ping -n 11 127.0.0.1 >nul
goto :autoloop
