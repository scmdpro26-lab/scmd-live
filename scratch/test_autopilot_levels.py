import sys
import os
import time
import asyncio

# Thêm thư mục gốc vào PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.database as db
from src.ai_brain import AIBrain
from src.tts_engine import TTSEngine
from src.obs_client import OBSClient
from src.priority_queue import PriorityQueueProcessor

# Mock OBS
class MockOBSClient(OBSClient):
    def __init__(self):
        self.is_connected = True
        self.client = None
        self.texts = {}

    def update_text_source(self, source_name: str, text: str):
        self.texts[source_name] = text
        print(f"[Mock OBS] Set text '{source_name}' -> '{text}'")

    def change_scene(self, scene_name: str):
        pass

    def set_source_visibility(self, scene_name: str, source_name: str, visible: bool):
        pass

# Mock TTS
class MockTTSEngine(TTSEngine):
    def __init__(self):
        self.is_playing = False
        self.speak_count = 0
        self.last_spoken_text = ""

    def speak(self, text: str, on_start=None, on_finished=None, *args, **kwargs):
        self.is_playing = True
        self.speak_count += 1
        self.last_spoken_text = text
        print(f"[Mock TTS] Đang phát: '{text}' (Lần thứ {self.speak_count})")
        
        # Giả lập nói rất nhanh trong 0.2s để test chạy nhanh
        async def fake_play():
            await asyncio.sleep(0.2)
            self.is_playing = False
            if on_finished:
                on_finished()
                
        asyncio.create_task(fake_play())

async def main():
    print("=== START TEST: MULTI-LEVEL AUTOPILOT ===")
    
    # Reset DB sạch
    db.init_db()
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM orders")
    cursor.execute("UPDATE products SET quantity = 10 WHERE code = 'SP001'")
    conn.commit()
    conn.close()

    ai = AIBrain()
    tts = MockTTSEngine()
    obs = MockOBSClient()
    
    processor = PriorityQueueProcessor(ai_brain=ai, tts_engine=tts, obs_client=obs)
    
    # ----------------------------------------------------
    # TEST 1: LEVEL 3 (Tự động hoàn toàn)
    # ----------------------------------------------------
    print("\n--- TEST 1: AUTOPILOT LEVEL 3 (Fully Auto) ---")
    processor.autopilot_level = 3
    await processor.start()

    start_time = time.time()
    await processor.enqueue({
        "username": "Khách L3_1",
        "comment": "Chốt sản phẩm SP001",
        "platform": "Test"
    })
    
    # Chờ xử lý comment 1 (tính cả gom lô 1s)
    await asyncio.sleep(3.0)
    assert tts.speak_count == 1, "Lỗi: Level 3 phải tự động phát TTS ngay!"
    assert "chốt đơn thành công" in tts.last_spoken_text.lower(), "Lỗi: Lời thoại AI không đúng!"
    
    # Gửi comment 2
    await processor.enqueue({
        "username": "Khách L3_2",
        "comment": "áo thun SP001 bao nhiêu em?",
        "platform": "Test"
    })
    
    # Chờ xử lý comment 2 (bao gồm cả gom lô + cooldown 3s giãn cách thông thường)
    await asyncio.sleep(6.5)
    assert tts.speak_count == 2, "Lỗi: Level 3 comment 2 phải được phát tự động!"
    print("✅ TEST 1 THÀNH CÔNG: Autopilot Level 3 tự động xử lý và phát bình luận hoàn hảo.")
    
    # Dừng processor để reset cho Test 2
    await processor.stop()

    # ----------------------------------------------------
    # TEST 2: LEVEL 2 (Bán tự động + Cooldown nhạy cảm 10s)
    # ----------------------------------------------------
    print("\n--- TEST 2: AUTOPILOT LEVEL 2 (Guarded Cooldown 10s) ---")
    tts.speak_count = 0
    processor.autopilot_level = 2
    processor.last_sensitive_action_time = 0.0 # reset cooldown timer
    
    await processor.start()
    
    # Gửi comment nhạy cảm 1 (Chốt đơn) -> Xử lý ngay lập tức
    print("-> Gửi bình luận nhạy cảm 1...")
    t1 = time.time()
    await processor.enqueue({
        "username": "Khách L2_1",
        "comment": "Chốt sản phẩm SP001",
        "platform": "Test"
    })
    
    await asyncio.sleep(2.5)
    assert tts.speak_count == 1, "Bình luận nhạy cảm 1 phải xử lý ngay!"
    
    # Gửi comment nhạy cảm 2 (Chốt đơn) -> Phải bị delay cho đủ 10 giây
    print("-> Gửi bình luận nhạy cảm 2 (bắt buộc phải chờ cooldown)...")
    await processor.enqueue({
        "username": "Khách L2_2",
        "comment": "Lấy thêm 1 cái SP001 nữa shop ơi",
        "platform": "Test"
    })
    
    # Ngủ 4 giây. Do cooldown nhạy cảm là 10 giây tính từ t1, sau 4 giây tts.speak_count vẫn phải là 1!
    await asyncio.sleep(4.0)
    print(f"Kiểm tra sau 4 giây: speak_count = {tts.speak_count} (Phải là 1 do đang cooldown)")
    assert tts.speak_count == 1, "Lỗi: Bình luận nhạy cảm 2 được phát quá sớm, vi phạm cooldown 10s!"
    
    # Đợi tiếp 7 giây nữa (tổng cộng đã qua 11 giây)
    await asyncio.sleep(7.0)
    print(f"Kiểm tra sau 11 giây: speak_count = {tts.speak_count} (Phải là 2 do đã hết cooldown)")
    assert tts.speak_count == 2, "Lỗi: Hết cooldown 10s mà bình luận nhạy cảm 2 vẫn chưa được xử lý!"
    print("✅ TEST 2 THÀNH CÔNG: Autopilot Level 2 ngăn chặn spam thao tác nhạy cảm bằng cooldown 10s chuẩn xác.")
    
    await processor.stop()

    # ----------------------------------------------------
    # TEST 3: LEVEL 1 (AI gợi ý + Người vận hành duyệt trước)
    # ----------------------------------------------------
    print("\n--- TEST 3: AUTOPILOT LEVEL 1 (Manual Approval) ---")
    tts.speak_count = 0
    processor.autopilot_level = 1
    
    pending_list = []
    def on_pending(comment_data):
        print(f"[Callback Nhận Chờ Duyệt] {comment_data['username']}: AI gợi ý: '{comment_data['answer']}'")
        pending_list.append(comment_data)
        
    processor.on_pending_approval_callback = on_pending
    
    await processor.start()
    
    # Gửi bình luận chốt đơn -> Chỉ sinh gợi ý, không phát TTS, không tạo đơn trong DB
    print("-> Gửi bình luận chốt đơn ở Level 1...")
    await processor.enqueue({
        "username": "Khách L1",
        "comment": "Chốt sản phẩm SP001 nha em",
        "platform": "Test"
    })
    
    await asyncio.sleep(2.0)
    assert tts.speak_count == 0, "Lỗi: Level 1 tự ý phát TTS khi chưa được duyệt!"
    assert len(pending_list) == 1, "Lỗi: Không tìm thấy bình luận trong danh sách chờ duyệt!"
    
    # Kiểm tra DB xem có đơn hàng của Khách L1 chưa (phải chưa có)
    orders = db.get_all_orders()
    has_l1_order = any(o["customer_name"] == "Khách L1" for o in orders)
    assert not has_l1_order, "Lỗi: Đơn hàng tự động được tạo ở Level 1 khi chưa được duyệt!"
    print("-> Xác nhận: Không phát TTS, không tạo đơn hàng tự động. Đã tạo bình luận chờ duyệt thành công.")

    # Người vận hành duyệt: Gọi execute_approved_comment thủ công
    print("-> Người vận hành bấm duyệt phát...")
    approved_item = pending_list[0]
    approved_item["answer"] = "Chào bạn L1, đơn hàng SP001 của bạn đã được duyệt nhé!"
    
    await processor.execute_approved_comment(approved_item)
    await asyncio.sleep(1.0)
    
    # Lúc này TTS mới được phát và đơn hàng mới được tạo trong DB
    assert tts.speak_count == 1, "Lỗi: Sau khi duyệt, TTS vẫn chưa được phát!"
    assert tts.last_spoken_text == "Chào bạn L1, đơn hàng SP001 của bạn đã được duyệt nhé!", "Lỗi: Nội dung phát không khớp với nội dung đã duyệt!"
    
    orders_after = db.get_all_orders()
    has_l1_order_after = any(o["customer_name"] == "Khách L1" for o in orders_after)
    assert has_l1_order_after, "Lỗi: Đơn hàng không được tạo trong DB sau khi đã duyệt!"
    print("✅ TEST 3 THÀNH CÔNG: Autopilot Level 1 giữ bình luận chờ duyệt và chỉ thực thi khi được Approve.")

    await processor.stop()
    print("\n✅ KẾT QUẢ: Hệ thống Autopilot phân cấp Level 1-3 hoạt động hoàn hảo 100%!")

if __name__ == "__main__":
    asyncio.run(main())
