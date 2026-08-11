import sys
import os

# Set environment variables BEFORE importing src.web.server to ensure module level initialization uses them
os.environ["WEB_TOKEN"] = "admin_secret"

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

async def order_test_client():
    global test_success
    ws_uri = "ws://127.0.0.1:8080/ws?token=admin_secret"
    api_url = "http://127.0.0.1:8080/api/orders"
    
    print(f"\n[Test Order] Đang kết nối tới WebSocket: {ws_uri}...")
    try:
        async with websockets.connect(ws_uri) as websocket:
            print("[Test Order] Kết nối WebSocket thành công!")
            
            # Đọc trạng thái ban đầu để kiểm tra tồn kho ban đầu của SP001
            initial_state_json = await websocket.recv()
            initial_state = json.loads(initial_state_json)
            
            sp001_qty_start = 50
            for prod in initial_state.get("products", []):
                if prod["code"] == "SP001":
                    sp001_qty_start = prod["quantity"]
                    break
            print(f"[Test Order] Tồn kho ban đầu của SP001: {sp001_qty_start}")
            
            # 1. Gửi bình luận chốt đơn giả lập từ khách hàng
            print("\n1. Gửi bình luận chốt đơn giả lập...")
            await websocket.send(json.dumps({
                "action": "send_comment",
                "params": {"username": "Khách Chốt Đơn", "comment": "chốt chiếc áo SP001 này nhé shop ơi!"}
            }))
            
            # Chờ PriorityQueueProcessor xử lý và ghi nhận đơn hàng
            print("[Test Order] Chờ hệ thống ghi nhận đơn hàng và cập nhật tồn kho...")
            await asyncio.sleep(4.0)
            
            # 2. Kiểm tra đơn hàng được ghi nhận trong database
            print("\n2. Kiểm tra cơ sở dữ liệu...")
            orders = db.get_all_orders()
            assert len(orders) > 0, "Không tìm thấy đơn hàng nào được tạo!"
            
            latest_order = orders[0]
            print(f"[Test Order] Đơn hàng mới nhất trong DB: ID={latest_order['id']}, Khách={latest_order['customer_name']}, Mã SP={latest_order['product_code']}, Giá={latest_order['price']}, Trạng thái={latest_order['status']}")
            
            assert latest_order["customer_name"] == "Khách Chốt Đơn", "Tên khách hàng không khớp!"
            assert latest_order["product_code"] == "SP001", "Mã sản phẩm không khớp!"
            assert latest_order["status"] == "Chờ xác nhận", "Trạng thái đơn hàng mặc định không khớp!"
            print("✅ Đơn hàng tự động ghi nhận thành công với trạng thái 'Chờ xác nhận'!")
            
            # Kiểm tra tồn kho SP001 giảm đi 1
            products = db.get_all_products()
            sp001_qty_after = 49
            for prod in products:
                if prod["code"] == "SP001":
                    sp001_qty_after = prod["quantity"]
                    break
            print(f"[Test Order] Tồn kho SP001 sau khi chốt đơn: {sp001_qty_after}")
            assert sp001_qty_after == sp001_qty_start - 1, f"Tồn kho không tự động trừ đúng! (Trước: {sp001_qty_start}, Sau: {sp001_qty_after})"
            print("✅ Tồn kho sản phẩm tự động trừ chính xác!")
            
            # 3. Gửi REST API cập nhật trạng thái đơn hàng (Chờ xác nhận -> Đã chốt)
            order_id = latest_order["id"]
            status_url = f"{api_url}/{order_id}/status"
            print(f"\n3. Gọi REST API cập nhật trạng thái đơn #{order_id} sang 'Đã chốt'...")
            
            status_payload = {"status": "Đã chốt"}
            data_bytes = json.dumps(status_payload).encode("utf-8")
            req_post = urllib.request.Request(
                status_url,
                data=data_bytes,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer admin_secret"
                },
                method="POST"
            )
            with urllib.request.urlopen(req_post) as response_post:
                resp_post = json.loads(response_post.read().decode("utf-8"))
                print(f"[Test Order] API Response: {resp_post}")
                assert resp_post.get("status") == "ok", "Cập nhật trạng thái qua API thất bại!"
            
            # Đọc lại từ DB để kiểm tra
            orders_updated = db.get_all_orders()
            for o in orders_updated:
                if o["id"] == order_id:
                    print(f"[Test Order] Trạng thái đơn #{order_id} trong DB sau khi cập nhật: {o['status']}")
                    assert o["status"] == "Đã chốt", "Trạng thái đơn hàng không cập nhật đúng!"
                    break
            print("✅ Trạng thái đơn hàng đã được cập nhật chính xác sang 'Đã chốt'!")
            
            # 4. Xóa đơn hàng và kiểm tra hoàn trả tồn kho
            print(f"\n4. Xóa đơn hàng #{order_id} để hoàn trả tồn kho...")
            delete_success = db.delete_order(order_id)
            assert delete_success, "Không thể xóa đơn hàng!"
            
            # Kiểm tra tồn kho quay lại ban đầu
            products_final = db.get_all_products()
            sp001_qty_final = sp001_qty_start
            for prod in products_final:
                if prod["code"] == "SP001":
                    sp001_qty_final = prod["quantity"]
                    break
            print(f"[Test Order] Tồn kho SP001 sau khi hủy đơn hàng: {sp001_qty_final}")
            assert sp001_qty_final == sp001_qty_start, "Tồn kho không được hoàn trả chính xác!"
            print("✅ Tồn kho sản phẩm được hoàn trả đầy đủ và chính xác sau khi hủy đơn!")
            
            print("\n✅ KẾT QUẢ: Hệ thống Order Management hoạt động hoàn hảo và không lỗi crash!")
            test_success = True
            
    except Exception as e:
        print(f"\n❌ Lỗi trong quá trình kiểm thử Order Management: {e}")
        test_success = False

def run_test_client_thread(window, app):
    time.sleep(3.0) # Đợi server sẵn sàng
    asyncio.run(order_test_client())
    
    print("\n[Dọn dẹp] Gửi tín hiệu tắt ứng dụng...")
    QMetaObject.invokeMethod(window, "close", Qt.QueuedConnection)
    QMetaObject.invokeMethod(app, "quit", Qt.QueuedConnection)

def main():
    print("=== START INTEGRATION TEST: ORDER MANAGEMENT & AUTOMATIC CHECKOUT ===")
    
    # Đảm bảo DB sạch và khởi tạo đầy đủ
    conn = db.get_db_connection()
    cursor = conn.cursor()
    db.init_db()
    # Xóa các đơn hàng cũ để tránh nhiễu
    cursor.execute("DELETE FROM orders")
    # Đặt lại số lượng tồn kho SP001 về 50
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
        print("\n✅ THÀNH CÔNG: Tính năng Order Management hoạt động hoàn hảo!")
        sys.exit(0)
    else:
        print("\n❌ THẤT BẠI: Quá trình kiểm thử Order Management gặp lỗi.")
        sys.exit(1)

if __name__ == "__main__":
    main()
