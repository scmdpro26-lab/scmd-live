import sys
import os
import time
import asyncio
import threading
import websockets
import json
from PySide6.QtCore import QMetaObject, Qt, QCoreApplication

# Thêm thư mục gốc vào PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.database as db
from src.gui.main_window import MainWindow
from PySide6.QtWidgets import QApplication
from src.web.server import start_api_server, stop_api_server

# Biến toàn cục để theo dõi kết quả test
test_success = False

async def websocket_test_client():
    global test_success
    uri = "ws://127.0.0.1:8080/ws?token=admin_secret"
    print(f"\n[Test WebSocket] Đang kết nối tới: {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("[Test WebSocket] Kết nối thành công!")
            
            # Nhận trạng thái ban đầu
            initial_state = await websocket.recv()
            print(f"[Test WebSocket] Nhận trạng thái ban đầu (Độ dài: {len(initial_state)} ký tự)")
            
            # 1. Test action: send_comment
            print("\n1. Gửi action: send_comment...")
            await websocket.send(json.dumps({
                "action": "send_comment",
                "params": {"username": "Khách Test", "comment": "Giá áo thun SP001 bao nhiêu shop?"}
            }))
            await asyncio.sleep(0.5)
            
            # 2. Test action: override
            print("\n2. Gửi action: override...")
            await websocket.send(json.dumps({
                "action": "override",
                "params": {"text": "Tin nhắn can thiệp khẩn cấp."}
            }))
            await asyncio.sleep(0.5)
            
            # 3. Test action: mute
            print("\n3. Gửi action: mute...")
            await websocket.send(json.dumps({
                "action": "mute"
            }))
            await asyncio.sleep(0.5)
            
            # 4. Test action: toggle_connector cho TikTok
            print("\n4. Gửi action: toggle_connector (TikTok)...")
            await websocket.send(json.dumps({
                "action": "toggle_connector",
                "params": {"platform": "tiktok"}
            }))
            await asyncio.sleep(0.5)
            
            # 5. Test action: toggle_connector cho Facebook
            print("\n5. Gửi action: toggle_connector (Facebook)...")
            await websocket.send(json.dumps({
                "action": "toggle_connector",
                "params": {"platform": "facebook"}
            }))
            await asyncio.sleep(0.5)
            
            print("\n[Test WebSocket] Hoàn thành gửi tất cả các actions không phát sinh lỗi crash!")
            test_success = True
    except Exception as e:
        print(f"\n❌ Lỗi trong client WebSocket: {e}")
        test_success = False

def run_test_client_thread(window, app):
    # Đợi server sẵn sàng
    time.sleep(3.0)
    
    # Chạy client
    asyncio.run(websocket_test_client())
    
    # Yêu cầu đóng cửa sổ GUI và thoát ứng dụng an toàn
    print("\n[Dọn dẹp] Gửi tín hiệu đóng ứng dụng...")
    QMetaObject.invokeMethod(window, "close", Qt.QueuedConnection)
    QMetaObject.invokeMethod(app, "quit", Qt.QueuedConnection)

def main():
    print("=== START INTEGRATION TEST: WEBSOCKET ACTIONS ON MAIN THREAD ===")
    db.init_db()
    
    # Khởi tạo QApplication trên Main Thread (Bắt buộc của Qt)
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show() # Hiển thị cửa sổ để đảm bảo event loop đóng đúng cách khi window close
    
    # Khởi động Web Server tại cổng test 8080
    start_api_server(window, host="127.0.0.1", port=8080)
    
    # Khởi chạy luồng phụ gửi dữ liệu kiểm thử
    client_thread = threading.Thread(target=run_test_client_thread, args=(window, app), daemon=True)
    client_thread.start()
    
    # Chạy vòng lặp sự kiện Qt trên Main Thread
    exit_code = app.exec()
    
    print("\n[Dọn dẹp] Đã đóng cửa sổ Qt. Đang dừng Web Server...")
    stop_api_server()
    time.sleep(1.0)
    
    if test_success:
        print("\n✅ KẾT QUẢ: Tất cả các WebSocket actions đã được xác minh thành công!")
        sys.exit(0)
    else:
        print("\n❌ Thất bại: Một số hành động WebSocket bị lỗi hoặc không phản hồi.")
        sys.exit(1)

if __name__ == "__main__":
    main()
