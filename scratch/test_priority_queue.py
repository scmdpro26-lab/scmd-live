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

# Mock lớp TTS để không phát âm thanh thực tế khi test, giảm thời gian chạy test
class MockTTSEngine(TTSEngine):
    def __init__(self):
        super().__init__()
        self.is_playing = False
        
    def speak(self, text: str, on_start=None, on_finished=None, *args, **kwargs):
        self.is_playing = True
        print(f"[Mock TTS] Đang nói: '{text}'")
        # Giả lập phát âm thanh mất 1.5 giây
        async def fake_play():
            await asyncio.sleep(1.0)
            self.is_playing = False
            if on_finished:
                on_finished()
        asyncio.create_task(fake_play())

async def main():
    print("=== TEST HÀNG ĐỢI ƯU TIÊN (PRIORITY QUEUE) ===")
    db.init_db()
    
    # Khởi tạo các component mock/thật
    ai = AIBrain()
    tts = MockTTSEngine()
    obs = OBSClient() # disconnected
    
    # Biến theo dõi thứ tự xử lý thực tế
    processed_sequence = []
    
    def on_ai_response(user, comment, answer):
        print(f"[Xử lý xong] Khách {user}: '{comment}' -> Trả lời: {answer}")
        processed_sequence.append((user, comment))

    processor = PriorityQueueProcessor(
        ai_brain=ai,
        tts_engine=tts,
        obs_client=obs,
        on_queue_change_callback=lambda sizes: print(f"[Cập nhật kích thước Hàng đợi] Cao: {sizes['high']}, Trung: {sizes['medium']}, Thấp: {sizes['low']}")
    )
    processor.on_ai_response_callback = on_ai_response
    processor.subtitle_source = "Test_Subtitle"
    processor.comment_source = "Test_Comment"
    
    # 1. Nạp đồng thời 3 bình luận có độ ưu tiên khác nhau
    comments = [
        {"username": "Khách Thấp", "comment": "Hi shop, hello em!", "platform": "Test"},          # Priority 3 (Thấp)
        {"username": "Khách Trung", "comment": "Giao hàng đi Huế mất mấy ngày?", "platform": "Test"}, # Priority 2 (Trung)
        {"username": "Khách Cao", "comment": "Chốt sản phẩm SP001 nha em", "platform": "Test"}        # Priority 1 (Cao)
    ]
    
    print("\n[Đưa bình luận vào hàng đợi...]")
    for item in comments:
        await processor.enqueue(item)
        
    # Kích thước hàng đợi sau khi nạp
    sizes = processor.get_queue_sizes()
    print(f"\nKích thước sau khi nạp: Cao: {sizes['high']}, Trung: {sizes['medium']}, Thấp: {sizes['low']}")
    
    # 2. Khởi chạy bộ xử lý hàng đợi
    print("\n[Khởi chạy bộ xử lý hàng đợi...]")
    await processor.start()
    
    # Chờ xử lý hết cả 3 comment (mỗi comment mất khoảng 1s TTS + 3s delay Guardrail)
    await asyncio.sleep(13.0)

    
    # Dừng processor
    await processor.stop()
    
    # 3. Đánh giá thứ tự xử lý thực tế
    print("\n=== KẾT QUẢ THỨ TỰ XỬ LÝ ===")
    for idx, (user, comment) in enumerate(processed_sequence):
        print(f"Bước {idx+1}: {user} - '{comment}'")
        
    # Thứ tự mong muốn: Khách Cao (P1) -> Khách Trung (P2) -> Khách Thấp (P3)
    assert processed_sequence[0][0] == "Khách Cao", "Sai thứ tự: Phải xử lý Khách Cao trước!"
    assert processed_sequence[1][0] == "Khách Trung", "Sai thứ tự: Tiếp theo phải xử lý Khách Trung!"
    assert processed_sequence[2][0] == "Khách Thấp", "Sai thứ tự: Cuối cùng mới xử lý Khách Thấp!"
    
    print("\n✅ CHÚC MỪNG: Thứ tự xử lý hoàn toàn chính xác theo mức độ ưu tiên từ Cao xuống Thấp!")

if __name__ == "__main__":
    asyncio.run(main())
