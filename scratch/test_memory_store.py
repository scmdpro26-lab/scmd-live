import sys
import os
import sqlite3

# Thêm thư mục gốc vào PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.database as db
from src.memory_store import MemoryStore

def test_memory():
    print("=== TEST CUSTOMER MEMORY STORE ===")
    
    # 1. Khởi tạo DB
    db.init_db()
    
    # Khởi tạo MemoryStore trước để bảng customer_memories được tạo
    store = MemoryStore()
    
    # Xóa lịch sử cũ để đảm bảo tính nhất quán của bài test
    conn = db.get_db_connection()
    conn.execute("DELETE FROM customer_memories")
    conn.commit()
    conn.close()
    
    # 2. Lưu một số tương tác mẫu của khách hàng
    print("\nLưu các tương tác mẫu...")
    store.save_memory("Khách Minh", "Áo thun SP001 chất liệu gì thế em?", "Dạ áo thun SP001 chất cotton 100% co giãn cực tốt nha anh!")
    store.save_memory("Khách Minh", "Shop có giao nhanh đi Huế không?", "Dạ bên em ship toàn quốc mất 2-3 ngày là tới Huế luôn ạ.")
    
    # 3. Thử hỏi lại câu tương tự (Tìm kiếm tương đồng)
    print("\nTruy xuất lịch sử khi khách hỏi câu tương tự...")
    context_1 = store.recall_memory("Khách Minh", "Áo thun SP001 có co giãn nhiều không em?")
    print(f"Kết quả recall 1:\n{context_1}")
    
    # 4. Thử hỏi câu hoàn toàn mới (Trả về câu hỏi gần nhất)
    print("\nTruy xuất lịch sử khi khách hỏi câu mới hoàn toàn...")
    context_2 = store.recall_memory("Khách Minh", "Chào shop, hôm nay có voucher giảm giá gì không?")
    print(f"Kết quả recall 2:\n{context_2}")
    
    # Đánh giá kết quả
    assert "co giãn cực tốt" in context_1, "Không tìm thấy đúng ngữ cảnh tương đồng cho câu hỏi áo thun!"
    assert "ship toàn quốc" in context_2, "Không tìm thấy câu hỏi gần nhất là về giao hàng đi Huế!"
    
    print("\n✅ CHÚC MỪNG: Hệ thống Bộ nhớ Khách hàng dài hạn (Memory Store) hoạt động hoàn hảo!")

if __name__ == "__main__":
    test_memory()
