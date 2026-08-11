# Định Hướng Kiến Trúc và Lộ Trình Nâng Cấp: AI Live Studio

Tài liệu này định hướng thiết kế kiến trúc và lộ trình phát triển để nâng cấp phần mềm **AI Live Studio** từ phiên bản MVP (desktop đơn luồng, giả lập) lên phiên bản **Production-Ready (Thương mại hóa / Chuyên nghiệp)**, hỗ trợ đa nền tảng, điều khiển MC ảo realtime và xử lý hàng ngàn tương tác đồng thời.

---

## 1. Tầm Nhìn Hệ Thống (System Vision)

Mục tiêu là biến **AI Live Studio** thành một **"Đạo diễn AI kiêm MC ảo"** hoạt động độc lập và tự động hóa 90% quy trình livestream bán hàng:
- **Tự động hóa toàn phần:** Tự nhận diện bình luận, tự kiểm tra kho hàng, tự chốt đơn, tự đổi cảnh OBS, và tự phát giọng nói/hình ảnh MC.
- **Tương tác thông minh:** AI có bộ nhớ khách hàng, cá nhân hóa cuộc hội thoại dựa trên lịch sử chat của khách.
- **Đa kênh đồng thời (Omnichannel):** Hỗ trợ livestream đồng thời lên TikTok, Facebook, YouTube và Shopee.

---

## 2. Kiến Trúc Đề Xuất Cho Phiên Bản Nâng Cấp (Target Architecture)

Để đảm bảo tính mở rộng (Scalability) và khả năng bảo trì (Maintainability), chúng ta cần chuyển đổi cấu trúc nguyên khối (Monolith) sang kiến trúc **Hướng sự kiện (Event-Driven Architecture)** và chia nhỏ thành các **Service độc lập**:

```text
       TikTok Live SDK     Facebook Webhook     YouTube Chat API
              │                   │                    │
              └───────────┬───────┴────────────────────┘
                          ▼
            ┌───────────────────────────┐
            │   Comment Collector Bus   │ (Xử lý hàng đợi comment)
            └─────────────┬─────────────┘
                          ▼
            ┌───────────────────────────┐      ┌──────────────────────────┐
            │    Central Event Broker   │ ◄───►│ Database (PostgreSQL)    │
            │      (Redis Pub/Sub)      │      │ Redis Cache (Sản phẩm)   │
            └──────┬─────────────┬──────┘      └──────────────────────────┘
                   │             │
         ┌─────────┴───┐     ┌───┴─────────┐
         ▼             ▼     ▼             ▼
  ┌─────────────┐ ┌────────┐ ┌───────────────┐ ┌──────────────────────────┐
  │  AI Brain   │ │  TTS   │ │OBS Controller │ │  Virtual MC Controller   │
  │ (Gemini/LLM)│ │Service │ │  (Websocket)  │ │ (VMC Protocol/Live2D/3D) │
  └─────────────┘ └────────┘ └───────────────┘ └──────────────────────────┘
```

### Các thành phần chính trong kiến trúc mới:

1. **Central Event Broker (Redis):** Đóng vai trò là xương sống kết nối các service. Mọi comment từ khách hàng, lệnh điều khiển OBS, hay âm thanh TTS phát đi đều được truyền tải qua các Topic/Channel của Redis.
2. **Comment Collector Services (Connectors):** Các module nhỏ chạy ngầm kết nối với API/Scraper của các nền tảng để thu thập comment thời gian thực và đẩy vào Redis.
3. **Voice Engine & TTS Queue:** Tách biệt tác vụ sinh audio TTS thành một service chạy nền độc lập để tránh hiện tượng trễ giọng đọc và hỗ trợ hàng đợi phát âm thanh (Play Queue).
4. **Virtual MC Controller:** Module đồng bộ cử chỉ khẩu hình (Lipsync) và hành động của nhân vật 2D/3D dựa trên âm thanh đầu ra của TTS hoặc hoạt hoạt ảnh định sẵn thông qua giao thức VMC (Virtual Motion Capture).

---

## 3. Lộ Trình Nâng Cấp & Phát Triển (Roadmap)

Lộ trình được chia làm 4 giai đoạn rõ rệt từ mở rộng tính năng cơ bản đến hoàn thiện sản phẩm thương mại.

### Giai đoạn 1: Kết nối Nền tảng thực tế & Tối ưu luồng tương tác (Core Expansion)
- **Tích hợp cổng kết nối Livestream:**
  - **TikTok:** Sử dụng thư viện kết nối qua TikTok Live Webcast API hoặc giao thức Protobuf để cào bình luận thời gian thực mà không cần API chính thức.
  - **Facebook:** Cấu hình Facebook Graph API Webhooks để lắng nghe bình luận trên Page Live Video.
  - **YouTube:** Sử dụng YouTube Live Chat API.
- **Hàng đợi phản hồi (Response Priority Queue):**
  - Ưu tiên trả lời trước các bình luận chứa từ khóa mua hàng (ví dụ: "chốt", "mua", "mã SP", "giá").
  - Gộp các câu hỏi trùng lặp trong thời gian ngắn để MC không bị lặp lại một câu trả lời nhiều lần.

### Giai đoạn 2: Tích hợp MC ảo & Giọng đọc cá nhân hóa (Visual AI & Voice)
- **Nhân vật ảo (Virtual Host):**
  - **Phương án 1 (Phổ thông):** Sử dụng nhân vật **Live2D** hoặc **3D Vroid** được render trực tiếp thông qua phần mềm VTube Studio hoặc Unity. Python sẽ gửi lệnh cử chỉ (vui, buồn, chỉ tay vào bảng giá) qua giao thức mạng.
  - **Phương án 2 (Cao cấp):** Sử dụng các mô hình AI Talker thời gian thực (như HeyGen API, SadTalker hoặc mô hình cục bộ LivePortrait) để tạo video cử động môi khớp với file âm thanh TTS.
- **Cá nhân hóa giọng nói (Voice Cloning):**
  - Tích hợp các dịch vụ voice cloning tiếng Việt chất lượng cao (như FPT.AI, Zalo AI, hoặc mô hình mã nguồn mở XTTS v2 chạy cục bộ) để tạo ra giọng nói tự nhiên, có cảm xúc bán hàng thay vì giọng đọc máy.

### Giai đoạn 3: Đạo diễn AI & Kịch bản tự động (Autopilot Script)
- **Bộ nhớ khách hàng dài hạn (Customer Memory Store):**
  - Sử dụng cơ sở dữ liệu Vector (như ChromaDB hoặc FAISS) lưu trữ thông tin sở thích, lịch sử mua hàng của khách. Ví dụ: Khi khách hàng "Minh" quay lại livestream hỏi, AI sẽ tự chào: *"A, chào anh Minh, hôm trước chiếc áo thun SP001 anh mặc có vừa vặn không ạ?"*.
- **Kịch bản động và Đạo diễn tự động (AI Director):**
  - Phát hiện thời điểm livestream bị giảm tương tác (ví dụ: 1 phút không có comment mới).
  - Tự động kích hoạt đổi scene sang minigame, tung voucher giảm giá hoặc đổi background camera.
  - Phát các câu hỏi kích thích tương tác: *"Mọi người ơi, thả tim cho em lên 10k tim em tung voucher 50% nhé!"*.

### Giai đoạn 4: Quản trị mạng & Thương mại hóa (Enterprise Web Dashboard)
- **Chuyển đổi giao diện sang Web-based (SaaS):**
  - Chuyển từ ứng dụng PySide6 Desktop sang giao diện Web sử dụng **Next.js (Frontend)** và **FastAPI/Go (Backend)**.
  - Cho phép người dùng cấu hình chiến dịch livestream, quản lý kho sản phẩm, thiết lập giọng nói và xem thống kê từ mọi thiết bị qua trình duyệt web.
- **Báo cáo và Phân tích chuyên sâu (Analytics Dashboard):**
  - Biểu đồ thời gian thực về số lượng viewer, tốc độ comment/phút.
  - Thống kê tỷ lệ chuyển đổi đơn hàng trực tiếp từ luồng chat livestream.

---

## 4. Bảng So Sánh Công Nghệ Đề Xuất Cho Việc Nâng Cấp

| Module | Công nghệ hiện tại (MVP) | Công nghệ đề xuất (Production) | Lý do nâng cấp |
| :--- | :--- | :--- | :--- |
| **Cơ sở dữ liệu** | SQLite | PostgreSQL + Redis | Hỗ trợ ghi đọc đồng thời cao, lưu cache sản phẩm và phiên chat khách hàng. |
| **Xử lý AI (LLM)** | Gemini Flash API / Mock | Gemini Pro API + VectorDB (ChromaDB) | Đọc hiểu ngữ cảnh sâu hơn, truy xuất bộ nhớ khách hàng dài hạn cực nhanh. |
| **Giao diện (UI)** | PySide6 Desktop | Next.js + TailwindCSS + WebSockets | Dễ dàng triển khai dưới dạng dịch vụ Cloud (SaaS), quản trị từ xa qua điện thoại/máy tính. |
| **Giao tiếp MC** | Phát file audio qua Pygame | VMC Protocol + VTube Studio / Unity | Tạo hình ảnh MC chuyển động 2D/3D sống động khớp khẩu hình miệng (Lipsync). |
| **Hàng đợi (Queue)** | Python Threading Queue | Celery + Redis | Đảm bảo không mất mát dữ liệu sự kiện khi có hàng ngàn bình luận đổ về cùng lúc. |

---

## 5. Các Nguyên Tắc An Toàn & Bảo Mật (AI Guardrails)

Khi đưa hệ thống tự động vào livestream thực tế, chúng ta bắt buộc phải cấu hình các bộ lọc an toàn:
1. **Bộ lọc từ ngữ thô tục & Spam (Moderation):** Sử dụng mô hình phân loại văn bản (Text Classification) cục bộ hoặc Regex nâng cao để loại bỏ bình luận tục tĩu, công kích chính trị hoặc spam link từ đối thủ trước khi gửi vào LLM.
2. **Hạn chế tần suất phát TTS (Rate Limiting):** Đảm bảo khoảng cách tối thiểu giữa các lần phát giọng đọc là 3 - 5 giây để tránh việc MC ảo nói chồng chéo lên nhau hoặc phát liên tục không ngừng nghỉ.
3. **Cơ chế Can thiệp thủ công (Human-in-the-loop):** Giao diện quản trị của người vận hành livestream luôn có nút **"Mute MC"** (Tắt tiếng MC) và **"Override System"** để người thật có thể nói trực tiếp qua mic hoặc bấm nút hủy câu trả lời của AI ngay lập tức nếu phát hiện AI trả lời sai sót.
