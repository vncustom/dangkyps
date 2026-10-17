# Đăng ký phát sóng file 4K

Web FastAPI + SQLite cho Đài truyền hình, quy trình:

1. **Kỹ thuật** — Check file (thông số + MD5 trên file gốc) → Upload lên storage
2. **Ban phụ trách + Biên tập viên** — xem file bằng player, đánh giá Đạt / Không đạt
3. **Thư ký** — tạo phiếu đăng ký phát sóng, nạp file đã kiểm duyệt vào phiếu
4. **In phiếu** theo mẫu

## Chạy

Cách nhanh nhất: bấm đúp **`run.bat`** (hoặc `run.bat 8080` để đổi cổng). Mặc định chạy tại **http://localhost:8004**.
Nếu chưa có `.venv`, `run.bat` tự tạo và cài thư viện (cần Python 3.11+ và mạng). Dừng app bằng Ctrl+C.

Chạy tay tương đương:

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8004
```

FTP local để thử (cửa sổ khác, user `dkps` / pass `dkps`, cổng 2121):

```powershell
.\.venv\Scripts\python scripts\dev_ftp.py
```

### Cài trên máy mới (clone từ GitHub)

Các thành phần bị `.gitignore` loại nên phải chép thêm:

| Cần | Chép / cấu hình thế nào |
|---|---|
| `ffmpeg/` (ffmpeg.exe, ffprobe.exe + DLL) | Chép thư mục vào cạnh app, hoặc cài ffmpeg vào PATH, hoặc đặt `FFMPEG_DIR` trong `.env` |
| `tailieu chuan bi lam app/Danh sách_user.csv` | Chép đúng đường dẫn đó, hoặc đặt `USERS_CSV` trong `.env`. Không có CSV thì bảng user trống, không ai đăng nhập được |
| `.env` | `copy .env.example .env`, **đổi `SECRET_KEY`** |

Lần chạy đầu app tự nạp CSV (mật khẩu mặc định `14dth@HTV`, lưu dạng hash). Nạp lại thủ công:
`python scripts\import_users.py [--reset]` (`--reset` đặt lại mật khẩu mặc định cho user đã có).

Lưu ý khi triển khai:
- Mở cổng 8004 trên firewall. App chạy HTTP thường (chưa có HTTPS).
- Chỉ chạy **một worker** uvicorn (trạng thái MD5 của upload đang dở nằm trong bộ nhớ).
- `scripts\dev_ftp.py` chỉ để thử nghiệm; production trỏ **Storage** (admin) tới FTP thật của đài.

## Cấu hình (`.env`, tất cả tùy chọn)

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `SECRET_KEY` | `dev-secret-change-me` | Khóa ký phiên đăng nhập — **phải đổi** khi chạy thật |
| `ADMIN_USERS` | `admin,adminxe` | Tài khoản admin của app (xem Phân quyền) |
| `DEFAULT_PASSWORD` | `14dth@HTV` | Mật khẩu mặc định khi nạp CSV / đặt lại mật khẩu |
| `FORCE_PASSWORD_CHANGE` | `0` | `1` = bắt đổi mật khẩu ở lần đăng nhập đầu |
| `USERS_CSV`, `DB_PATH`, `FFMPEG_DIR` | xem `.env.example` | Đường dẫn file CSV user, SQLite, ffmpeg |
| `STORAGE_TYPE`, `FTP_*` | `ftp`, `127.0.0.1:2121` | Giá trị khởi tạo của cấu hình storage (sửa sau ở trang **Storage**) |
| `CREATE_PROXY` | `0` | `1` = tạo thêm bản proxy H.264 720p khi upload |
| `TICKET_START`, `FILE_ID_START` | `1` | Số phiếu / File ID bắt đầu (chỉ áp dụng khi bảng còn trống) |

## Phân quyền

- **Admin**: các tài khoản trong `ADMIN_USERS` (mặc định `admin` và `adminxe`) — được cấp quyền admin **mỗi lần app khởi động** nếu user có trong CSV/DB.
  Admin thấy tất cả, gán vai trò ở trang **Người dùng**, đặt lại mật khẩu, cấu hình **Storage**.
  Vì cấp lại khi khởi động nên bỏ tick admin của các tài khoản này trên giao diện chỉ có tác dụng đến lần restart sau; muốn bỏ hẳn thì sửa `ADMIN_USERS`.
- **Vai trò chức năng gán trong app** (trang Người dùng): `ky_thuat` (upload), `bien_tap_vien` (duyệt), `thu_ky` (phiếu + in).
- **Ban phụ trách** suy ra từ cột `ds_vai_tro` của CSV (`truong_ban`, `pho_ban`, `truong_phong`, `pho_phong`); chỉ duyệt file thuộc đơn vị (`ds_ban`) của mình.
- File được lập phiếu khi **cả** Ban phụ trách và Biên tập viên đánh giá Đạt; mỗi file chỉ gắn vào một phiếu.

## Check file (iCheck) và MD5

Ở bước Upload, kỹ thuật chọn file → **Check file**: trình duyệt (Web Worker) đọc thông số MP4 và tính **MD5 trên file gốc** ngay tại máy kỹ thuật, hiện bảng 25 mục **PASS / FAIL / INFO**.
Kỹ thuật xem kết quả rồi mới bấm **Upload** (file có mục FAIL vẫn upload được sau khi xác nhận).

- MD5 lưu vào CSDL (và in lên phiếu) là MD5 lúc Check. Khi nhận đủ file, server tính lại và **từ chối** nếu không khớp (file lỗi khi truyền hoặc bị đổi sau Check).
- Báo cáo QC được lưu kèm file; người duyệt xem lại ở trang duyệt.
- Chỉ đọc được MP4 thường (không hỗ trợ fragmented MP4).

Yêu cầu thông số HTV (tạm thời) nằm ở `QC_SPEC` trong `app/config.py`:

| Mục | Điều kiện đạt hiện tại |
|---|---|
| Video compression | `h264` (đổi `video_codec` thành `hevc` nếu muốn nhận HEVC) |
| Video profile | Main, Main 10 hoặc High (`video_profiles`) |
| Video level | ≥ 4.0 (`video_level_min`) |
| Resolution / Aspect / Frame rate | 3840 × 2160 / 16:9 / 50 fps, cadence constant |
| Scan, Chroma / bit depth | Progressive, 4:2:0 / 8-bit |
| Audio format | AAC LC (nén) **hoặc** PCM (không nén) (`audio_formats`, `audio_aac_profile`) |
| Audio sample rate / channels | 48 kHz / stereo |
| Start timecode | 00:00:00:00 |

Các mục còn lại (tên file, dung lượng, bitrate, GOP, loudness, MD5...) chỉ hiển thị (INFO).
Code: `app/static/js/qc-core.js`, `md5.js`, `qc-worker.js`. DB cũ tự được bổ sung cột QC khi khởi động lại app.

## Storage và player

Cấu hình ở **Storage** (admin): FTP hoặc thư mục cục bộ. Thêm backend mới = viết lớp kế thừa `StorageBackend` trong `app/services/storage.py`.
Upload cắt chunk 16 MB; file được staging ở `data/tmp` cho đến khi ffprobe/thumbnail xong và đã đẩy lên storage (ổ cần trống ≥ 1 file).

Player duyệt **xem trực tiếp file gốc** từ storage (HTTP Range, có -1/+1 frame, timecode, thanh kéo theo frame). HEVC 4K cần trình duyệt giải mã được (thường cần giải mã phần cứng).
Nếu máy xem bị giật hoặc không phát được, bật **Tạo thêm bản proxy** ở trang Storage (hoặc `CREATE_PROXY=1`) — file upload sau đó có thêm bản H.264 720p và player ưu tiên bản này.

## Tên đầy đủ của Thể loại

Mục "Đơn vị" trên phiếu in lấy từ `THE_LOAI` trong `app/config.py` (hiện chỉ `CT` = CHƯƠNG TRÌNH; các mã khác đang để nguyên mã — hãy điền tên đầy đủ).

## Test

```powershell
.\.venv\Scripts\python -m pytest -q
```

Gồm test API/quy trình và test code Check file (chạy chính file JS bằng Node.js — cần `node` trong PATH, thiếu thì các test đó tự bỏ qua).
