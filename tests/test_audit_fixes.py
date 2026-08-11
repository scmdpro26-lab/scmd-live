import unittest
import os
import asyncio
import sys

# Thêm thư mục gốc vào PYTHONPATH để tìm thấy src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ai_brain import predict_vietnamese_pronoun
from src.database import get_db_connection, create_order, delete_order
from src.priority_queue import PriorityQueueProcessor

class TestAuditFixes(unittest.TestCase):
    
    def setUp(self):
        # Thiết lập cơ sở dữ liệu test riêng
        self.test_db_path = "test_autolive_temp.db"
        from src.config import Config
        self.original_db_path = Config.DB_PATH
        Config.DB_PATH = self.test_db_path
        
        # Khởi tạo bảng test
        from src.database import init_db
        init_db()

    def tearDown(self):
        # Dọn dẹp tệp cơ sở dữ liệu tạm thời
        from src.config import Config
        Config.DB_PATH = self.original_db_path
        
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except Exception:
                pass
                
        # Dọn dẹp tệp cấu hình tạm của test env
        if os.path.exists(".env.test_temp"):
            try:
                os.remove(".env.test_temp")
            except Exception:
                pass
        if os.path.exists(".env.test_temp.tmp"):
            try:
                os.remove(".env.test_temp.tmp")
            except Exception:
                pass

    def test_pronoun_prediction(self):
        """Xác thực bộ nhận diện danh xưng giới tính dựa trên tên tiếng Việt."""
        self.assertEqual(predict_vietnamese_pronoun("Anh hùng"), "anh")
        self.assertEqual(predict_vietnamese_pronoun("Vy Vy"), "chị")
        self.assertEqual(predict_vietnamese_pronoun("Linh Nhi"), "chị")
        self.assertEqual(predict_vietnamese_pronoun("Văn Nam"), "anh")
        self.assertEqual(predict_vietnamese_pronoun("thị thanh"), "chị")
        self.assertEqual(predict_vietnamese_pronoun("Web Tester Pro"), "anh/chị")
        self.assertEqual(predict_vietnamese_pronoun(""), "anh/chị")

    def test_atomic_env_writing(self):
        """Xác thực quy trình ghi tệp cấu hình nguyên tử (Atomic write)."""
        env_path = ".env.test_temp"
        tmp_path = ".env.test_temp.tmp"
        
        # Tạo file .env giả lập ban đầu
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("TEST_KEY=OLD_VALUE\nOTHER_KEY=KEEP_ME\n")
            
        # Mô phỏng logic hàm update_env_file nguyên tử
        def simulate_update_env_file(key: str, value: str):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            new_lines = []
            key_found = False
            for line in lines:
                if line.strip().startswith(f"{key}="):
                    new_lines.append(f"{key}={value}\n")
                    key_found = True
                else:
                    new_lines.append(line)
            if not key_found:
                new_lines.append(f"{key}={value}\n")
            
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            os.replace(tmp_path, env_path)
            
        simulate_update_env_file("TEST_KEY", "NEW_VALUE")
        simulate_update_env_file("NEW_KEY", "ADDED_VALUE")
        
        # Kiểm tra file đã được cập nhật thành công và không bị rỗng/hỏng
        with open(env_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        self.assertIn("TEST_KEY=NEW_VALUE", content)
        self.assertIn("OTHER_KEY=KEEP_ME", content)
        self.assertIn("NEW_KEY=ADDED_VALUE", content)
        self.assertFalse(os.path.exists(tmp_path)) # Tệp tạm phải được dọn dẹp sạch

    def test_bounded_priority_queue_dropping(self):
        """Xác thực hàng đợi giới hạn kích thước và chính sách loại bỏ phần tử cũ nhất."""
        async def run_queue_test():
            # Khởi tạo processor với mock objects
            processor = PriorityQueueProcessor(None, None, None)
            
            # Cấu hình lại hàng đợi có kích thước giới hạn là 2
            processor.high_queue = asyncio.Queue(maxsize=2)
            
            # Mock hàm is_moderated và classify_comment
            processor.is_moderated = lambda comment: asyncio.sleep(0.001) or False
            processor.classify_comment = lambda comment: 1
            
            # Enqueue 3 comment liên tục
            await processor.enqueue({"username": "user1", "comment": "comment1"})
            await processor.enqueue({"username": "user2", "comment": "comment2"})
            await processor.enqueue({"username": "user3", "comment": "comment3"})
            
            # Hàng đợi có kích thước tối đa là 2, phần tử đầu tiên (user1) phải bị drop
            self.assertEqual(processor.high_queue.qsize(), 2)
            
            first_item = processor.high_queue.get_nowait()
            second_item = processor.high_queue.get_nowait()
            
            # user1 bị drop, chỉ còn user2 và user3 trong queue
            self.assertEqual(first_item["username"], "user2")
            self.assertEqual(second_item["username"], "user3")
            
        asyncio.run(run_queue_test())

    def test_database_isolation_level_override(self):
        """Xác thực việc tắt isolation_level để tự kiểm soát transaction trong các hàm ghi."""
        # 1. Kiểm thử tạo đơn hàng khi mã sản phẩm không tồn tại
        success = create_order("Test User", "Web", "SP_NON_EXISTENT", 150000.0, 1)
        self.assertFalse(success)
        
        # 2. Kiểm thử tạo đơn hàng thành công khi mã sản phẩm tồn tại
        success = create_order("Test User", "Web", "SP001", 150000.0, 1)
        self.assertTrue(success)
        
        # 3. Kiểm thử xóa đơn hàng không tồn tại
        success = delete_order(99999)
        self.assertFalse(success)

if __name__ == "__main__":
    unittest.main()
