@echo off
rem Chay web Dang ky phat song. Dung: run.bat [port]   mac dinh port 8004
setlocal
cd /d "%~dp0"

set "PORT=%~1"
if "%PORT%"=="" set "PORT=8004"

if not exist ".venv\Scripts\python.exe" goto :setup
goto :check

:setup
echo [setup] Chua co .venv - dang tao va cai thu vien. Can Python va ket noi mang.
python -m venv .venv
if errorlevel 1 goto :novenv
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :nopip
goto :check

:novenv
echo [loi] Khong tao duoc .venv. Hay cai Python 3.11 tro len va them vao PATH.
pause
exit /b 1

:nopip
echo [loi] Cai thu vien that bai.
pause
exit /b 1

:check
if not exist ".env" echo [canh bao] Chua co file .env - dang dung SECRET_KEY mac dinh. Hay copy .env.example thanh .env va doi SECRET_KEY.
if not exist "ffmpeg\ffprobe.exe" echo [canh bao] Khong thay ffmpeg\ffprobe.exe - upload se loi neu may khong co ffmpeg trong PATH.

echo.
echo App dang chay tai http://localhost:%PORT%   Nhan Ctrl+C de dung.
echo.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port %PORT%

echo.
echo App da dung.
pause
endlocal
