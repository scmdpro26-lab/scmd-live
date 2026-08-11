import sys
import os
import asyncio

# Thêm thư mục gốc vào PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai_brain import AIBrain
from src.priority_queue import PriorityQueueProcessor

async def main():
    print("=== START TEST: AI-AUGMENTED MODERATION ENGINE ===")
    
    ai = AIBrain()
    
    # Tạo processor giả lập để test
    processor = PriorityQueueProcessor(ai_brain=ai, tts_engine=None, obs_client=None)
    
    # 1. Các trường hợp bình luận LÀNH MẠNH (CLEAN) -> Không được chặn
    clean_comments = [
        "áo SP001 bao nhiêu shop ơi",
        "cho mình hỏi ship đi Đà Nẵng bao lâu",
        "chất vải cotton co giãn tốt không em",
        "hello shop nha chúc shop đắt khách"
    ]
    
    print("\n--- 1. KIỂM THỬ BÌNH LUẬN LÀNH MẠNH ---")
    for comm in clean_comments:
        is_mod = await processor.is_moderated(comm)
        print(f"Bình luận: '{comm}' | Bị chặn: {is_mod}")
        assert is_mod is False, f"Lỗi: Chặn nhầm bình luận lành mạnh: '{comm}'"
    print("✅ Xác thực bình luận lành mạnh thành công!")

    # 2. Các trường hợp SPAM link đối thủ / thông tin kéo khách tinh vi -> Bắt buộc chặn
    spam_comments = [
        "mua đồ rẻ hơn bên link_doi_thu.com này",
        "qua shopee đối thủ mua kìa rẻ lắm",
        "kết bạn z-a-l-o số 090 123 4567 để mua giá sỉ",
        "liên hệ qua z a l o nhận link sale 70%",
        "lh sđt 0.9.0.1.2.3.4.5.6 để mua hàng sỉ lẻ",
        "mua bên shop doi thu giá rẻ một nửa"
    ]
    
    print("\n--- 2. KIỂM THỬ SPAM LINK ĐỐI THỦ TINH VI ---")
    for comm in spam_comments:
        is_mod = await processor.is_moderated(comm)
        print(f"Bình luận: '{comm}' | Bị chặn: {is_mod}")
        assert is_mod is True, f"Lỗi: Không chặn được spam đối thủ tinh vi: '{comm}'"
    print("✅ Xác thực chặn spam đối thủ thành công!")

    # 3. Các trường hợp biến thể từ tục cách điệu -> Bắt buộc chặn
    vulgar_comments = [
        "đ.é.o mua nữa",
        "d e o shop làm ăn chán quá",
        "đjt mẹ",
        "l0n",
        "c*c",
        "d\t\te\t\to"
    ]
    
    print("\n--- 3. KIỂM THỬ BIẾN THỂ TỪ TỤC CÁCH ĐIỆU ---")
    for comm in vulgar_comments:
        is_mod = await processor.is_moderated(comm)
        print(f"Bình luận: '{comm}' | Bị chặn: {is_mod}")
        assert is_mod is True, f"Lỗi: Không chặn được từ tục cách điệu: '{comm}'"
    print("✅ Xác thực chặn từ tục cách điệu thành công!")

    print("\n✅ KẾT QUẢ: Hệ thống AI Moderation hoạt động hoàn hảo 100%!")

if __name__ == "__main__":
    asyncio.run(main())
