import sqlite3
import logging
from typing import Optional, Dict, Any, List
from src.config import Config
from src.database import get_db_connection

logger = logging.getLogger("MemoryStore")

class MemoryStore:
    def __init__(self):
        self.init_memory_table()

    def init_memory_table(self):
        """Khởi tạo bảng lưu bộ nhớ khách hàng nếu chưa tồn tại."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customer_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                comment TEXT NOT NULL,
                response TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("Khởi tạo bảng customer_memories thành công.")

    def save_memory(self, username: str, comment: str, response: str):
        """Lưu tương tác của khách hàng vào CSDL."""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO customer_memories (username, comment, response)
                VALUES (?, ?, ?)
            ''', (username.strip(), comment.strip(), response.strip()))
            conn.commit()
            conn.close()
            logger.info(f"Đã lưu bộ nhớ cho khách {username}")
        except Exception as e:
            logger.error(f"Lỗi khi lưu bộ nhớ: {e}")

    def recall_memory(self, username: str, current_comment: str) -> Optional[str]:
        """Truy xuất lịch sử tương tác trước đó của khách hàng."""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT comment, response, timestamp 
                FROM customer_memories 
                WHERE username = ? 
                ORDER BY id DESC 
                LIMIT 5
            ''', (username.strip(),))
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return None
                
            memories = [dict(row) for row in rows]
            
            # Tính Jaccard Similarity tìm comment tương đồng nhất
            best_match = None
            best_score = 0.0
            
            current_words = set(current_comment.lower().split())
            
            for mem in memories:
                past_words = set(mem["comment"].lower().split())
                intersection = current_words.intersection(past_words)
                union = current_words.union(past_words)
                score = len(intersection) / len(union) if union else 0.0
                
                if score > best_score:
                    best_score = score
                    best_match = mem
            
            # Nếu tìm thấy một câu tương tự (Score > 0.3)
            if best_match and best_score > 0.3:
                return (
                    f"Khách hàng {username} từng hỏi câu tương tự trước đó: '{best_match['comment']}'\n"
                    f"AI từng trả lời: '{best_match['response']}'"
                )
            
            # Ngược lại, trả về thông tin lần hỏi gần đây nhất
            last_mem = memories[0]
            return (
                f"Khách hàng {username} đã tương tác trước đó.\n"
                f"Câu hỏi gần nhất: '{last_mem['comment']}' (Lúc: {last_mem['timestamp']})\n"
                f"AI đã trả lời gần nhất: '{last_mem['response']}'"
            )
            
        except Exception as e:
            logger.error(f"Lỗi khi recall bộ nhớ: {e}")
            return None
