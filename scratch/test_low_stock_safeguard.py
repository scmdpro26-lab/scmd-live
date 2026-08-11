import sys
import os
import asyncio

# Thêm thư mục gốc vào PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.database as db
from src.ai_brain import AIBrain
from src.tts_engine import TTSEngine
from src.obs_client import OBSClient
from src.priority_queue import PriorityQueueProcessor

# Mock OBS Client để theo dõi trạng thái hiển thị
class MockOBSClient(OBSClient):
    def __init__(self):
        self.is_connected = True
        self.client = None
        self.visibility_events = [] # Lưu các cuộc gọi set_source_visibility

    def set_source_visibility(self, scene_name: str, source_name: str, visible: bool):
        print(f"[Mock OBS] Sét hiển thị source '{source_name}' trong scene '{scene_name}' -> {visible}")
        self.visibility_events.append((scene_name, source_name, visible))

    def change_scene(self, scene_name: str):
        print(f"[Mock OBS] Chuyển scene -> '{scene_name}'")

    def update_text_source(self, source_name: str, text: str):
        print(f"[Mock OBS] Cập nhật text source '{source_name}' -> '{text}'")

# Mock TTS
class MockTTSEngine(TTSEngine):
    def speak(self, text: str, on_start=None, on_finished=None, *args, **kwargs):
        print(f"[Mock TTS] Đang phát: '{text}'")
        if on_finished:
            on_finished()

async def main():
    print("=== TEST LOW-STOCK ALERT & AUTO-HIDE OBS ===")
    
    # 1. Chuẩn bị database sạch: Set SP001 có số lượng bằng 1, đặt obs_scene/source hợp lệ
    db.init_db()
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM orders")
    cursor.execute("UPDATE products SET quantity = 1, obs_scene = 'Live Scene', obs_source = 'Product_SP001' WHERE code = 'SP001'")
    conn.commit()
    conn.close()
    
    # Đọc sản phẩm để kiểm tra
    product = db.find_product_by_query("SP001")
    print(f"Sản phẩm SP001 ban đầu: Tồn kho = {product['quantity']}, OBS Source = '{product['obs_source']}'")
    assert product['quantity'] == 1, "Tồn kho ban đầu phải là 1!"

    ai = AIBrain()
    tts = MockTTSEngine()
    obs = MockOBSClient()
    
    processor = PriorityQueueProcessor(ai_brain=ai, tts_engine=tts, obs_client=obs)
    await processor.start()

    # 2. Gửi comment chốt đơn lượt 1 (Thành công, tồn kho về 0)
    print("\n--- GỬI COMMENT CHỐT ĐƠN LƯỢT 1 ---")
    await processor.enqueue({
        "username": "Khách A",
        "comment": "Chốt sản phẩm SP001 nha shop",
        "platform": "Test"
    })
    
    # Đợi xử lý comment 1 (gồm cả delay 3s giãn cách)
    await asyncio.sleep(4.5)
    
    # Kiểm tra xem OBS có nhận được tín hiệu ẩn source sản phẩm (False) không
    print("\nKiểm tra trạng thái OBS sau lượt 1...")
    found_hide_event = False
    for scene, source, visible in obs.visibility_events:
        if source == product['obs_source'] and visible is False:
            found_hide_event = True
            break
            
    assert found_hide_event, "Lỗi: Không tìm thấy sự kiện ẩn OBS Source khi sản phẩm hết hàng!"
    print("✅ Thành công: Lệnh ẩn OBS Source đã được gửi ngay khi sản phẩm hết hàng (quantity = 0).")

    # 3. Gửi comment chốt đơn lượt 2 (Thất bại do hết hàng)
    print("\n--- GỬI COMMENT CHỐT ĐƠN LƯỢT 2 ---")
    
    ai_responses = []
    def on_ai_response(user, comment, answer):
        ai_responses.append(answer)
        
    processor.on_ai_response_callback = on_ai_response
    
    await processor.enqueue({
        "username": "Khách B",
        "comment": "Lấy cho mình 1 cái SP001 nữa",
        "platform": "Test"
    })
    
    # Đợi xử lý comment 2
    await asyncio.sleep(4.5)
    
    # Kiểm tra câu trả lời của AI
    assert len(ai_responses) > 0, "Không nhận được phản hồi từ AI!"
    print(f"AI response lượt 2: '{ai_responses[0]}'")
    
    # Kiểm tra từ khóa từ chối / xin lỗi hết hàng
    assert "hết hàng" in ai_responses[0].lower() or "tiếc" in ai_responses[0].lower(), "Lỗi: AI vẫn chốt đơn/không xin lỗi khi hết hàng!"
    print("✅ Thành công: AI thông báo hết hàng và từ chối lên đơn chuẩn xác.")

    # Dừng processor
    await processor.stop()
    print("\n✅ KẾT QUẢ: Hệ thống Low-stock alert & auto-hide OBS hoạt động hoàn hảo 100%!")

if __name__ == "__main__":
    asyncio.run(main())
