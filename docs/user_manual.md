# Sổ Tay Vận Hành & Hướng Dẫn Sử Dụng Chi Tiết AI Live Studio v3.0

Tài liệu này cung cấp hướng dẫn toàn diện về cách thức hoạt động, cấu hình, vận hành và quản lý hệ thống livestream tự động **AI Live Studio v3.0**.

---

## 1. Nguyên Lý Hoạt Động Tổng Thể

Hệ thống hoạt động theo một luồng xử lý khép kín dạng pipeline thời gian thực:

```
[Bình luận từ TikTok/FB/YouTube]
         │
         ▼
[Guardrail #1: AI Moderation] ──(Từ tục/Spam đối thủ)──► [Chặn & Cảnh báo đỏ]
         │ (Hợp lệ)
         ▼
[Phân loại Độ ưu tiên] (P1: Giá/Chốt đơn, P2: Ship/Size, P3: Chào hỏi)
         │
         ▼
[Gom lô (Batching) trong 1.0 giây] (Nếu Autopilot Lvl 2/3)
         │
         ▼
[Xử lý nghiệp vụ & Chốt đơn SQLite] (Trừ kho, rollback nếu hết hàng)
         │
         ▼
[Truy vấn Lịch sử Memory Store] (Gợi ý bán chéo - Cross-sell)
         │
         ▼
[Sinh câu trả lời thông minh qua Gemini] (Phản hồi gộp kèm nhãn Sentiment)
         │
         ▼
[Thực thi hành động & Phát ngôn]
 ├── Cập nhật Phụ đề & Comment lên OBS Studio overlays
 ├── Tự động ẩn OBS source sản phẩm nếu tồn kho về 0 (Low-stock Safeguard)
 ├── Gửi lệnh VMC OSC điều khiển nét mặt & cử chỉ của Avatar
 └── Phát giọng nói qua Local XTTS v2 hoặc Fallback Cloud Edge-TTS (có điều âm)
         │
         ▲ (Tương tác tăng đột biến)
[Highlight Director] ──► [Cắt video clip ngắn tự động qua OBS Replay Buffer]
```

---

## 2. Các Chế Độ Tự Động Hóa (Autopilot Levels)

Hệ thống cung cấp 3 cấp độ vận hành được điều khiển trực tiếp trên Web Dashboard:

* **Level 1: AI Gợi ý & Duyệt Thủ Công (Human-in-the-loop)**:
  * Bình luận đổ về sẽ được AI phân loại và sinh câu trả lời đề xuất.
  * Câu trả lời được đưa vào danh sách **Bình luận chờ duyệt** trên Web Dashboard.
  * Người vận hành có thể sửa lại nội dung trong ô văn bản và bấm **Phát (Approve)** hoặc **Bỏ qua (Reject)**. Hệ thống chỉ phát âm thanh và đẩy lên OBS khi được duyệt.
* **Level 2: Bán Tự Động (Guarded Autopilot)**:
  * Hệ thống tự động phản hồi ngay lập tức.
  * **Cơ chế Cooldown 10 giây**: Nếu phát hiện các bình luận mang tính nhạy cảm cao (hỏi giá, chốt đơn hàng), hệ thống tự động khóa thời gian giãn cách tối thiểu 10 giây giữa các lần chốt để tránh spam hoặc trùng lặp đơn hàng của cùng một khách hàng.
* **Level 3: Tự Động Hoàn Toàn (Fully Autonomous)**:
  * Hệ thống tự động gom lô, chốt đơn, trừ kho, và phát câu trả lời ngay lập tức mà không cần bất kỳ sự can thiệp nào của con người.

---

## 3. Hướng Dẫn Cấu Hình Hệ Thống

Mọi cấu hình hoạt động của hệ thống được quản lý tập trung trong file [`.env`](file:///d:/SCMD_Tech/13.autolive/.env):

```env
# 1. Google Gemini AI API
GEMINI_API_KEY=your_gemini_api_key_here

# 2. OBS Studio WebSocket
OBS_HOST=127.0.0.1
OBS_PORT=4455
OBS_PASSWORD=your_obs_websocket_password_here

# 3. Bảo mật Web Console
WEB_TOKEN=autolive_console_secret_token

# 4. Cấu hình TTS Mặc định (Edge-TTS Cloud)
TTS_VOICE=vi-VN-HoaiMyNeural

# 5. Clone giọng nói cục bộ (Offline XTTS v2)
USE_LOCAL_XTTS=False
XTTS_SPEAKER_WAV=resources/speaker.wav
XTTS_LANGUAGE=vi

# 6. TikTok Webcast Username
TIKTOK_USERNAME=@your_shop_tiktok_id

# 7. Bảo mật Facebook Webhook
FB_VERIFY_TOKEN=fb_verify_secret
FB_APP_SECRET=your_facebook_app_secret
```

---

## 4. Hướng Dẫn Vận Hành Từng Bước

### Bước 1: Khởi chạy Ứng dụng Lõi
1. Mở PowerShell tại thư mục dự án và kích hoạt môi trường ảo:
   ```powershell
   .venv\Scripts\activate
   ```
2. Chạy ứng dụng chính:
   ```powershell
   python main.py
   ```
   *Giao diện Desktop GUI của AI Live Studio sẽ hiện lên, đồng thời tự động kích hoạt FastAPI Web Server chạy ngầm.*

### Bước 2: Truy cập Web Control Panel
Mở trình duyệt web bất kỳ và truy cập đường dẫn bảo mật cố định:
👉 **[http://127.0.0.1:8000/?token=autolive_console_secret_token](http://127.0.0.1:8000/?token=autolive_console_secret_token)**

### Bước 3: Cấu hình OBS Studio hiển thị hình ảnh sản phẩm
1. Trên **OBS Studio**, bật tính năng **Replay Buffer** (Settings -> Output -> Recording -> check *Enable Replay Buffer*).
2. Tạo một Scene tên là `Live Scene`.
3. Tạo các nguồn hiển thị hình ảnh sản phẩm và đặt tên theo đúng định dạng mã sản phẩm, ví dụ:
   - Một nguồn hình ảnh tên là `Product_SP001`.
   - Một nguồn hình ảnh tên là `Product_SP002`.
4. Tạo hai nguồn text để hiển thị phụ đề và bình luận:
   - Nguồn Text (GDI+) tên là `Subtitle_Source`.
   - Nguồn Text (GDI+) tên là `Comment_Source`.
5. Kết nối ứng dụng AI Live Studio với OBS bằng cách điền thông tin cổng/password trên GUI và bấm **Kết nối**.

### Bước 4: Chạy Live Stream & Kiểm Thử
1. **Mô phỏng comment**: Ở cột trái Web Dashboard, chọn các comment mẫu trong danh sách hoặc tự gõ rồi bấm **Gửi vào Hàng Đợi**.
2. **Theo dõi chốt đơn**: Khi bạn gửi comment chốt đơn (ví dụ: `Khách A: chốt SP001`), hệ thống sẽ:
   - Tạo đơn hàng ở bảng **Đơn hàng** trên GUI.
   - Trừ kho sản phẩm SP001 đi 1 đơn vị.
   - Nếu tồn kho về 0, hệ thống lập tức gửi lệnh ẩn nguồn ảnh `Product_SP001` trên OBS, tránh tình trạng treo biển quảng cáo sản phẩm đã hết hàng.
3. **Theo dõi ROI Dashboard**: Cuộn xuống cuối trang Web Dashboard để theo dõi các KPI bán hàng và xem hai biểu đồ combo ROI sản phẩm & doanh thu phân bổ khung giờ cập nhật tự động sau mỗi 5 giây.

---

## 5. Các Tính Năng Độc Đáo Cần Lưu Ý

* **Tránh Đè OBS overlay**: Banner voucher và trò chơi vòng quay may mắn khi tự động kích hoạt (theo timeline hoặc khi phòng live im lặng quá 30 giây) sẽ hiển thị đè lên màn hình và có bộ đếm tự động ẩn sau đúng **15 giây** để dọn sạch khung hình livestream.
* **Xác Thực Chữ Ký Webhook**: Khi triển khai cổng Facebook Webhook lên môi trường production thật, mọi payload gửi tới `/webhook/facebook` bắt buộc phải được ký bằng thuật toán HMAC-SHA256 sử dụng App Secret được cấu hình trong `.env` thì hệ thống mới tiếp nhận xử lý.
* **Đổi Tông Giọng Đọc Cảm Xúc**: AI tự động chèn nhãn cảm xúc vào lời thoại:
  - `[SENTIMENT: vui]`: Giọng đọc tự động tăng tốc (+5%) và tăng độ cao (+1Hz), Avatar VMC đổi biểu cảm tươi cười.
  - `[SENTIMENT: khó chịu]`: Giọng đọc tự động giảm tốc (-8%) và hạ trầm giọng nói (-3Hz) để xoa dịu khách, Avatar đổi biểu cảm buồn bã.
  - `[SENTIMENT: nghi ngờ]`: Giọng đọc nói chậm hơn (-3%) và hơi lên giọng nhẹ (+1Hz) để giải thích, Avatar đổi biểu cảm ngạc nhiên.
* **Custom VMC OSC Action Triggers**:
  Hệ thống gửi các thông điệp OSC đặc biệt phục vụ thiết lập Node Graph nâng cao trong Unity/VNyan:
  - **Chốt đơn thành công**: Gửi tới OSC address `/VMC/Ext/Action/CheckoutSuccess` với tham số là `[tên sản phẩm]`. Bạn có thể cấu hình Node Graph kích hoạt animation giơ tay ăn mừng, nhảy múa hoặc tung confetti.
  - **Tung Voucher**: Gửi tới address `/VMC/Ext/Action/VoucherDrop` khi Đạo diễn AI tung voucher, giúp MC ảo đổi tư thế sang chỉ tay hướng về phía góc màn hình hiển thị voucher.
  - **Kích hoạt Minigame**: Gửi tới address `/VMC/Ext/Action/MinigameStart` để MC ảo chào đón người chơi tham gia vòng quay.
  - **Sentiment Khó chịu (Xin lỗi khách)**: Gửi tới address `/VMC/Ext/Action/Apology` (tham số là thời gian `3.0` giây) để MC ảo thực hiện hành động cúi đầu xin lỗi thay vì chỉ đổi nét mặt Sorrow thông thường.
* **Auto-launch & Health-check VNyan (Kiểm tra sức khỏe Renderer)**:
  - **Tự động mở VNyan**: Bạn chỉ cần định cấu hình đường dẫn tuyệt đối tới tệp `VNyan.exe` (ví dụ: `VNYAN_EXE_PATH=C:\VNyan\VNyan.exe`) trong file `.env` hoặc chọn trực tiếp bằng nút duyệt file trong tab **Cài đặt**. Bấm nút **Bật MC ảo** trên GUI để Python tự động khởi chạy phần mềm.
  - **Giám sát sức khỏe định kỳ (Healthcheck)**: Hệ thống tự động gửi tín hiệu OSC Ping tới port `39539` mỗi 3 giây và lắng nghe gói tin phản hồi (hoặc luồng dữ liệu tracking ngược lại) trên port feedback `39540`. Nếu sau 5 giây không phát hiện tín hiệu, Web Dashboard sẽ hiện cảnh báo màu đỏ nổi bật: *"⚠️ Chưa phát hiện phần mềm Renderer 3D đang chạy. Vui lòng bật VNyan hoặc kiểm tra kết nối OSC!"* để kịp thời xử lý sự cố.
