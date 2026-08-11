import sys
import os

# Set environment variables BEFORE importing project files
os.environ["WEB_TOKEN"] = "admin_secret"

import time
import asyncio
import threading
import json
import websockets
from PySide6.QtCore import QMetaObject, Qt
from PySide6.QtWidgets import QApplication

# Thêm thư mục gốc vào PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.database as db
from src.gui.main_window import MainWindow
from src.web.server import start_api_server, stop_api_server

# MOCK TIKTOK LIVE LIBRARY FOR TESTING
# Điều này đảm bảo test chạy thành công 100% độc lập, không phụ thuộc vào trạng thái online/offline của streamer thật.
class MockUser:
    def __init__(self, nickname):
        self.nickname = nickname

class MockCommentEvent:
    def __init__(self, nickname, comment):
        self.user = MockUser(nickname)
        self.comment = comment

class MockTikTokLiveClient:
    def __init__(self, unique_id):
        self.unique_id = unique_id
        self.events = {}
        self.is_running = False

    def on(self, event_name):
        def decorator(func):
            self.events[event_name] = func
            return func
        return decorator

    async def start(self):
        self.is_running = True
        print(f"[Mock Webcast Client] Đang kết nối mô phỏng tới TikTok Live Webcast...")
        
        # Gọi event connect nếu có đăng ký
        if "connect" in self.events:
            # Giả lập connect event
            class MockConnectEvent:
                pass
            await self.events["connect"](MockConnectEvent())
            
        print("[Mock Webcast Client] Kết nối thành công! Bắt đầu phát comment webcast giả lập...")
        
        # Phát comment giả lập
        mock_comments = [
            ("Nguyễn Hữu Đạt", "chốt sản phẩm SP001 nha shop"),
            ("Thảo Vy", "quần jean SP002 còn size M không?"),
            ("Minh Hoàng", "Mũ lưỡi trai SP003 màu đen đẹp quá")
        ]
        
        for nickname, comment in mock_comments:
            if not self.is_running:
                break
            await asyncio.sleep(1.0)
            if "comment" in self.events:
                print(f"[Mock Webcast Client] Webcast binary packet -> comment: {nickname}: '{comment}'")
                await self.events["comment"](MockCommentEvent(nickname, comment))
                
        # Giữ kết nối mở cho đến khi bị cancel
        try:
            while self.is_running:
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass

    def stop(self):
        self.is_running = False

# Áp dụng Mock vào module
import src.connectors.tiktok as tiktok_module
tiktok_module.TikTokLiveClient = MockTikTokLiveClient
tiktok_module.TIKTOK_LIVE_AVAILABLE = True

test_success = False

async def tiktok_test_client():
    global test_success
    ws_uri = "ws://127.0.0.1:8080/ws?token=admin_secret"
    
    print(f"\n[Test TikTok Webcast] Đang kết nối tới WebSocket: {ws_uri}...")
    try:
        async with websockets.connect(ws_uri) as websocket:
            print("[Test TikTok Webcast] Kết nối WebSocket thành công!")
            
            # Nhận trạng thái ban đầu
            initial_state = await websocket.recv()
            print(f"[Test TikTok Webcast] Đã nhận trạng thái ban đầu (Độ dài: {len(initial_state)})")
            
            # 1. Bật TikTok Connector qua WebSocket
            print("\n1. Bật TikTok Webcast Connector...")
            await websocket.send(json.dumps({
                "action": "toggle_connector",
                "params": {"platform": "tiktok"}
            }))
            
            # Chờ Mock Webcast Client gửi các comment protobuf giả lập và xử lý chốt đơn
            print("\n2. Chờ nhận comment webcast và PriorityQueue xử lý...")
            await asyncio.sleep(8.0)
            
            # Kiểm tra xem đơn hàng chốt từ "Nguyễn Hữu Đạt" có được tự động tạo trong DB không
            orders = db.get_all_orders()
            print(f"\n3. Kiểm tra DB xem có đơn hàng chốt tự động không...")
            found_order = False
            for order in orders:
                if order["customer_name"] == "Nguyễn Hữu Đạt" and order["product_code"] == "SP001":
                    print(f"✅ Tìm thấy đơn hàng tự động chốt từ TikTok Webcast: ID={order['id']}, Khách={order['customer_name']}, Mã={order['product_code']}")
                    found_order = True
                    break
            
            assert found_order, "Không tìm thấy đơn hàng tự động chốt từ bình luận TikTok Webcast!"
            print("\n✅ KẾT QUẢ: TikTok Webcast Connector đã cào comment và hệ thống chốt đơn tự động chạy hoàn hảo!")
            test_success = True
            
    except Exception as e:
        print(f"\n❌ Lỗi trong quá trình kiểm thử TikTok Webcast: {e}")
        test_success = False

def run_test_client_thread(window, app):
    time.sleep(3.0) # Đợi server sẵn sàng
    asyncio.run(tiktok_test_client())
    
    print("\n[Dọn dẹp] Gửi tín hiệu tắt ứng dụng...")
    QMetaObject.invokeMethod(window, "close", Qt.QueuedConnection)
    QMetaObject.invokeMethod(app, "quit", Qt.QueuedConnection)

def main():
    print("=== START INTEGRATION TEST: TIKTOK WEBCAST PROTOBUF CONNECTOR ===")
    
    # Reset DB sạch cho test
    conn = db.get_db_connection()
    cursor = conn.cursor()
    db.init_db()
    cursor.execute("DELETE FROM orders")
    cursor.execute("UPDATE products SET quantity = 50 WHERE code = 'SP001'")
    conn.commit()
    conn.close()
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    
    start_api_server(window, host="127.0.0.1", port=8080)
    
    client_thread = threading.Thread(target=run_test_client_thread, args=(window, app), daemon=True)
    client_thread.start()
    
    exit_code = app.exec()
    
    print("\n[Dọn dẹp] Đã đóng cửa sổ Qt. Đang dừng Web Server...")
    stop_api_server()
    time.sleep(1.0)
    
    if test_success:
        print("\n✅ THÀNH CÔNG: Tích hợp TikTok Webcast Protobuf hoạt động hoàn hảo!")
        sys.exit(0)
    else:
        print("\n❌ THẤT BẠI: Quá trình kiểm thử TikTok Webcast gặp lỗi.")
        sys.exit(1)

if __name__ == "__main__":
    main()
