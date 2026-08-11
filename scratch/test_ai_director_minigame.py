import sys
import os
import json
import asyncio
import time

# Thêm thư mục gốc vào PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai_director import AIDirector
from src.event_broker import global_broker
from src.tts_engine import TTSEngine
from src.obs_client import OBSClient

class MockOBSClient(OBSClient):
    def __init__(self):
        self.is_connected = True
        self.client = None
        self.sources = {}

    def set_source_visibility(self, scene_name: str, source_name: str, visible: bool):
        self.sources[source_name] = visible
        print(f"[Mock OBS] Đặt source '{source_name}' trong scene '{scene_name}' -> Hiển thị: {visible}")
        return True

    def change_scene(self, scene_name: str):
        print(f"[Mock OBS] Đổi scene -> '{scene_name}'")
        return True

class MockTTSEngine(TTSEngine):
    def __init__(self):
        self.is_playing = False
        self.speech_records = []

    def speak(self, text: str, on_start=None, on_finished=None, rate: str = "+0%", pitch: str = "+0Hz"):
        print(f"[Mock TTS] Đang đọc: '{text}'")
        self.speech_records.append(text)
        if on_finished:
            on_finished()

async def main():
    print("=== START TEST: AUTOMATED MINIGAME & VOUCHER ENGINE ===")
    
    # 1. Tạo file kịch bản timeline test tạm thời
    timeline_path = "scratch/test_timeline.json"
    test_events = [
        {
            "time_seconds": 2,
            "action": "trigger_minigame",
            "description": "Kích hoạt minigame theo timeline",
            "params": {
                "text": "Minigame bắt đầu theo lịch timeline nha mọi người!"
            }
        },
        {
            "time_seconds": 4,
            "action": "trigger_voucher",
            "description": "Tung voucher theo timeline",
            "params": {
                "text": "Voucher tung ra theo lịch timeline nha mọi người!"
            }
        }
    ]
    with open(timeline_path, "w", encoding="utf-8") as f:
        json.dump(test_events, f, indent=4)
        
    obs = MockOBSClient()
    tts = MockTTSEngine()
    ai_brain = None # Không cần AI brain thực tế cho test này
    
    director = AIDirector(obs, ai_brain, tts, timeline_path=timeline_path)
    
    # Rút ngắn các mốc thời gian để test nhanh
    director.silence_threshold = 3.0  # Phòng nguội quá 3s là kích hoạt hâm nóng
    director.like_milestone = 50       # Đạt 50 tim tự động tung voucher
    
    await director.start()
    
    # 2. VERIFY TIMELINE EVENTS
    print("\n--- 2. KIỂM TRA TIMELINE SCHEDULE ---")
    
    # Chờ 2.5s để event minigame chạy (ở giây thứ 2)
    await asyncio.sleep(2.5)
    assert obs.sources.get("Minigame_Source") is True, "Lỗi: Không tự kích hoạt Minigame Source theo lịch!"
    assert any("Minigame bắt đầu theo lịch timeline" in r for r in tts.speech_records), "Lỗi: MC không đọc thông báo minigame timeline!"
    print("✅ Tự động kích hoạt Minigame theo kịch bản timeline thành công!")
    
    # Chờ thêm 2.0s để event voucher chạy (ở giây thứ 4)
    await asyncio.sleep(2.0)
    assert obs.sources.get("Voucher_Source") is True, "Lỗi: Không tự kích hoạt Voucher Source theo lịch!"
    assert any("Voucher tung ra theo lịch timeline" in r for r in tts.speech_records), "Lỗi: MC không đọc thông báo voucher timeline!"
    print("✅ Tự động tung Voucher theo kịch bản timeline thành công!")

    # 3. VERIFY LIKES MILESTONE TRIGGERS
    print("\n--- 3. KIỂM TRA MỐC THẢ TIM (LIKES MILESTONE) ---")
    obs.sources["Voucher_Source"] = False # Reset status
    tts.speech_records.clear()
    
    # Gửi sự kiện tim đạt mốc 60 (vượt milestone 50)
    event_data = {
        "platform": "TikTok",
        "username": "Khách_Yêu",
        "like_count": 60
    }
    await global_broker.publish("like_received", event_data)
    
    # Chờ xử lý sự kiện
    await asyncio.sleep(0.5)
    assert obs.sources.get("Voucher_Source") is True, "Lỗi: Không tự động hiện Voucher banner khi đạt mốc tim!"
    assert any("Đạt mốc 50 tim rồi" in r for r in tts.speech_records), "Lỗi: MC không đọc giới thiệu voucher mốc tim!"
    print("✅ Tự động kích hoạt Voucher banner khi đạt mốc tim thành công!")

    # 4. VERIFY SILENCE DETECTION
    print("\n--- 4. KIỂM TRA SILENCE DETECTION ---")
    obs.sources["Minigame_Source"] = False
    obs.sources["Voucher_Source"] = False
    tts.speech_records.clear()
    
    # Reset last_comment_time để tính mốc silence 3s
    director.last_comment_time = time.time()
    
    # Chờ 4.5s để kích hoạt monitor loop (chạy mỗi 2.0s) phát hiện silence > 3.0s
    await asyncio.sleep(4.5)
    
    # Xác minh là đã kích hoạt một trong các hình thức hâm nóng
    activated_minigame = obs.sources.get("Minigame_Source") is True
    activated_voucher = obs.sources.get("Voucher_Source") is True
    activated_question = any("hâm nóng phòng livestream" in r or "hỏi giao lưu" in r for r in tts.speech_records)
    
    # Chúng ta check comment được bắn lên broker hâm nóng
    # Nhưng vì ai_brain=None, ta chỉ cần check có ít nhất 1 hình thức (hoặc minigame, hoặc voucher, hoặc TTS nói câu hâm nóng) được chạy
    has_hot_trigger = activated_minigame or activated_voucher or len(tts.speech_records) > 0
    print(f"Trạng thái hâm nóng: Minigame={activated_minigame}, Voucher={activated_voucher}, TTS Speech={tts.speech_records}")
    assert has_hot_trigger, "Lỗi: Silence Detection không kích hoạt bất kỳ sự kiện hâm nóng nào!"
    print("✅ Silence Detection tự động kích hoạt hâm nóng phòng live thành công!")

    # 5. DỌN DẸP
    await director.stop()
    if os.path.exists(timeline_path):
        os.remove(timeline_path)
        
    print("\n✅ KẾT QUẢ: Hệ thống Minigame & Voucher tự động hoạt động hoàn hảo 100%!")

if __name__ == "__main__":
    asyncio.run(main())
