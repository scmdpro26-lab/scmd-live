import sys
import os

# Thêm thư mục gốc vào PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
import src.database as db
from src.gui.main_window import MainWindow

def capture_gui():
    db.init_db()
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    
    # Hàm chụp ảnh màn hình và thoát
    def capture():
        # Đảm bảo thư mục lưu screenshot tồn tại
        screenshot_dir = r"C:\Users\quanying_zhang\.gemini\antigravity\brain\0f6db614-21cc-45e9-ad3f-eb904c0dbc6b"
        os.makedirs(screenshot_dir, exist_ok=True)
        screenshot_path = os.path.join(screenshot_dir, "gui_screenshot.png")
        
        # Chụp giao diện cửa sổ
        pixmap = window.grab()
        pixmap.save(screenshot_path)
        print(f"Chụp ảnh giao diện thành công và lưu tại: {screenshot_path}")
        app.quit()
        
    # Chờ 1.5 giây để giao diện vẽ xong hoàn toàn rồi chụp
    QTimer.singleShot(1500, capture)
    
    app.exec()

if __name__ == "__main__":
    capture_gui()
