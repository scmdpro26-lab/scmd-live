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
        self.speech_records = []

    def speak(self, text: str, on_start=None, on_finished=None, rate: str = "+0%", pitch: str = "+0Hz"):
        print(f"[Mock TTS] Speak: '{text}' | Rate: {rate} | Pitch: {pitch}")
        self.speech_records.append(text)
        if on_finished:
            on_finished()

async def main():
    print("=== START TEST: MULTI-PLATFORM RESTREAM & AGGREGATED RESPONSE ===")
    
    # 1. Setup DB sạch
    db.init_db()
    
    # Reset tồn kho SP001 và SP002
    conn = db.get_db_connection()
    conn.execute("UPDATE products SET quantity = 10 WHERE code = 'SP001'")
    conn.execute("UPDATE products SET quantity = 5 WHERE code = 'SP002'")
    conn.commit()
    conn.close()
    
    ai = AIBrain()
    tts = MockTTSEngine()
    obs = MockOBSClient()
    
    processor = PriorityQueueProcessor(ai_brain=ai, tts_engine=tts, obs_client=obs)
    
    # Mock VMC Client
    class MockVMCClient:
        def trigger_expression(self, expression_name: str, duration: float):
            print(f"[Mock VMC] Biểu cảm -> '{expression_name}'")
        def start_talking(self):
            pass
        def stop_talking(self):
            pass
            
    processor.vmc_client = MockVMCClient()
    
    # Đặt autopilot level = 3 (Tự động hoàn toàn) để tự động kích hoạt gom batch
    processor.autopilot_level = 3
    await processor.start()

    # 2. Gửi đồng thời 3 comment từ 3 platform khác nhau
    print("\n--- Gửi đồng thời 3 comment đa kênh (TikTok, Facebook, YouTube) ---")
    await processor.enqueue({
        "username": "Minh TikTok",
        "comment": "chốt SP001 nha shop ơi",
        "platform": "TikTok"
    })
    
    await processor.enqueue({
        "username": "Hương Facebook",
        "comment": "ship thế nào shop ơi",
        "platform": "Facebook"
    })
    
    await processor.enqueue({
        "username": "Tuấn YouTube",
        "comment": "quần SP002 còn không?",
        "platform": "YouTube"
    })

    # Chờ 6 giây để gom batch (chờ 1.0s gom + 3.0s phát tts + 2.0s dư dả)
    await asyncio.sleep(6.0)

    # 3. XÁC THỰC KẾT QUẢ
    print("\n=== KIỂM TRA KẾT QUẢ ===")
    
    # A. Check đơn hàng được tạo tự động cho Minh TikTok (SP001)
    orders = db.get_orders_by_customer("Minh TikTok")
    print(f"Đơn hàng của Minh TikTok: {orders}")
    assert len(orders) == 1, "Lỗi: Không tự động tạo đơn hàng chốt đơn trong batch!"
    assert orders[0]["product_code"] == "SP001", "Lỗi: Mã sản phẩm chốt đơn không khớp!"
    
    # Check tồn kho SP001 bị trừ đi 1 (còn 9)
    prod = db.find_product_by_query("SP001")
    print(f"Tồn kho SP001 sau chốt đơn: {prod['quantity']} cái (Phải là 9)")
    assert prod["quantity"] == 9, "Lỗi: Không tự động trừ tồn kho khi chốt đơn trong batch!"
    print("✅ Tự động tạo đơn hàng & trừ kho chốt đơn trong batch thành công!")

    # B. Check câu trả lời gộp của AI MC
    print(f"Danh sách phát TTS: {tts.speech_records}")
    assert len(tts.speech_records) == 1, "Lỗi: MC không phát câu trả lời gộp (hoặc phát nhiều câu đơn lẻ)!"
    
    combined_response = tts.speech_records[0]
    print(f"Câu trả lời gộp thực tế của MC: '{combined_response}'")
    
    # Verify câu trả lời chứa thông tin phản hồi cho cả 3 khách hàng
    assert "Minh TikTok" in combined_response or "Minh" in combined_response, "Lỗi: Thiếu phản hồi cho Minh TikTok!"
    assert "Hương Facebook" in combined_response or "Hương" in combined_response, "Lỗi: Thiếu phản hồi cho Hương Facebook!"
    assert "Tuấn YouTube" in combined_response or "Tuấn" in combined_response, "Lỗi: Thiếu phản hồi cho Tuấn YouTube!"
    print("✅ MC trả lời gộp đa nền tảng đồng thời thành công!")

    await processor.stop()
    print("\n✅ KẾT QUẢ: Hệ thống Đa nền tảng đồng thời & Trả lời gộp hoạt động hoàn hảo 100%!")

if __name__ == "__main__":
    asyncio.run(main())
