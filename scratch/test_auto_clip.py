import sys
import os
import asyncio
import time

# Thêm thư mục gốc vào PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Đặt cấu hình môi trường test cho HighlightDirector trước khi import
os.environ["ENABLE_AUTO_CLIP"] = "True"
os.environ["HIGHLIGHT_THRESHOLD"] = "3"  # Đặt ngưỡng là 3 để test chạy nhanh
os.environ["HIGHLIGHT_COOLDOWN"] = "5"    # Cooldown 5 giây

from src.event_broker import global_broker
from src.obs_client import OBSClient
from src.highlight_director import HighlightDirector

# Mock OBS Client
class MockOBSClient(OBSClient):
    def __init__(self):
        self.is_connected = True
        self.client = None
        self.start_calls = 0
        self.save_calls = 0
        self.stop_calls = 0

    def start_replay_buffer(self) -> bool:
        self.start_calls += 1
        print("[Mock OBS] Khởi động Replay Buffer")
        return True

    def save_replay_buffer(self) -> bool:
        self.save_calls += 1
        print(f"[Mock OBS] Đã cắt và lưu Replay Buffer (Highlight clip) thành công! (Lần gọi thứ {self.save_calls})")
        return True

    def stop_replay_buffer(self) -> bool:
        self.stop_calls += 1
        print("[Mock OBS] Dừng Replay Buffer")
        return True

# Mock GUI Signals
class MockSignals:
    def emit(self, text: str):
        print(f"[GUI Log Signal] {text}")

class MockAppSignals:
    def __init__(self):
        self.log_event = MockSignals()

async def main():
    print("=== START TEST: AUTO-CLIP HIGHLIGHT ENGINE ===")
    
    obs = MockOBSClient()
    signals = MockAppSignals()
    
    director = HighlightDirector(obs_client=obs, app_signals=signals)
    await director.start()

    # Nhường quyền chạy để HighlightDirector kịp subscribe vào Event Broker
    await asyncio.sleep(0.2)

    # 1. Gửi 2 tương tác (Threshold là 3) -> Replay save chưa được phép gọi
    print("\n--- Gửi 2 tương tác đầu tiên ---")
    await global_broker.publish("comment_received", {"username": "User1", "comment": "Hello"})
    await global_broker.publish("like_received", {"username": "User2", "like_count": 1})
    
    await asyncio.sleep(0.5)
    print(f"Kiểm tra sau 2 tương tác: save_calls = {obs.save_calls} (Phải là 0)")
    assert obs.save_calls == 0, "Lỗi: Đã lưu replay trước khi đạt ngưỡng threshold!"

    # 2. Gửi tương tác thứ 3 -> Phải kích hoạt save replay
    print("\n--- Gửi tương tác thứ 3 (Đạt threshold) ---")
    await global_broker.publish("comment_received", {"username": "User3", "comment": "SP001"})
    
    await asyncio.sleep(0.5)
    print(f"Kiểm tra sau 3 tương tác: save_calls = {obs.save_calls} (Phải là 1)")
    assert obs.save_calls == 1, "Lỗi: Không tự động lưu highlight clip khi đạt ngưỡng threshold!"

    # 3. Gửi dồn dập thêm tương tác -> Phải bị chặn bởi Cooldown 5 giây
    print("\n--- Gửi dồn dập thêm tương tác khi đang cooldown ---")
    await global_broker.publish("like_received", {"username": "User4", "like_count": 5})
    await global_broker.publish("comment_received", {"username": "User5", "comment": "Tuyệt vời"})
    
    await asyncio.sleep(0.5)
    print(f"Kiểm tra trong thời gian cooldown: save_calls = {obs.save_calls} (Vẫn phải là 1)")
    assert obs.save_calls == 1, "Lỗi: Cắt clip highlight liên tục dồn dập, vi phạm cooldown!"

    # 4. Đợi 5 giây cho hết thời gian cooldown và dọn dẹp window cũ
    print("\n--- Đợi 5.5 giây cho hết cooldown ---")
    await asyncio.sleep(5.5)
    
    # 5. Gửi 3 tương tác mới -> Phải kích hoạt save replay lần thứ 2
    print("\n--- Gửi 3 tương tác mới sau khi hết cooldown ---")
    await global_broker.publish("comment_received", {"username": "User6", "comment": "Đẹp quá"})
    await global_broker.publish("like_received", {"username": "User7", "like_count": 2}) # 2 tim + 1 comment = 3 tương tác
    
    await asyncio.sleep(0.5)
    print(f"Kiểm tra sau khi hết cooldown: save_calls = {obs.save_calls} (Phải là 2)")
    assert obs.save_calls == 2, "Lỗi: Không lưu highlight clip lần thứ 2 sau khi hết cooldown!"

    # Dừng director
    await director.stop()
    print("\n✅ KẾT QUẢ: Hệ thống Auto-clip Highlight hoạt động hoàn hảo 100%!")

if __name__ == "__main__":
    asyncio.run(main())
