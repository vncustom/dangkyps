# Đăng ký phát sóng file 4K

Web FastAPI + SQLite: Upload (MD5) → Kiểm duyệt (player) → Phiếu DKPS → In phiếu.

## Chạy

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env          # chỉnh nếu cần
.\.venv\Scripts\python scripts\dev_ftp.py            # FTP local (cửa sổ 1) - user dkps/dkps, cổng 2121
.\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000   # cửa sổ 2
```

Lần chạy đầu app tự nạp `tailieu chuan bi lam app/Danh sách_user.csv` (mật khẩu mặc định `14dth@HTV`, lưu dạng hash).
Nạp lại thủ công: `python scripts\import_users.py [--reset]`. Mở http://localhost:8000.

## Phân quyền

- `admin` (user `admin`): thấy tất cả, gán vai trò ở **Người dùng**, cấu hình **Storage**.
- Vai trò gán trong app: `ky_thuat` (upload), `bien_tap_vien` (duyệt), `thu_ky` (phiếu + in).
- **Ban phụ trách** suy ra từ cột `ds_vai_tro` của CSV (`truong_ban`, `pho_ban`, `truong_phong`, `pho_phong`) và chỉ duyệt file thuộc đơn vị (`ds_ban`) của mình.
- File được lập phiếu khi **cả** Ban phụ trách và Biên tập viên đánh giá Đạt; mỗi file chỉ gắn vào một phiếu.

## Storage

Cấu hình ở **Storage** (admin): FTP hoặc thư mục cục bộ. Thêm backend mới = viết lớp kế thừa `StorageBackend` trong `app/services/storage.py`.
Upload cắt chunk 16 MB; file được staging ở `data/tmp` cho đến khi ffprobe/thumbnail/proxy xong và đã đẩy lên storage.
Player duyệt phát bản proxy H.264 720p (tạo bằng ffmpeg trong `ffmpeg/`); nếu proxy lỗi sẽ thử file gốc.

## Tên đầy đủ của Thể loại

Mục "Đơn vị" trên phiếu in lấy từ `THE_LOAI` trong `app/config.py` (hiện chỉ `CT` = CHƯƠNG TRÌNH; các mã khác đang để nguyên mã — hãy điền tên đầy đủ).

## Test

```powershell
.\.venv\Scripts\python -m pytest -q
```
