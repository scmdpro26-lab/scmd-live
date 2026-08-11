import sys
import os
import time

# Thêm thư mục gốc vào PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vmc_client import VMCClient

# Mock SimpleUDPClient to capture sent messages
class MockUDPClient:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sent_messages = []

    def send_message(self, path, arguments):
        self.sent_messages.append((path, arguments))
        print(f"[Mock UDP] Sent: {path} -> {arguments}")

def test_vmc():
    print("=== TEST VMC CLIENT (OSC PROTOCOL) ===")
    
    # Khởi tạo VMC client tới localhost port mặc định 39539
    vmc = VMCClient("127.0.0.1", 39539)
    
    # Thay thế client thật bằng mock client
    mock_client = MockUDPClient("127.0.0.1", 39539)
    vmc.vmc_client = mock_client
    
    print("\n1. Gửi biểu cảm Joy (Vui vẻ)")
    vmc.send_blendshape("Joy", 1.0)
    
    print("\n2. Gửi biểu cảm Surprise (Bất ngờ) qua trigger")
    vmc.trigger_expression("Surprise", 0.5)
    time.sleep(0.8)
    
    print("\n3. Mô phỏng nhép môi Lipsync (Talking)")
    vmc.start_talking()
    time.sleep(0.5)
    vmc.stop_talking()
    
    # Assertions
    assert len(mock_client.sent_messages) > 0, "No VMC messages were sent"
    
    # Kiểm tra blendshape Joy được gửi
    joy_messages = [msg for msg in mock_client.sent_messages if msg[0] == "/VMC/Ext/Blend/Val" and msg[1][0] == "Joy"]
    assert len(joy_messages) > 0, "Blendshape Joy was not sent"
    assert joy_messages[0][1][1] == 1.0, f"Joy value should be 1.0, got {joy_messages[0][1][1]}"
    
    print("\n=== Hoàn thành kiểm thử VMC Client ===")
    sys.exit(0)

if __name__ == "__main__":
    test_vmc()
