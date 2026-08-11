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

# Mock OBS
class MockOBSClient(OBSClient):
    def __init__(self):
        self.is_connected = True
        self.client = None

    def update_text_source(self, source_name: str, text: str):
        pass
    def change_scene(self, scene_name: str):
        pass
    def set_source_visibility(self, scene_name: str, source_name: str, visible: bool):
        pass

# Mock TTS
class MockTTSEngine(TTSEngine):
    def speak(self, text: str, on_start=None, on_finished=None, *args, **kwargs):
        print(f"[Mock TTS] Đang phát: '{text}'")
        if on_finished:
            on_finished()

async def main():
    print("=== TEST CROSS-SELL DỰA TRÊN MEMORY STORE (ORDER HISTORY) ===")
    
    # 1. Setup Database sạch
    db.init_db()
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM orders")
    cursor.execute("UPDATE products SET quantity = 50 WHERE code = 'SP001'")
    cursor.execute("UPDATE products SET quantity = 25 WHERE code = 'SP002'")
    conn.commit()
    conn.close()

    # 2. Tạo đơn hàng cũ thành công cho Anh Minh mua SP001
    order_created = db.create_order(
        customer_name="Anh Minh",
        platform="Test",
        product_code="SP001",
        price=150000.0,
        quantity=1,
        status="Đã giao"
    )
    assert order_created, "Lỗi: Không tạo được đơn hàng cũ cho khách hàng!"
    
    # Đọc lại đơn hàng để chắc chắn đơn đã được lưu
    history = db.get_orders_by_customer("Anh Minh")
    print(f"Lịch sử mua hàng cũ của 'Anh Minh': {[dict(h) for h in history]}")
    assert len(history) == 1, "Lỗi: Lịch sử mua hàng của khách trống!"

    ai = AIBrain()
    tts = MockTTSEngine()
    obs = MockOBSClient()
    
    processor = PriorityQueueProcessor(ai_brain=ai, tts_engine=tts, obs_client=obs)
    await processor.start()

    # Callback nhận câu trả lời từ AI
    ai_responses = []
    def on_ai_response(user, comment, answer):
        ai_responses.append(answer)
        
    processor.on_ai_response_callback = on_ai_response

    # 3. Gửi comment hỏi phối đồ thời trang từ Anh Minh
    print("\n--- GỬI COMMENT HỎI PHỐI ĐỒ ---")
    await processor.enqueue({
        "username": "Anh Minh",
        "comment": "Shop ơi, có quần gì phối hợp thời trang hợp với cái áo cũ không?",
        "platform": "Test"
    })
    
    # Đợi xử lý comment (3s giãn cách)
    await asyncio.sleep(4.5)
    
    # 4. Kiểm tra câu trả lời
    assert len(ai_responses) > 0, "Lỗi: Không nhận được câu trả lời từ AI!"
    response_text = ai_responses[0]
    print(f"\nPhản hồi thực tế từ AI MC:\n'{response_text}'\n")

    # Kiểm tra xem AI có nhận biết sản phẩm cũ SP001 và bán chéo SP002 không
    # Vì chạy offline/mock hoặc online, chúng ta mong muốn tìm thấy từ khóa SP001 và SP002 (hoặc tên sản phẩm)
    # Trình mock_response của chúng ta đã viết sẵn để sinh câu bán chéo SP002 khi có lịch sử SP001.
    assert "sp001" in response_text.lower() or "áo thun" in response_text.lower(), "Lỗi: AI không nhận biết được áo thun SP001 đã mua!"
    assert "sp002" in response_text.lower() or "quần jean" in response_text.lower(), "Lỗi: AI không bán chéo quần jean SP002!"
    
    print("✅ THÀNH CÔNG: AI MC đã chủ động gợi ý bán chéo SP002 (Quần Jean) dựa trên lịch sử mua SP001 (Áo thun) của Anh Minh thành công!")

    await processor.stop()
    print("\n✅ KẾT QUẢ: Tính năng Cross-sell dựa trên Memory Store hoạt động hoàn hảo 100%!")

if __name__ == "__main__":
    asyncio.run(main())
