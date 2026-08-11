import sys
import os

# Thêm thư mục gốc vào PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import asyncio
from src.config import Config
import src.database as db
from src.ai_brain import AIBrain
from src.tts_engine import TTSEngine

def test_database():
    print("\n--- TEST DATABASE ---")
    db.init_db()
    products = db.get_all_products()
    print(f"Tổng số sản phẩm trong DB: {len(products)}")
    for p in products:
        print(f"- [{p['code']}] {p['name']} - Giá: {p['price']:,.0f} VNĐ (Tồn: {p['quantity']})")

def test_ai_brain():
    print("\n--- TEST AI BRAIN ---")
    brain = AIBrain()
    print(f"Trạng thái Gemini API: {'Đã cấu hình' if brain.api_configured else 'Mock Mode'}")
    
    # Test 1: Hỏi giá sản phẩm
    product = db.find_product_by_query("SP001")
    response_1 = brain.generate_response("Khách Hàng A", "Sản phẩm SP001 này bao nhiêu tiền vậy shop?", product)
    print(f"Q: Sản phẩm SP001 này bao nhiêu tiền vậy shop?")
    print(f"A: {response_1}")
    
    # Test 2: Hỏi chung chung
    response_2 = brain.generate_response("Khách Hàng B", "Ship Huế bao lâu thì nhận được em?")
    print(f"Q: Ship Huế bao lâu thì nhận được em?")
    print(f"A: {response_2}")

def test_tts():
    print("\n--- TEST TTS ENGINE ---")
    tts = TTSEngine()
    print(f"Giọng đọc hiện tại: {tts.voice}")
    
    print("Bắt đầu nói...")
    tts.speak("Hệ thống tự động hóa livestream bán hàng đã sẵn sàng hoạt động.", 
              on_start=lambda: print("-> Đang phát giọng đọc..."),
              on_finished=lambda: print("-> Đã phát xong."))
    
    # Đợi 5 giây để nghe thử
    time.sleep(5)
    tts.stop()

if __name__ == "__main__":
    test_database()
    test_ai_brain()
    test_tts()
    print("\n=== Hoàn thành kiểm thử ===")
