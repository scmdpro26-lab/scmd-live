import sys
import os
import time
import urllib.request
import threading

# Thêm thư mục gốc vào PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.database as db
from src.gui.main_window import MainWindow
from PySide6.QtWidgets import QApplication
from src.web.server import start_api_server, stop_api_server

def test_server():
    print("=== TEST FASTAPI WEB SERVER ===")
    
    # 1. Khởi tạo DB
    db.init_db()
    
    # 2. Khởi tạo QApplication (yêu cầu bởi MainWindow)
    app = QApplication(sys.argv)
    window = MainWindow()
    
    # 3. Chạy Web Server trong luồng phụ
    print("Khởi chạy Web Server...")
    start_api_server(window, host="127.0.0.1", port=8080)
    time.sleep(2.0) # Đợi 2s để server khởi động hoàn toàn
    
    # 4. Gửi HTTP GET request kiểm tra
    try:
        url = "http://127.0.0.1:8080/"
        print(f"Gửi request tới: {url}")
        with urllib.request.urlopen(url) as response:
            html = response.read().decode('utf-8')
            print(f"HTTP Status: {response.status}")
            print(f"Kích thước trang HTML nhận được: {len(html)} bytes")
            assert "AI Live Studio" in html, "Lỗi: Không tìm thấy tiêu đề 'AI Live Studio' trong HTML phản hồi!"
            print("✅ HTTP GET Request thành công!")
    except Exception as e:
        print(f"❌ Lỗi khi gửi request: {e}")
        sys.exit(1)
        
    # 5. Dừng server
    print("Đang dừng Web Server...")
    stop_api_server()
    time.sleep(1.0)
    print("=== Hoàn thành kiểm thử Web Server ===")

if __name__ == "__main__":
    test_server()
