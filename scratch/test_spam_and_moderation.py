import sys
import os
import asyncio
import time
from typing import Dict, Any

# Thêm thư mục gốc vào PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.database as db
from src.ai_brain import AIBrain
from src.priority_queue import PriorityQueueProcessor

# Mock OBS Client
class MockOBS:
    is_connected = False
    def update_text_source(self, source, text):
        pass
    def set_source_visibility(self, scene, source, visible):
        pass
    def change_scene(self, scene):
        pass

# Mock TTS
class MockTTS:
    is_playing = False
    def speak(self, text, on_start=None, on_finished=None, rate=None, pitch=None):
        if on_start:
            on_start()
        if on_finished:
            on_finished()

async def main():
    print("=== START TEST: CHECKOUT SPAM BLOCK & OUTPUT MODERATION ===")
    db.init_db()
    
    ai = AIBrain()
    tts = MockTTS()
    obs = MockOBS()
    
    processor = PriorityQueueProcessor(ai_brain=ai, tts_engine=tts, obs_client=obs)
    
    # 1. KIỂM THỬ KIỂM DUYỆT ĐẦU RA AI (OUTPUT MODERATION)
    print("\n--- 1. KIỂM THỬ KIỂM DUYỆT ĐẦU RA AI ---")
    toxic_outputs = [
        ("áo thun này mặc như cặc ấy em", "áo thun này mặc như *** ấy em"),
        ("địt mẹ sản phẩm gì thế shop", "*** mẹ sản phẩm gì thế shop"),
        ("l0n d e o mua nữa đjt", "*** *** mua nữa ***"),
    ]
    
    for input_text, expected_output in toxic_outputs:
        result = processor.moderate_ai_output(input_text)
        print(f"Đầu ra AI: '{input_text}'\n-> Đã lọc:  '{result}'")
        assert "***" in result, f"Lỗi: Không lọc được từ nhạy cảm trong '{input_text}'"
        
    # Xác thực không lọc nhầm từ lành mạnh tiếng Việt (ví dụ Nguyễn chứa ngu)
    clean_outputs = [
        "chào bạn Nguyễn Văn A",
        "giao hàng đi Đà Nẵng",
        "vải mang mát mẻ"
    ]
    for input_text in clean_outputs:
        result = processor.moderate_ai_output(input_text)
        print(f"Đầu ra lành mạnh: '{input_text}'\n-> Đã lọc:          '{result}'")
        assert result == input_text, f"Lỗi: Lọc nhầm từ lành mạnh trong '{input_text}' -> '{result}'"
        
    print("✅ Xác thực kiểm duyệt đầu ra AI thành công!")

    # 2. KIỂM THỬ CHẶN SPAM CHỐT ĐƠN
    print("\n--- 2. KIỂM THỬ CHẶN SPAM CHỐT ĐƠN ---")
    
    # Giả lập comment chốt đơn của người dùng 'spam_user' cho sản phẩm 'SP001'
    comment_data_1 = {
        "username": "spam_user",
        "comment": "Chốt đơn SP001 giá tốt nhé shop",
        "platform": "Test"
    }
    
    # Lần 1: Chốt đơn bình thường (sản phẩm SP001 còn tồn kho)
    await processor._process_comment(comment_data_1)
    print(f"Lần 1: is_checkout = {comment_data_1.get('is_checkout')}, order_success = {comment_data_1.get('order_success')}")
    assert comment_data_1.get("is_checkout") is True
    assert comment_data_1.get("order_success") is True
    
    # Lần 2: Chốt tiếp SP001 ngay lập tức (cooldown 10s & trùng SP001 trong 30s) -> Bị chặn
    comment_data_2 = {
        "username": "spam_user",
        "comment": "Chốt đơn SP001 giá tốt nhé shop",
        "platform": "Test"
    }
    await processor._process_comment(comment_data_2)
    print(f"Lần 2 (Chốt tiếp SP001 ngay lập tức): is_checkout = {comment_data_2.get('is_checkout')}, order_success = {comment_data_2.get('order_success')}, lý do: '{comment_data_2.get('order_error_reason')}'")
    assert comment_data_2.get("is_checkout") is True
    assert comment_data_2.get("order_success") is False
    assert "quá nhanh" in comment_data_2.get("order_error_reason") or "gần đây" in comment_data_2.get("order_error_reason")

    # Lần 3: Giả lập chốt sản phẩm khác 'SP002' sau 2 giây (vẫn nằm trong cooldown 10 giây của user) -> Bị chặn vì chốt quá nhanh
    time.sleep(2)
    comment_data_3 = {
        "username": "spam_user",
        "comment": "Chốt đơn SP002",
        "platform": "Test"
    }
    await processor._process_comment(comment_data_3)
    print(f"Lần 3 (Chốt SP002 sau 2 giây): is_checkout = {comment_data_3.get('is_checkout')}, order_success = {comment_data_3.get('order_success')}, lý do: '{comment_data_3.get('order_error_reason')}'")
    assert comment_data_3.get("is_checkout") is True
    assert comment_data_3.get("order_success") is False
    assert "quá nhanh" in comment_data_3.get("order_error_reason")

    # Lần 4: Giả lập chốt SP002 sau 11 giây (vượt qua cooldown 10s của user, và không trùng SP001) -> Thành công
    time.sleep(9) # 2s trước + 9s = 11s
    comment_data_4 = {
        "username": "spam_user",
        "comment": "Chốt đơn SP002",
        "platform": "Test"
    }
    await processor._process_comment(comment_data_4)
    print(f"Lần 4 (Chốt SP002 sau 11 giây): is_checkout = {comment_data_4.get('is_checkout')}, order_success = {comment_data_4.get('order_success')}")
    assert comment_data_4.get("is_checkout") is True
    assert comment_data_4.get("order_success") is True

    # Lần 5: Giả lập chốt lại SP001 sau 12 giây nữa (vượt cooldown 10s của user, nhưng trùng SP001 trong vòng 30s kể từ lần 1) -> Bị chặn vì trùng sản phẩm gần đây
    time.sleep(12) # Tổng cộng 2 + 9 + 12 = 23 giây kể từ lần 1 (< 30s)
    comment_data_5 = {
        "username": "spam_user",
        "comment": "Chốt đơn SP001",
        "platform": "Test"
    }
    await processor._process_comment(comment_data_5)
    print(f"Lần 5 (Chốt lại SP001 sau 23 giây kể từ lần 1): is_checkout = {comment_data_5.get('is_checkout')}, order_success = {comment_data_5.get('order_success')}, lý do: '{comment_data_5.get('order_error_reason')}'")
    assert comment_data_5.get("is_checkout") is True
    assert comment_data_5.get("order_success") is False
    assert "gần đây" in comment_data_5.get("order_error_reason")

    print("✅ Xác thực chặn spam chốt đơn thành công!")

    # 3. KIỂM THỬ TÁI SINH CÂU TRẢ LỜI KHI HẾT HÀNG LÚC DUYỆT (L1 AUTOPILOT)
    print("\n--- 3. KIỂM THỬ TÁI SINH CÂU TRẢ LỜI KHI HẾT HÀNG LÚC DUYỆT ---")
    
    # Đặt tồn kho SP001 về 0 để mô phỏng hết hàng lúc duyệt
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET quantity = 0 WHERE code = 'SP001'")
    conn.commit()
    conn.close()
    
    # Khách chốt SP001 lúc trước (khi còn hàng)
    comment_approved = {
        "username": "customer_l1",
        "comment": "Chốt chiếc áo SP001 nha em",
        "platform": "Test",
        "answer": "Chúc mừng bạn đã chốt thành công áo SP001!",
        "is_checkout": True,
        "order_success": True,
        "matched_product": db.find_product_by_query("SP001")
    }
    
    # Thực thi duyệt comment này
    await processor.execute_approved_comment(comment_approved)
    
    print(f"Kết quả duyệt sau khi hết hàng: order_success = {comment_approved.get('order_success')}, lý do = '{comment_approved.get('order_error_reason')}'")
    
    # Đảm bảo order_success bị chuyển sang False
    assert comment_approved.get("order_success") is False
    assert comment_approved.get("order_error_reason") == "Sản phẩm đã hết hàng trong kho."
    
    # Khôi phục tồn kho cho SP001 về 50 để phục vụ các bài test khác
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET quantity = 50 WHERE code = 'SP001'")
    conn.commit()
    conn.close()
    
    print("✅ Xác thực tái sinh câu trả lời khi hết hàng lúc duyệt thành công!")

    print("\n✅ TẤT CẢ CÁC BÀI KIỂM THỬ ĐÃ ĐẠT!")

if __name__ == "__main__":
    asyncio.run(main())
