# 🎬 VLC Hotkey Highlight Cutter (Python)

Một công cụ **cắt clip highlight nhanh giống DaVinci Resolve** được xây dựng bằng **Python + VLC (libVLC) + FFmpeg**.

Cho phép:
- Xem video
- Bấm phím tắt để đánh dấu **IN / OUT**
- Xuất ngay các đoạn highlight **cực nhanh**, không cần mở timeline hay phần mềm dựng nặng.

> Phù hợp cho workflow **review – cắt nhanh – tiền dựng (pre-edit)**.

---

## ✨ Tính năng chính

- ▶️ Phát video bằng **VLC (libVLC)**
- ⌨️ **Phím tắt toàn cục** (hoạt động ngay cả khi cửa sổ VLC đang focus)
- ✂️ Cắt highlight bằng mắt:
  - `I` → Đánh dấu **IN**
  - `O` → Đánh dấu **OUT** (tự động lưu highlight)
- 🎯 **Trim giống DaVinci Resolve**
  - Pre-roll (mặc định trừ `0.3s`)
  - Post-roll (mặc định cộng `0.2s`)
- ⚡ Xuất nhanh bằng **FFmpeg `-c copy`**
- 📄 Xuất:
  - File video: `HL_001.mp4`, `HL_002.mp4`, …
  - File tham chiếu `highlights.csv`
- 🧠 Undo, xem lại danh sách highlight
- 🚪 Thoát chương trình bất cứ lúc nào bằng `Q` **hoặc `Ctrl + Q`**

---

## 🖥️ Nền tảng hỗ trợ

- **Windows**
- Python **64-bit**
- VLC **64-bit** (bắt buộc)

---

## 📦 Yêu cầu cài đặt

### 1️⃣ Python
- Python **3.9+ (64-bit)**

Kiểm tra:
```bash
python -c "import platform; print(platform.architecture())"
```

### 2️⃣ VLC Media Player (64-bit)
- Tải tại: https://www.videolan.org/vlc/
- Đường dẫn mặc định:
```
C:\Program Files\VideoLAN\VLC
```

⚠️ Không dùng VLC 32-bit (`Program Files (x86)`) nếu Python là 64-bit.

### 3️⃣ FFmpeg
- Cài FFmpeg và thêm vào PATH
- Kiểm tra:
```bash
ffmpeg -version
```

### 4️⃣ Thư viện Python
```bash
pip install python-vlc keyboard
```

---

## 🚀 Cách sử dụng nhanh

### 1️⃣ Chuẩn bị
- Đặt video tên:
```
input.mp4
```
- Đặt cùng thư mục với file script.

### 2️⃣ Chạy chương trình
```bash
python cutter-video.py
```

---

## ⌨️ Phím tắt

### 🎯 Cắt highlight
| Phím | Chức năng |
|---|---|
| `I` | Đánh dấu IN |
| `O` | Đánh dấu OUT + lưu |
| `U` | Undo |
| `P` | In danh sách |
| `E` | Xuất highlight |
| `Q` | Thoát |
| `Ctrl + Q` | Thoát ngay |

### 🎛️ Điều chỉnh Roll
| Phím | Chức năng |
|---|---|
| `R` | Bật / tắt Roll |
| `[` | Giảm pre-roll |
| `]` | Tăng pre-roll |
| `-` | Giảm post-roll |
| `=` | Tăng post-roll |

---

## 📤 Kết quả xuất

```
highlights/
├── HL_001.mp4
├── HL_002.mp4
└── highlights.csv
```

---

## 📜 Giấy phép
MIT License

---

## 🙌 Ghi công
- Python
- VLC (libVLC)
- FFmpeg
