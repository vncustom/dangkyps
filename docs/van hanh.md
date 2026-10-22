# Hướng dẫn vận hành – Đăng ký phát sóng file 4K

Tài liệu cho người triển khai và vận hành trên **server chính thức** (Windows). Mô tả chức năng xem `README.md`.

Mục lục
1. [Yêu cầu server](#1-yêu-cầu-server)
2. [Chép source code sang server chính thức](#2-chép-source-code-sang-server-chính-thức)
3. [Cấu hình `.env` cho production](#3-cấu-hình-env-cho-production)
4. [Xóa dữ liệu test trước khi chạy thật](#4-xóa-dữ-liệu-test-trước-khi-chạy-thật)
5. [Chạy lần đầu và thiết lập ban đầu](#5-chạy-lần-đầu-và-thiết-lập-ban-đầu)
6. [Chạy thường trực (tự chạy lại khi khởi động máy)](#6-chạy-thường-trực)
7. [Vận hành hằng ngày](#7-vận-hành-hằng-ngày)
8. [Cập nhật phiên bản mới](#8-cập-nhật-phiên-bản-mới)
9. [Xử lý sự cố thường gặp](#9-xử-lý-sự-cố-thường-gặp)

---

## 1. Yêu cầu server

| Thành phần | Yêu cầu |
|---|---|
| Hệ điều hành | Windows (đã chạy thử trên Windows 10) |
| Python | 3.11 trở lên, có trong PATH (khi cài tick "Add python.exe to PATH") |
| ffmpeg | `ffmpeg.exe`, `ffprobe.exe` + DLL (dùng đọc thông số, làm thumbnail) |
| Ổ đĩa chứa `data\` | Còn trống **≥ 2 × file lớn nhất** (file upload nằm tạm ở `data\tmp` cho đến khi đẩy xong lên storage). Nếu nhiều người upload cùng lúc thì nhân theo số file đồng thời |
| Mạng | Mở cổng **8004** (hoặc cổng bạn chọn) trên firewall cho máy người dùng. App chạy HTTP thường, chưa có HTTPS |
| Storage | FTP của đài (host, port, user, pass, có quyền tạo thư mục và ghi/xóa file) |
| Gói thư viện | Cài bằng `pip` từ `requirements.txt` (cần mạng, hoặc xem mục 2.4 nếu server không có mạng) |

## 2. Chép source code sang server chính thức

### 2.1 Cần chép gì, không chép gì

| Chép | Không chép |
|---|---|
| `app\`, `scripts\`, `docs\`, `requirements.txt`, `run.bat`, `htv_sso_fastapi.py`, `README.md` | `.venv\` (tạo lại trên server), `__pycache__\`, `.pytest_cache\` |
| `ffmpeg\` (cả thư mục, vì không nằm trong git) | `data\` của máy dev (chứa dữ liệu test, xem mục 4) |
| `tailieu chuan bi lam app\Danh sách_user.csv` (không nằm trong git) | `.env` của máy dev (tạo `.env` mới cho server, mục 3) |
| `tests\` (tùy chọn) | file `.mp4` test |

### 2.2 Cách A – clone từ GitHub (khuyên dùng, dễ cập nhật sau này)

```powershell
cd D:\
git clone https://github.com/vncustom/dangkyps.git
cd dangkyps
```

Sau đó chép tay 2 thứ bị `.gitignore` loại: thư mục `ffmpeg\` và file CSV user (đúng đường dẫn `tailieu chuan bi lam app\Danh sách_user.csv`, hoặc để chỗ khác rồi đặt `USERS_CSV` trong `.env`).

> Nếu thay đổi code mới nhất chưa được commit/push từ máy dev thì server sẽ thiếu các thay đổi đó – commit và push trước khi clone.

### 2.3 Cách B – chép thư mục (không cần git)

Trên máy dev, nén cả thư mục project **trừ** `.venv`, `data`, `__pycache__`, `.env` rồi giải nén vào `D:\dangkyps` trên server.

### 2.4 Cài đặt tự động bằng `setup.bat` (khuyên dùng, ai cũng làm được)

Sau khi chép source (và `ffmpeg\`, file CSV nếu có), **bấm đúp `setup.bat`** (bấm Yes khi Windows hỏi quyền Administrator). File này tự làm các việc còn thiếu, việc nào đã có thì bỏ qua nên chạy lại nhiều lần được:

| Bước | Việc làm |
|---|---|
| 1 | Tìm Python 3.11+ cài cho **mọi người dùng**; chưa có thì tải và cài Python 3.12 (cần mạng) |
| 2–3 | Tạo `.venv` và cài thư viện từ `requirements.txt` (nếu có thư mục `wheels\` thì cài offline từ đó) |
| 4 | Thiếu `ffmpeg\` thì tự tải bản ffmpeg dựng sẵn (~90 MB, cần mạng) |
| 5 | Tạo `.env` với `SECRET_KEY` ngẫu nhiên (không ghi đè `.env` đã có); kiểm tra app nạp được, ffprobe chạy được, có file CSV user |
| 6 | Mở cổng 8004 trên Windows Firewall (`setup.bat 8080` để dùng cổng khác) |
| 7 | Tạo tác vụ Task Scheduler **`DangKyPhatSong`** chạy `run.bat auto` khi bật máy (tài khoản SYSTEM, không cần ai đăng nhập) rồi chạy luôn |

Cuối cùng setup in địa chỉ truy cập và các việc còn lại làm trên web (mục 5). Máy không có quyền Administrator: `setup.bat /user` (chỉ làm bước 1–5, không firewall, không tự chạy khi bật máy).

Server **không có internet**: chép sẵn `ffmpeg\`, cài Python (all users) thủ công, và trên máy có mạng chạy `python -m pip download -r requirements.txt -d wheels` rồi chép thư mục `wheels` vào thư mục app (cùng phiên bản Python / kiến trúc) – `setup.bat` sẽ tự dùng `wheels`.

Cài thủ công (nếu không dùng `setup.bat`):

```powershell
cd D:\dangkyps
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

### 2.5 Kiểm tra nhanh sau khi chép

```powershell
.\ffmpeg\ffprobe.exe -version           # ffmpeg chạy được
.\.venv\Scripts\python -m pytest -q     # (tùy chọn) toàn bộ test phải pass
```

## 3. Cấu hình `.env` cho production

```powershell
copy .env.example .env
notepad .env
```

Các giá trị **bắt buộc đổi** so với máy dev:

| Biến | Việc cần làm |
|---|---|
| `SECRET_KEY` | Chuỗi ngẫu nhiên dài, giữ bí mật. Tạo bằng: `.\.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(48))"`. Đổi key sẽ làm mọi người phải đăng nhập lại |
| `DEFAULT_PASSWORD` | Mật khẩu mặc định khi nạp CSV / admin đặt lại mật khẩu. Nên đổi khỏi giá trị mặc định |
| `FORCE_PASSWORD_CHANGE` | `1` = bắt đổi mật khẩu ở lần đăng nhập đầu của mỗi user |
| `ADMIN_USERS` | Danh sách tài khoản admin (phân cách dấu phẩy), phải có trong CSV |
| `STORAGE_TYPE=ftp`, `FTP_HOST`, `FTP_PORT`, `FTP_USER`, `FTP_PASS`, `FTP_BASE_DIR` | Trỏ tới **FTP thật** của đài (không dùng `scripts\dev_ftp.py`) |
| `HTV_SSO_SECRET`, `HTV_SSO_SERVER_URL`, `HTV_SSO_APP_URL`, `HTV_SSO_VERIFY_SLO` | Nếu dùng đăng nhập SSO HTV: secret phải **giống hệt** Dashboard SSO. Để trống secret = từ chối mọi token SSO (chỉ đăng nhập bằng user/mật khẩu) |
| `FILE_ID_START`, `TICKET_START` | Số File ID / Số phiếu bắt đầu (chỉ có tác dụng khi bảng còn trống, xem mục 4) |
| `DB_PATH` | Mặc định `data\dkps.db`. Có thể đặt sang ổ khác (thư mục `tmp`, `thumbs`, `proxy` nằm cùng thư mục với file DB) |
| `CREATE_PROXY` | Để `0` (xem trực tiếp file gốc). Chỉ bật khi máy xem bị giật |

> Lưu ý: cấu hình storage được **lưu trong CSDL** (bảng `settings`) sau lần lưu đầu tiên ở trang **Storage**. Giá trị `FTP_*` trong `.env` chỉ là giá trị khởi tạo. Nếu copy DB từ máy dev sang, storage sẽ vẫn trỏ về FTP test → vào trang Storage kiểm tra lại.

## 4. Xóa dữ liệu test trước khi chạy thật

Dữ liệu test nằm ở:

| Nơi | Chứa |
|---|---|
| `data\dkps.db` (+ `-wal`, `-shm`) | file, đánh giá, phiếu, user, vai trò đã gán, cấu hình storage |
| `data\thumbs\`, `data\proxy\` | thumbnail, bản proxy |
| `data\tmp\` | file tạm của upload (`*.part`) |
| `data\storage\` | file video nếu từng dùng storage "Thư mục cục bộ" |
| **FTP storage** | các video đã upload khi test (nằm trong các folder đơn vị, ví dụ `BanChuongtrinh\`, hoặc `files\<id>\` của bản cũ) |

> **Làm trước:** dừng app và **backup** (mục 7.2). Xóa là không phục hồi được.

### Cách A – xóa dữ liệu nghiệp vụ, GIỮ user và vai trò (khuyên dùng)

Giữ nguyên danh sách user, vai trò đã gán ở trang Người dùng, cấu hình Storage. Chỉ xóa file, đánh giá, phiếu và các file phụ.

```powershell
cd D:\dangkyps
# 1. Dừng app:  schtasks /end /tn DangKyPhatSong   (hoặc Ctrl+C nếu chạy bằng run.bat)
# 2. Chạy script, gõ XOA để xác nhận
.\.venv\Scripts\python scripts\reset_test_data.py
#    (thêm --with-local-storage nếu cũng muốn xóa data\storage; thêm --yes để bỏ bước hỏi)
```

Script xóa: file, đánh giá, phiếu, upload dở trong CSDL; thumbnail, proxy, file tạm; **đặt lại bộ đếm** để File ID / Số phiếu bắt đầu lại từ `FILE_ID_START` / `TICKET_START` trong `.env` khi khởi động lại app. Script **không** động tới user, vai trò, cấu hình storage.

### Cách B – làm sạch hoàn toàn (kể cả user và vai trò)

```powershell
# Dừng app (schtasks /end /tn DangKyPhatSong), rồi:
Remove-Item data\dkps.db, data\dkps.db-wal, data\dkps.db-shm -ErrorAction SilentlyContinue
Remove-Item data\thumbs\*, data\proxy\*, data\tmp\* -Recurse -ErrorAction SilentlyContinue
```

Khi khởi động lại, app tạo DB mới và nạp lại user từ CSV với mật khẩu mặc định. **Phải gán lại vai trò** (`ky_thuat`, `bien_tap_vien`, `thu_ky`) ở trang Người dùng và nhập lại cấu hình Storage.

### Xóa video test trên FTP storage (cả hai cách)

Script không xóa file trên FTP. Dùng FileZilla (hoặc công cụ FTP khác) vào `FTP_BASE_DIR` và xóa các folder/file test. Nếu FTP chỉ dùng cho app này, xóa sạch nội dung bên trong `FTP_BASE_DIR` (giữ lại chính thư mục gốc). Đây là thao tác tay duy nhất cần cẩn thận: **đừng xóa nhầm FTP đang chứa dữ liệu khác**.

### Kiểm tra sau khi xóa

1. Khởi động app (mục 5), đăng nhập admin.
2. Trang **1. Upload file** → bảng "Danh sách file" trống; trang **3-4. Phiếu phát sóng** trống.
3. Trang **Người dùng** vẫn còn user và vai trò (cách A).
4. Upload thử 1 file nhỏ, xác nhận File ID đầu tiên đúng bằng `FILE_ID_START`, file nằm đúng folder đơn vị trên FTP; sau đó xóa file thử này bằng nút **Xóa** (nút này cũng xóa file trên storage) – hoặc chạy lại bước Cách A nếu đã tạo phiếu thử.

## 5. Chạy lần đầu và thiết lập ban đầu

Nếu đã chạy `setup.bat` (bước 7) thì app **đã tự chạy**. Chạy tay để thử: `run.bat` (cổng mặc định 8004; `run.bat 8080` để đổi cổng; Ctrl+C để dừng).

Mở `http://<IP-server>:8004` từ máy khác để chắc chắn firewall đã mở.

Checklist lần đầu (đăng nhập bằng tài khoản admin):

- [ ] **Đổi mật khẩu** các tài khoản admin (nếu còn mật khẩu mặc định).
- [ ] Trang **Storage** → nhập thông tin FTP thật → **Kiểm tra kết nối** → **Lưu**.
- [ ] Trang **Người dùng** → gán vai trò chức năng: `ky_thuat` (upload), `bien_tap_vien` (duyệt), `thu_ky` (phiếu + in). Có thể lọc theo Ban / vai trò.
- [ ] Kiểm tra **Ban phụ trách** thấy đúng file của đơn vị mình (quy đổi `ds_ban` → đơn vị ở `DS_BAN_TO_UNIT` trong `app\config.py`; user thuộc `Ban TGĐ`, `Phat_Thanh`, `Test` chưa có đơn vị tương ứng nên không duyệt được file của đơn vị nào).
- [ ] Chạy thử trọn quy trình bằng 1 file nhỏ: Check → Upload → duyệt (Ban phụ trách + Biên tập viên) → tạo phiếu → in. Sau đó dọn dữ liệu thử (mục 4).

## 6. Chạy thường trực

`setup.bat` đã tạo tác vụ Task Scheduler `DangKyPhatSong` chạy **`run.bat <cổng> auto`** khi bật máy (trễ 30 giây cho mạng sẵn sàng). Chế độ `auto` của `run.bat`:

- không `pause`, chạy nền không cần cửa sổ;
- ghi log vào `logs\app.log` (quá 20 MB tự chuyển thành `app.old.log`);
- app dừng bất ngờ thì **tự chạy lại sau 10 giây**.

Điều khiển:

```powershell
schtasks /run /tn DangKyPhatSong      # bật
schtasks /end /tn DangKyPhatSong      # tắt (dùng khi bảo trì, backup, cập nhật, xóa dữ liệu)
schtasks /query /tn DangKyPhatSong    # xem trạng thái
```

Tự tạo tác vụ bằng tay (không dùng `setup.bat`): chạy `powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1 -Port 8004 -Dir D:\dangkyps` bằng quyền Administrator. **Không** tạo bằng `schtasks /create` mặc định vì Task Scheduler sẽ tự dừng tác vụ sau 72 giờ; script trên đã tắt giới hạn này. Python phải cài cho **mọi người dùng** (không nằm trong `C:\Users\...`), nếu không tài khoản SYSTEM không chạy được `.venv`.

Quy tắc quan trọng:
- **Chỉ chạy 1 worker** uvicorn (không thêm `--workers`). Trạng thái MD5 của file đang upload nằm trong bộ nhớ của tiến trình.
- Không dùng `--reload` trên production (khởi động lại giữa chừng sẽ làm đứt upload đang chạy).
- Nếu đặt sau **reverse proxy** (nginx/IIS…): phải tắt giới hạn dung lượng body và tắt buffer request, vì app nhận nguyên file trong một request. Với nginx: `client_max_body_size 0; proxy_request_buffering off; proxy_read_timeout 3600s; proxy_send_timeout 3600s;`.

## 7. Vận hành hằng ngày

### 7.1 Quy trình sử dụng (nhắc người dùng)

1. **Kỹ thuật**: chọn file `.mp4` → chọn **Đơn vị (ban phụ trách duyệt)** (bắt buộc) → **Check file** → xem kết quả → **Upload**. File upload xong nằm ở `<FTP_BASE_DIR>\<TenDonViKhongDau>\<tên file>`, ví dụ `BanChuyendeKhoagiao\abc.mp4`.
2. **Ban phụ trách + Biên tập viên**: vào trang duyệt, xem file, chọn Đạt / Không đạt (Không đạt bắt buộc nhận xét).
3. **Thư ký**: tạo phiếu, chọn file đã được **cả hai** đánh giá Đạt, in phiếu.

Lưu ý cho kỹ thuật: upload gửi nguyên file một lần – **không đóng tab / không để máy ngủ** trong lúc upload. Nếu mất kết nối phải Upload lại từ đầu. Mỗi lần Upload cần Check trước (MD5 lấy từ lúc Check).

### 7.2 Backup

Dừng app (hoặc chọn lúc không ai upload) rồi chép:

| Cần backup | Ghi chú |
|---|---|
| `data\dkps.db` **cùng** `dkps.db-wal` và `dkps.db-shm` (nếu có) | Chứa toàn bộ dữ liệu nghiệp vụ. Chép cả ba file; hoặc dừng app trước để SQLite gộp WAL vào file chính. Nên backup mỗi ngày |
| `.env` | Chứa `SECRET_KEY`, mật khẩu FTP |
| `tailieu chuan bi lam app\Danh sách_user.csv` | Nguồn user |
| Video trên FTP | Do bộ phận quản lý FTP backup |

`data\thumbs`, `data\proxy`, `data\tmp` không cần backup (thumbnail có thể tạo lại bằng cách upload lại; tmp là file tạm).

### 7.3 Theo dõi dung lượng

- Ổ chứa `data\`: file đang upload nằm ở `data\tmp` đến khi đẩy xong lên FTP. Ổ đầy → upload lỗi.
- Dung lượng FTP storage: tự theo dõi phía FTP.
- Khi **không có ai upload** và không có file nào trạng thái "Đang xử lý", có thể xóa mọi `*.part` trong `data\tmp` (là file tạm của lần upload/xử lý lỗi). Mỗi lần khởi động lại app, upload dở dang bị đứt cũng được tự dọn.

### 7.4 Log

Khi chạy tự động, log nằm ở `logs\app.log` (và `logs\app.old.log`); khi chạy tay bằng `run.bat` log hiện trên cửa sổ. Khi cần điều tra lỗi, đọc log quanh thời điểm lỗi; lỗi xử lý file (thumbnail, đẩy lên FTP) cũng hiện ở cột **Trạng thái** của file trên trang Upload.

### 7.5 Quản lý người dùng

- User mới/đổi ban: cập nhật file CSV rồi chạy `.\.venv\Scripts\python scripts\import_users.py` (thêm mới và cập nhật thông tin, **không** đổi mật khẩu user cũ). Thêm `--reset` để đặt lại mật khẩu mặc định cho cả user đã có – **dùng cẩn thận**.
- Quên mật khẩu: admin vào trang **Người dùng** → đặt lại mật khẩu (về `DEFAULT_PASSWORD`).
- Admin mặc định được cấp lại mỗi lần khởi động theo `ADMIN_USERS`; muốn bỏ quyền admin hẳn thì sửa `ADMIN_USERS` rồi khởi động lại.

### 7.6 Thay đổi danh mục (sửa `app\config.py`, rồi **khởi động lại app**)

| Việc | Biến |
|---|---|
| Danh sách Đơn vị (dropdown upload, tên folder trên FTP) | `UNITS` |
| Quy đổi `ds_ban` trong CSV → Đơn vị chính thức (quyền duyệt) | `DS_BAN_TO_UNIT` |
| Danh sách Thể loại và đơn vị hiển thị trên phiếu in | `THE_LOAI` |
| Kênh phát sóng, nguồn cung cấp | `KENH_SONG`, `NGUON_CUNG_CAP` |
| Yêu cầu thông số file (codec, độ phân giải, fps, audio…) | `QC_SPEC` |

Đổi **tên** đơn vị trong `UNITS` sẽ làm folder mới trên FTP khác folder cũ và các file đã upload (lưu tên đơn vị cũ) không khớp quyền duyệt theo tên mới – hạn chế đổi tên; thêm đơn vị mới thì không ảnh hưởng gì.

### 7.7 Đổi storage giữa chừng

Đổi cấu hình ở trang Storage chỉ áp dụng cho file upload **sau đó**. File đã upload vẫn nằm ở storage cũ nhưng app sẽ đọc theo cấu hình mới → phải **chép file sang storage mới giữ nguyên đường dẫn** trước khi đổi, nếu không các file cũ không xem được.

## 8. Cập nhật phiên bản mới

1. Chọn lúc không có ai upload. Dừng app (`schtasks /end /tn DangKyPhatSong`).
2. Backup (mục 7.2).
3. Lấy code mới: `git pull` (nếu clone) hoặc chép đè `app\`, `scripts\`, `docs\`, `requirements.txt`, `run.bat`, `htv_sso_fastapi.py`. **Không** chép đè `.env`, `data\`, `ffmpeg\`, file CSV.
4. Nếu `requirements.txt` thay đổi: `.\.venv\Scripts\python -m pip install -r requirements.txt`.
5. Khởi động lại app (`schtasks /run /tn DangKyPhatSong`). CSDL tự thêm cột mới khi cần (migrate tự động, không mất dữ liệu).
6. Trình duyệt người dùng tự nhận JS/CSS mới; nếu giao diện còn cũ, bảo họ Ctrl+F5.

## 9. Xử lý sự cố thường gặp

| Hiện tượng | Nguyên nhân / cách xử lý |
|---|---|
| Không ai đăng nhập được, bảng user trống | Thiếu file CSV khi chạy lần đầu → chép CSV đúng đường dẫn rồi `python scripts\import_users.py` |
| Máy khác không vào được web | Firewall chưa mở cổng (chạy lại `setup.bat`); app chưa chạy (xem `logs\app.log`, `schtasks /query /tn DangKyPhatSong`); sai IP |
| Bật máy xong app không tự chạy | Task `DangKyPhatSong` chưa có hoặc Python cài riêng cho 1 user (nằm trong `C:\Users\...`) → cài Python cho mọi người dùng rồi chạy lại `setup.bat` |
| Báo `Không tìm thấy ffprobe` khi upload | Thiếu thư mục `ffmpeg\` hoặc sai `FFMPEG_DIR` |
| File ở trạng thái **Lỗi** (cột Trạng thái hiện lý do) | Thường do FTP lỗi (sai mật khẩu, hết dung lượng, mất kết nối) hoặc file không đọc được. Sửa nguyên nhân, bấm **Xóa** file đó rồi upload lại. File tạm của lần lỗi còn ở `data\tmp` (xóa theo mục 7.3) |
| Trang Storage → Kiểm tra kết nối lỗi | Sai host/port/user/pass, FTP chặn IP server, hoặc thiếu quyền tạo thư mục/ghi |
| Folder trên FTP hiển thị ký tự lạ | Tên folder đã được bỏ dấu (`BanChuyendeKhoagiao`). Folder lỗi font còn lại là của bản cũ → xóa tay trên FTP. Tên **file** tiếng Việt vẫn có thể lỗi font tùy FTP server – nên đặt tên file không dấu |
| Upload báo `MD5 không khớp` | File bị lỗi khi truyền hoặc bị sửa sau khi Check → Check và Upload lại. Lặp lại nhiều lần → kiểm tra mạng / ổ đĩa của máy kỹ thuật |
| Upload bị đứt giữa chừng | Mất kết nối, đóng tab, máy ngủ hoặc app khởi động lại. Upload lại từ đầu (không tiếp tục được) |
| Check file báo FAIL với file HEVC | Xem cột Result từng mục. Mục "Video compression" đã nhận H.264/HEVC; FAIL thường do độ phân giải, fps, profile/level, chroma/bit depth (hiện yêu cầu 8-bit) hoặc audio. Đổi yêu cầu trong `QC_SPEC` nếu cần. Kết quả Check chỉ tham khảo – kỹ thuật quyết định có Upload không |
| Player xem file bị giật / không phát | HEVC 4K cần máy xem giải mã được (thường cần GPU). Bật **Tạo thêm bản proxy** ở trang Storage cho các file upload sau đó |
| Ban phụ trách không thấy file cần duyệt | `ds_ban` của họ chưa quy đổi được sang đúng đơn vị → bổ sung `DS_BAN_TO_UNIT`; hoặc user chưa có đúng vai trò trưởng/phó ban trong CSV |
| `database is locked` | Hiếm gặp; do có tiến trình khác mở file DB (backup đang chạy, công cụ xem SQLite). Đóng tiến trình đó |
| Cổng 8004 đã bị dùng | Có bản app khác đang chạy → dừng nó, hoặc `run.bat 8080` |
