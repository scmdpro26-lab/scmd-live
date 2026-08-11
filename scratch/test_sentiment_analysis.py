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
        self.speech_records = [] # Lưu các lần gọi speak: (text, rate, pitch)

    def speak(self, text: str, on_start=None, on_finished=None, rate: str = "+0%", pitch: str = "+0Hz"):
        print(f"[Mock TTS] Speak: '{text}' | Rate: {rate} | Pitch: {pitch}")
        self.speech_records.append((text, rate, pitch))
        if on_finished:
            on_finished()

async def main():
    print("=== START TEST: SEMANTIC SENTIMENT ANALYSIS ===")
    
    # Setup DB
    db.init_db()
    
    ai = AIBrain()
    tts = MockTTSEngine()
    obs = MockOBSClient()
    
    processor = PriorityQueueProcessor(ai_brain=ai, tts_engine=tts, obs_client=obs)
    
    # Mock VMC Client để lưu biểu cảm được gọi
    vmc_records = []
    class MockVMCClient:
        def trigger_expression(self, expression_name: str, duration: float):
            print(f"[Mock VMC] Biểu cảm -> '{expression_name}' (Thời gian: {duration}s)")
            vmc_records.append(expression_name)
        def start_talking(self):
            pass
        def stop_talking(self):
            pass
            
    processor.vmc_client = MockVMCClient()
    await processor.start()

    # 1. Gửi comment vui vẻ
    print("\n--- 1. GỬI COMMENT VUI VẺ ---")
    await processor.enqueue({
        "username": "Khách Vui",
        "comment": "Chốt đồ đẹp tuyệt vời shop ơi",
        "platform": "Test"
    })
    await asyncio.sleep(4.5)
    
    # 2. Gửi comment khó chịu
    print("\n--- 2. GỬI COMMENT KHÓ CHỊU ---")
    await processor.enqueue({
        "username": "Khách Khó Chịu",
        "comment": "Áo này đắt quá shop làm ăn chán thật sự",
        "platform": "Test"
    })
    await asyncio.sleep(4.5)

    # 3. Gửi comment nghi ngờ
    print("\n--- 3. GỬI COMMENT NGHI NGỜ ---")
    await processor.enqueue({
        "username": "Khách Nghi Ngờ",
        "comment": "Không biết chất vải SP001 đúng cotton tự nhiên thật không?",
        "platform": "Test"
    })
    await asyncio.sleep(4.5)

    # 4. KIỂM TRA KẾT QUẢ XÁC THỰC
    print("\n=== KIỂM TRA KẾT QUẢ ===")
    
    # Check VMC expressions
    print(f"Danh sách biểu cảm VMC đã trigger: {vmc_records}")
    assert len(vmc_records) == 3, "Lỗi: Số lượng biểu cảm VMC không khớp!"
    assert vmc_records[0] == "Joy", "Lỗi: Lượt 1 phải trigger biểu cảm Joy!"
    assert vmc_records[1] == "Sorrow", "Lỗi: Lượt 2 phải trigger biểu cảm Sorrow (hối lỗi)!"
    assert vmc_records[2] == "Surprise", "Lỗi: Lượt 3 phải trigger biểu cảm Surprise (nghi ngờ)!"
    print("✅ VMC expressions khớp chuẩn 100%!")

    # Check TTS rate & pitch
    print(f"Danh sách giọng nói TTS: {tts.speech_records}")
    assert len(tts.speech_records) == 3, "Lỗi: Số lượng giọng nói TTS không khớp!"
    
    # Lượt 1: rate = +5%, pitch = +1Hz
    _, r1, p1 = tts.speech_records[0]
    assert r1 == "+5%" and p1 == "+1Hz", f"Lỗi: Lượt 1 rate/pitch không đúng! Nhận: {r1}/{p1}"
    
    # Lượt 2: rate = -8%, pitch = -3Hz
    _, r2, p2 = tts.speech_records[1]
    assert r2 == "-8%" and p2 == "-3Hz", f"Lỗi: Lượt 2 rate/pitch không đúng! Nhận: {r2}/{p2}"
    
    # Lượt 3: rate = -3%, pitch = +1Hz
    _, r3, p3 = tts.speech_records[2]
    assert r3 == "-3%" and p3 == "+1Hz", f"Lỗi: Lượt 3 rate/pitch không đúng! Nhận: {r3}/{p3}"
    print("✅ TTS rate/pitch giọng nói khớp chuẩn 100%!")

    # Check OBS subtitles (phải được làm sạch, không chứa thẻ [SENTIMENT])
    print(f"Phụ đề OBS cuối cùng: '{obs.texts.get(processor.subtitle_source)}'")
    for source_name, text in obs.texts.items():
        if source_name == processor.subtitle_source:
            assert not text.startswith("[SENTIMENT:"), f"Lỗi: OBS subtitle chưa được làm sạch! Nhận: '{text}'"
    print("✅ OBS subtitles đã được làm sạch hoàn hảo!")

    await processor.stop()
    print("\n✅ KẾT QUẢ: Hệ thống Sentiment Analysis điều chỉnh biểu cảm và tông giọng MC hoạt động hoàn hảo 100%!")

if __name__ == "__main__":
    asyncio.run(main())
