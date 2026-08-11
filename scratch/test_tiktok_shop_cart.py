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
from src.tiktok_shop import global_tiktok_shop
from src.event_broker import global_broker

# Mock OBS
class MockOBSClient(OBSClient):
    def __init__(self):
        self.is_connected = True
        self.client = None
        self.texts = {}
        self.visible_sources = {}

    def update_text_source(self, source_name: str, text: str):
        self.texts[source_name] = text
        print(f"[Mock OBS] Set text '{source_name}' -> '{text}'")

    def change_scene(self, scene_name: str):
        print(f"[Mock OBS] Change Scene -> '{scene_name}'")

    def set_source_visibility(self, scene_name: str, source_name: str, visible: bool):
        self.visible_sources[source_name] = visible
        print(f"[Mock OBS] Visibility '{source_name}' -> {visible}")

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
        print(f"[Mock TTS] Đang phát: '{text}'")
        
        # Giả lập phát âm thanh hoàn tất
        if on_start:
            on_start()
        
        async def fake_play():
            await asyncio.sleep(0.1)
            self.is_playing = False
            if on_finished:
                on_finished()
        
        asyncio.create_task(fake_play())

async def test_main():
    print("=== BẮT ĐẦU KIỂM THỬ R&D TIKTOK SHOP CART & LIVE EVENTS ===")
    
    # 1. Khởi tạo Database sạch cho test
    db.init_db()
    
    # Đặt lại số lượng tồn kho sản phẩm để test
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET quantity = 10 WHERE code = 'SP001'")
    cursor.execute("UPDATE products SET quantity = 5 WHERE code = 'SP002'")
    conn.commit()
    conn.close()
    
    # 2. Khởi tạo các mock client
    mock_obs = MockOBSClient()
    mock_tts = MockTTSEngine()
    ai_brain = AIBrain()
    
    # Mock AIBrain API call to run tests locally with zero network dependency
    ai_brain.generate_response = lambda username, comment, product_info=None, *args, **kwargs: (
        f"[SENTIMENT: vui] Dạ chào {username}, cảm ơn bạn đã tương tác! " + 
        (f"Mẫu {product_info['name']} ({product_info['code']}) này đẹp lắm ạ!" if product_info else "")
    )
    ai_brain.classify_moderation = lambda comment: "CLEAN"
    
    # Giao diện callback log

    def on_log(text):
        print(f"[System Log] {text}")
        
    # Tạo queue processor
    processor = PriorityQueueProcessor(
        ai_brain=ai_brain,
        tts_engine=mock_tts,
        obs_client=mock_obs
    )
    processor.autopilot_level = 3  # Tự động hoàn toàn
    
    # Bật processor
    await processor.start()
    
    # Helper to wait for conditions (with 5.0 seconds timeout)
    async def wait_until(condition_fn, timeout=5.0):
        start_t = time.time()
        while time.time() - start_t < timeout:
            if condition_fn():
                return True
            await asyncio.sleep(0.1)
        return False

    # --- TEST TÁC VỤ 1: Kiểm thử Ghim/Hủy ghim thủ công ---
    print("\n--- TEST 1: Ghim/Hủy ghim thủ công qua TikTokShopCart ---")
    
    # Ghim SP001
    res1 = await global_tiktok_shop.pin_product("SP001")
    assert res1 is True, "Ghim SP001 phải thành công"
    assert global_tiktok_shop.pinned_product_code == "SP001", "Mã sản phẩm ghim phải là SP001"
    
    # Hủy ghim
    res2 = await global_tiktok_shop.unpin_product()
    assert res2 is True, "Hủy ghim phải thành công"
    assert global_tiktok_shop.pinned_product_code is None, "Giỏ hàng phải trống sau khi hủy ghim"
    
    # --- TEST TÁC VỤ 2: Tự động ghim sản phẩm khi comment khớp ---
    print("\n--- TEST 2: Tự động ghim sản phẩm trên chat ---")
    
    # Giả lập comment hỏi về SP002
    comment_data = {
        "platform": "TikTok",
        "username": "Khách Test",
        "comment": "cho mình xin giá quần jean SP002 với"
    }
    await processor.enqueue(comment_data)
    
    # Đợi xử lý bằng polling
    success_pin = await wait_until(lambda: global_tiktok_shop.pinned_product_code == "SP002")
    assert success_pin, "SP002 phải được tự động ghim"
    print("-> Tự động ghim SP002 thành công!")
    
    # --- TEST TÁC VỤ 3: Tự động hủy ghim sản phẩm khi hết hàng ---
    print("\n--- TEST 3: Tự động hủy ghim khi hết hàng ---")
    
    # Cập nhật SP002 tồn kho về 0 (hết hàng)
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET quantity = 0 WHERE code = 'SP002'")
    conn.commit()
    conn.close()
    
    # Giả lập comment hỏi tiếp về SP002 để kích hoạt kiểm tra kho
    comment_data2 = {
        "platform": "TikTok",
        "username": "Khách Test 2",
        "comment": "quần SP002 còn không shop?"
    }
    await processor.enqueue(comment_data2)
    
    # Đợi xử lý bằng polling
    success_unpin = await wait_until(lambda: global_tiktok_shop.pinned_product_code is None)
    assert success_unpin, "SP002 phải bị hủy ghim tự động vì hết hàng"
    print("-> Tự động hủy ghim sản phẩm hết hàng thành công!")
    
    # --- TEST TÁC VỤ 4: Nhận và xử lý sự kiện live (Gift, Follow, Share, Click Cart) ---
    print("\n--- TEST 4: Tương tác sự kiện phòng live (Truly AI Live) ---")
    
    # 4a. Giả lập Follow
    print("-> Giả lập follow...")
    mock_tts.last_spoken_text = ""
    await global_broker.publish("follow_received", {"platform": "TikTok", "username": "Khách Follower"})
    success_follow = await wait_until(lambda: "Khách Follower" in mock_tts.last_spoken_text)
    assert success_follow, "MC phải cảm ơn người follow"
    
    # 4b. Giả lập Share
    print("-> Giả lập share...")
    mock_tts.last_spoken_text = ""
    await global_broker.publish("share_received", {"platform": "TikTok", "username": "Khách Sharer"})
    success_share = await wait_until(lambda: "Khách Sharer" in mock_tts.last_spoken_text)
    assert success_share, "MC phải cảm ơn người share"
    
    # 4c. Giả lập Gift
    print("-> Giả lập tặng quà...")
    mock_tts.last_spoken_text = ""
    await global_broker.publish("gift_received", {
        "platform": "TikTok",
        "username": "Khách Tặng Quà",
        "gift_name": "Hoa hồng",
        "gift_count": 5
    })
    success_gift = await wait_until(lambda: "Khách Tặng Quà" in mock_tts.last_spoken_text)
    assert success_gift, "MC phải cảm ơn người tặng quà"
    
    # 4d. Giả lập Click xem sản phẩm trong giỏ hàng
    print("-> Giả lập click xem sản phẩm SP001...")
    mock_tts.last_spoken_text = ""
    await global_broker.publish("cart_click_received", {
        "platform": "TikTok",
        "username": "Người Mua",
        "product_code": "SP001"
    })
    success_cart = await wait_until(lambda: global_tiktok_shop.pinned_product_code == "SP001")
    assert success_cart, "SP001 phải được ghim khi khách nhấp xem"
    success_cart_msg = await wait_until(lambda: "SP001" in mock_tts.last_spoken_text or "Áo" in mock_tts.last_spoken_text or "Khách" in mock_tts.last_spoken_text)
    assert success_cart_msg, "MC phải phản hồi khi khách xem sản phẩm"
    
    # Dừng processor
    await processor.stop()
    print("\n=== TẤT CẢ CÁC BÀI THỬ NGHIỆM ĐÃ VƯỢT QUA THÀNH CÔNG (EXIT 0) ===")


if __name__ == "__main__":
    asyncio.run(test_main())
