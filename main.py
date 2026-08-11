import sys
from dotenv import load_dotenv
load_dotenv() # Load environment variables before importing other modules

from PySide6.QtWidgets import QApplication
import src.database as db
from src.gui.main_window import MainWindow

def main():
    # 1. Khởi tạo cơ sở dữ liệu SQLite
    db.init_db()
    
    # 2. Khởi tạo ứng dụng PySide6
    app = QApplication(sys.argv)
    
    # 3. Tạo và hiển thị cửa sổ chính
    window = MainWindow()
    window.show()
    
    # 4. Bắt đầu vòng lặp sự kiện
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
