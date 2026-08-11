import sys
import os

# Set environment variables BEFORE importing src.web.server to ensure module-level initialization uses them
os.environ["WEB_TOKEN"] = "admin_secret"
os.environ["FB_VERIFY_TOKEN"] = "fb_verify_secret"
os.environ["FB_APP_SECRET"] = "fb_app_secret_test_value"

import time
import asyncio
import threading
import json
import urllib.request
import urllib.parse
import websockets
from PySide6.QtCore import QMetaObject, Qt
from PySide6.QtWidgets import QApplication

# Thêm thư mục gốc vào PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.database as db
from src.gui.main_window import MainWindow
from src.web.server import start_api_server, stop_api_server

test_success = False

async def webhook_test_client():
    global test_success
    ws_uri = "ws://127.0.0.1:8080/ws?token=admin_secret"
    webhook_url = "http://127.0.0.1:8080/webhook/facebook"
    
    print(f"\n[Test FB Webhook] Đang kết nối tới WebSocket: {ws_uri}...")
    try:
        async with websockets.connect(ws_uri) as websocket:
            print("[Test FB Webhook] Kết nối WebSocket thành công!")
            
            # Nhận trạng thái ban đầu
            initial_state = await websocket.recv()
            print(f"[Test FB Webhook] Đã nhận trạng thái ban đầu (Độ dài: {len(initial_state)})")
            
            # 1. Test GET Verification Webhook
            print("\n1. Test GET Verification Webhook...")
            verify_params = {
                "hub.mode": "subscribe",
                "hub.challenge": "fb_challenge_abc_123",
                "hub.verify_token": "fb_verify_secret"
            }
            query_string = urllib.parse.urlencode(verify_params)
            verify_url = f"{webhook_url}?{query_string}"
            
            req = urllib.request.Request(verify_url, method="GET")
            with urllib.request.urlopen(req) as response:
                resp_text = response.read().decode("utf-8")
                print(f"[Test FB Webhook] Verification Response: {resp_text}")
                assert resp_text == "fb_challenge_abc_123", "Verification challenge mismatch!"
                print("✅ Test Verification thành công!")
            
            # 2. Bật Facebook Connector qua WebSocket
            print("\n2. Bật Facebook Connector...")
            await websocket.send(json.dumps({
                "action": "toggle_connector",
                "params": {"platform": "facebook"}
            }))
            await asyncio.sleep(1.0) # Chờ cập nhật trạng thái
            
            # 3. Test POST Event Webhook (Gửi comment giả lập từ Facebook)
            print("\n3. Gửi POST Event Webhook giả lập bình luận từ Facebook...")
            mock_payload = {
                "object": "page",
                "entry": [
                    {
                        "id": "10420516",
                        "time": 1723112345,
                        "changes": [
                            {
                                "value": {
                                    "from": {
                                        "id": "123456789",
                                        "name": "Nguyễn Văn Webhook"
                                    },
                                    "message": "Giá áo thun SP001 thế nào shop?",
                                    "post_id": "10420516_99999",
                                    "comment_id": "111222333",
                                    "created_time": 1723112345,
                                    "item": "comment",
                                    "verb": "add"
                                },
                                "field": "feed"
                            }
                        ]
                    }
                ]
            }
            
            data_bytes = json.dumps(mock_payload).encode("utf-8")
            import hmac
            import hashlib
            app_secret = "fb_app_secret_test_value"
            expected_sig = "sha256=" + hmac.new(app_secret.encode('utf-8'), data_bytes, hashlib.sha256).hexdigest()
            
            req_post = urllib.request.Request(
                webhook_url,
                data=data_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": expected_sig
                },
                method="POST"
            )
            with urllib.request.urlopen(req_post) as response_post:
                resp_post = json.loads(response_post.read().decode("utf-8"))
                print(f"[Test FB Webhook] Webhook Post Response: {resp_post}")
                assert resp_post.get("status") == "ok", "Webhook Post failed!"
            
            # Chờ PriorityQueueProcessor xử lý comment
            print("\n4. Chờ hệ thống xử lý bình luận...")
            await asyncio.sleep(4.0)
            
            print("\n✅ KẾT QUẢ: Tiến trình test kết thúc không có lỗi crash!")
            test_success = True
            
    except Exception as e:
        print(f"\n❌ Lỗi trong quá trình kiểm thử FB Webhook: {e}")
        test_success = False

def run_test_client_thread(window, app):
    time.sleep(3.0) # Đợi server sẵn sàng
    asyncio.run(webhook_test_client())
    
    print("\n[Dọn dẹp] Gửi tín hiệu tắt ứng dụng...")
    QMetaObject.invokeMethod(window, "close", Qt.QueuedConnection)
    QMetaObject.invokeMethod(app, "quit", Qt.QueuedConnection)

def main():
    print("=== START INTEGRATION TEST: FACEBOOK GRAPH API WEBHOOK ===")
    db.init_db()
    
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
        print("\n✅ THÀNH CÔNG: Tích hợp Webhook Facebook hoạt động hoàn hảo!")
        sys.exit(0)
    else:
        print("\n❌ THẤT BẠI: Quá trình kiểm thử Webhook Facebook gặp lỗi.")
        sys.exit(1)

if __name__ == "__main__":
    main()
