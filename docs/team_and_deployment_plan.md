# Đề Xuất Đội Ngũ Coder & Kế Hoạch Triển Khai
## Dự án: Nâng cấp AI Live Studio (MVP → Production-Ready)

*Người lập: Kỹ sư R&D — Cải tiến & Phát triển tính năng phần mềm*
*Căn cứ: `docs/architecture_and_roadmap.md`*

---

## 1. Đánh giá nhanh hiện trạng (Baseline)

Codebase hiện tại là một ứng dụng desktop đơn khối (~490 dòng Python):

| File | Vai trò hiện tại | Giới hạn cần khắc phục |
|---|---|---|
| `main.py`, `src/gui/main_window.py` | UI PySide6 desktop | Đơn luồng, không scale, không truy cập từ xa |
| `src/ai_brain.py` | Gọi Gemini Flash / mock | Chưa có bộ nhớ khách hàng, chưa có moderation |
| `src/database.py` | SQLite | Không chịu được ghi/đọc đồng thời cao |
| `src/obs_client.py` | Điều khiển OBS qua websocket | Chưa có cơ chế hàng đợi lệnh |
| `src/tts_engine.py` + Pygame | Phát audio TTS | Chưa có rate-limit, chưa có lipsync |
| Không có kết nối nền tảng thật (TikTok/FB/YT) | — | Toàn bộ Giai đoạn 1 chưa tồn tại |

→ Khoảng cách giữa hiện trạng và kiến trúc mục tiêu (Event-Driven, đa service) là rất lớn. Đây là cơ sở để đề xuất quy mô đội ngũ bên dưới.

---

## 2. Cơ Cấu Đội Ngũ Đề Xuất

Đề xuất mô hình **Squad nhỏ, đa năng**, 6–7 người, chia theo trục kiến trúc (Event Broker → Connectors → AI/Voice → MC ảo → Web) thay vì theo phòng ban, để một người có thể theo một service xuyên suốt từ Giai đoạn 1 đến Giai đoạn 4.

| # | Vai trò | Số lượng | Trách nhiệm chính | Bám theo Giai đoạn |
|---|---|---|---|---|
| 1 | **Tech Lead / Solution Architect** | 1 | Thiết kế Event Broker (Redis), chuẩn hoá schema message, review kiến trúc, điều phối kỹ thuật giữa các service | 1 → 4 (xuyên suốt) |
| 2 | **Backend Engineer – Platform Connectors** | 1–2 | Xây Comment Collector cho TikTok (scrape/protobuf), Facebook (Graph API Webhook), YouTube (Live Chat API); Response Priority Queue | 1 |
| 3 | **Backend Engineer – Core Services** | 1 | Migration SQLite → PostgreSQL + Redis Cache, Celery task queue, API nội bộ giữa các service | 1, 3 |
| 4 | **AI/ML Engineer** | 1 | Nâng cấp AI Brain (Gemini Pro), tích hợp VectorDB (ChromaDB/FAISS) cho bộ nhớ khách hàng, xây bộ lọc moderation (spam/tục tĩu), AI Director (kịch bản tự động) | 3 |
| 5 | **Voice & Virtual MC Engineer** | 1 | Tích hợp Voice Cloning (XTTS v2 / FPT.AI / Zalo AI), VMC Protocol để điều khiển Live2D/3D qua VTube Studio hoặc Unity, đồng bộ lipsync | 2 |
| 6 | **Frontend Engineer – Web Dashboard** | 1 | Chuyển UI PySide6 → Next.js + TailwindCSS + WebSocket, dựng Analytics Dashboard | 4 |
| 7 | **DevOps / QA (kiêm nhiệm hoặc part-time)** | 1 | Docker hoá service, CI/CD, giám sát Redis/Celery, viết test tự động, kiểm thử tải (ngàn comment/giây) | 1 → 4 (xuyên suốt) |

**Quy mô tối thiểu để chạy song song:** 6 người full-time (1 Tech Lead, 2 Backend, 1 AI/ML, 1 Voice/MC, 1 Frontend) + 1 DevOps/QA bán thời gian.
Nếu ngân sách hạn chế, có thể gộp vai trò #3 và #6 vào cùng một Backend/Fullstack Engineer, đưa quy mô xuống **4–5 người**, nhưng sẽ kéo dài timeline Giai đoạn 4.

---

## 3. Phân Bổ Theo Giai Đoạn (Roadmap Thực Thi)

### Giai đoạn 1 — Kết nối nền tảng thực & Hàng đợi ưu tiên (≈ 4–6 tuần)
**Nhân sự:** Tech Lead, Backend Connectors (x1–2), DevOps/QA
- [ ] Dựng Redis Pub/Sub làm Central Event Broker, định nghĩa chuẩn message (JSON schema cho `comment`, `order_intent`, `obs_command`).
- [ ] Module `tiktok_connector`: cào comment realtime (Protobuf/Webcast), đẩy vào Redis topic `comments.tiktok`.
- [ ] Module `facebook_connector`: đăng ký Graph API Webhook cho Page Live Video.
- [ ] Module `youtube_connector`: tích hợp YouTube Live Chat API polling/streaming.
- [ ] Response Priority Queue: gắn nhãn comment theo từ khóa mua hàng ("chốt", "mua", "giá"), gộp câu hỏi trùng lặp trong cửa sổ thời gian ngắn.
- [ ] Migrate `database.py` SQLite → PostgreSQL, thêm Redis Cache cho dữ liệu sản phẩm.

**Definition of Done:** Một livestream thật trên nhất 1 nền tảng đẩy comment realtime vào hệ thống qua Redis, hiển thị được trên log/dashboard tạm thời.

### Giai đoạn 2 — MC ảo & Giọng đọc cá nhân hóa (≈ 4–6 tuần)
**Nhân sự:** Voice & Virtual MC Engineer, Tech Lead (hỗ trợ giao thức), DevOps/QA
- [ ] Đánh giá & chọn phương án: VTube Studio (Live2D, chi phí thấp, triển khai nhanh) vs LivePortrait/HeyGen API (cao cấp, chi phí/độ trễ cao hơn) — đề xuất bắt đầu bằng VTube Studio để MVP hóa nhanh.
- [ ] Viết bridge Python → VMC Protocol gửi lệnh cử chỉ (vui, chỉ tay bảng giá...).
- [ ] Thay Pygame bằng Voice Engine dạng service riêng, hỗ trợ hàng đợi phát âm (Play Queue).
- [ ] Tích hợp voice cloning tiếng Việt (ưu tiên XTTS v2 chạy cục bộ để tránh phụ thuộc API ngoài; fallback FPT.AI/Zalo AI cho tốc độ).
- [ ] Áp rate-limit tối thiểu 3–5 giây giữa các lượt phát TTS (Guardrail #2 trong tài liệu gốc).

**Definition of Done:** MC ảo phát giọng nói theo comment thật, môi khớp âm thanh cơ bản, không chồng tiếng.

### Giai đoạn 3 — Đạo diễn AI & Kịch bản tự động (≈ 5–7 tuần)
**Nhân sự:** AI/ML Engineer, Backend Core Services, Tech Lead
- [ ] Nâng cấp `ai_brain.py`: chuyển sang Gemini Pro, thiết kế prompt có ngữ cảnh dài.
- [ ] Customer Memory Store: dựng ChromaDB/FAISS lưu lịch sử & sở thích khách hàng, truy xuất theo `user_id` nền tảng.
- [ ] Bộ lọc moderation (spam, từ ngữ thô tục, spam link đối thủ) chạy trước khi vào LLM — có thể dùng model classification nhẹ cục bộ + regex nâng cao.
- [ ] AI Director: cơ chế phát hiện "im lặng" (không có comment mới > 1 phút) → tự động trigger đổi scene OBS / tung voucher / câu hỏi kích thích tương tác.
- [ ] Celery + Redis thay Python Threading Queue để đảm bảo không mất sự kiện khi tải cao.

**Definition of Done:** Hệ thống tự chào khách quay lại bằng dữ liệu lịch sử, tự kích hoạt kịch bản khi tương tác giảm, không cần người vận hành can thiệp trong kịch bản chuẩn.

### Giai đoạn 4 — Web Dashboard & Thương mại hóa (≈ 6–8 tuần)
**Nhân sự:** Frontend Engineer, Backend Core Services, DevOps/QA, Tech Lead
- [ ] Backend API: FastAPI (khuyến nghị dùng chung ngôn ngữ Python với AI Brain để giảm chi phí chuyển đổi ngữ cảnh, thay vì Go, trừ khi cần hiệu năng cực cao).
- [ ] Frontend: Next.js + TailwindCSS + WebSocket, các màn hình: cấu hình chiến dịch, quản lý kho, thiết lập giọng nói, dashboard viewer/comment realtime.
- [ ] Analytics Dashboard: biểu đồ viewer, tốc độ comment/phút, tỷ lệ chuyển đổi đơn hàng.
- [ ] **Human-in-the-loop UI** (Guardrail #3): nút "Mute MC" và "Override System" phải có mặt ngay từ bản dashboard đầu tiên, không để tới cuối giai đoạn.
- [ ] Đóng gói Docker Compose / CI-CD cho triển khai SaaS.

**Definition of Done:** Người vận hành cấu hình và giám sát toàn bộ livestream từ trình duyệt, có nút can thiệp thủ công hoạt động tức thời.

---

## 4. Timeline Tổng Quan (Ước tính)

```
Tuần:        1   2   3   4   5   6   7   8   9   10  11  12  13  14  15  16  17  18  19  20  21  22
GĐ1 Connect  ███████████
GĐ2 MC/Voice         ███████████
GĐ3 AI Dir.                      ███████████████
GĐ4 Web SaaS                                       ███████████████████
```
- Giai đoạn 2 có thể chạy **song song** với nửa sau Giai đoạn 1 (đội khác nhau).
- Giai đoạn 4 nên bắt đầu thiết kế API/UX từ giữa Giai đoạn 3 để rút ngắn tổng thời gian.
- Tổng thời gian dự kiến: **~5–5.5 tháng** với đội 6–7 người song song hóa hợp lý; **~7–8 tháng** nếu chạy tuần tự với đội 4–5 người.

---

## 5. Rủi Ro Kỹ Thuật Cần Lưu Ý Khi Phân Task

| Rủi ro | Ảnh hưởng | Đề xuất giảm thiểu |
|---|---|---|
| TikTok không có API chính thức cho comment | Connector dễ gãy khi TikTok đổi protobuf | Tách connector thành module độc lập, dễ thay thế; thêm cơ chế retry/fallback polling |
| Độ trễ pipeline Comment → LLM → TTS → Lipsync | MC trả lời chậm, mất tính "live" | Đặt SLA rõ ràng cho từng service (đo bằng Redis timestamp), ưu tiên tối ưu bước chậm nhất trước |
| Chi phí API (Gemini Pro, HeyGen, FPT.AI...) | Vượt ngân sách khi scale nhiều phiên livestream | Ưu tiên các phương án cục bộ (XTTS v2, VTube Studio) cho MVP, chỉ nâng cấp API cao cấp khi có doanh thu |
| Moderation bỏ sót nội dung nhạy cảm | Rủi ro thương hiệu khi phát sai trên live | Bắt buộc có "Mute MC" hoạt động **trước** khi go-live thật, không để đây là tính năng optional |

---

## 6. Đề Xuất Bước Tiếp Theo

1. Chốt quy mô đội (6–7 người hay rút gọn 4–5 người) dựa trên ngân sách.
2. Tuyển/phân công Tech Lead trước tiên — người này cần định nghĩa chuẩn message Redis trước khi các connector khác bắt đầu code, để tránh làm lại.
3. Bắt đầu Giai đoạn 1 với 1 nền tảng livestream duy nhất (đề xuất Facebook, vì có Webhook chính thức, ít rủi ro bị chặn hơn TikTok) để có bản demo nhanh nhất, sau đó mở rộng.
4. Review kiến trúc theo checkpoint cuối mỗi giai đoạn trước khi cấp phép sang giai đoạn kế tiếp.
