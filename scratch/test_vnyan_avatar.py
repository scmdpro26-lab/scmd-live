import time
import sys
import os

# Thêm thư mục gốc vào PYTHONPATH để import vmc_client
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.vmc_client import VMCClient

def run_avatar_test():
    print("=== BẮT ĐẦU KIỂM THỬ AVATAR MỘT CÁCH TRỰC TIẾP TRÊN VNYAN ===")
    print("Kết nối VMC OSC Clients (VMC Port: 3333, OSC Port: 39539)...")
    vmc = VMCClient(ip="127.0.0.1", vmc_port=3333, osc_port=39539)

    
    # Đợi 1 giây để cổng kết nối ổn định
    time.sleep(1.0)
    
    print("\n--- 1. Kiểm tra chuyển động nhép môi (Lipsync) ---")
    print("Đang nhép miệng mở to và nhỏ dần (Blendshape MouthOpen)...")
    for i in range(5):
        # Mở miệng 0.8
        vmc.send_blendshape("MouthOpen", 0.8)
        vmc.send_blendshape("A", 0.8)
        time.sleep(0.3)
        # Đóng miệng 0.1
        vmc.send_blendshape("MouthOpen", 0.1)
        vmc.send_blendshape("A", 0.1)
        time.sleep(0.3)
    
    # Trả về 0 để đóng miệng hẳn
    vmc.send_blendshape("MouthOpen", 0.0)
    vmc.send_blendshape("A", 0.0)
    print("✅ Kiểm tra Lipsync hoàn thành.")

    print("\n--- 2. Kiểm tra biểu cảm Joy (Vui vẻ) ---")
    print("Kích hoạt biểu cảm Joy trong 3 giây...")
    vmc.trigger_expression("Joy", duration=3.0)
    time.sleep(3.5)
    print("✅ Cảm xúc Joy đã tắt.")

    print("\n--- 3. Kiểm tra biểu cảm Sorrow (Buồn/Hối lỗi) ---")
    print("Kích hoạt biểu cảm Sorrow trong 3 giây...")
    vmc.trigger_expression("Sorrow", duration=3.0)
    time.sleep(3.5)
    print("✅ Cảm xúc Sorrow đã tắt.")

    print("\n--- 4. Kiểm tra biểu cảm Surprise (Ngạc nhiên) ---")
    print("Kích hoạt biểu cảm Surprise trong 3 giây...")
    vmc.trigger_expression("Surprise", duration=3.0)
    time.sleep(3.5)
    print("✅ Cảm xúc Surprise đã tắt.")

    print("\n--- 5. Kiểm tra lệnh hành động tùy biến (Custom OSC Actions) ---")
    print("Gửi lệnh chốt đơn thành công: /VMC/Ext/Action/CheckoutSuccess...")
    vmc.trigger_checkout_success("Áo Thun Cotton Basic")
    time.sleep(1.5)
    
    print("Gửi lệnh xin lỗi cúi đầu: /VMC/Ext/Action/Apology...")
    vmc.trigger_apology(duration=3.0)
    time.sleep(3.5)

    print("Gửi lệnh cúi chào (Greeting): /VMC/Ext/Action/Greeting...")
    vmc.trigger_greeting()
    time.sleep(2.0)
    
    print("Gửi lệnh vỗ tay (Clap): /VMC/Ext/Action/Clap...")
    vmc.trigger_clap()
    time.sleep(2.0)

    print("Gửi lệnh bắn tim (Heart): /VMC/Ext/Action/Heart...")
    vmc.trigger_heart()
    time.sleep(2.0)

    print("Gửi lệnh chỉ tay lên (Point Up): /VMC/Ext/Action/PointUp...")
    vmc.trigger_point_up()
    time.sleep(2.0)

    print("Gửi lệnh nhảy múa ăn mừng (Dance): /VMC/Ext/Action/Dance...")
    vmc.trigger_dance()
    time.sleep(3.5)
 
    print("\n🎉 KIỂM THỬ AVATAR HOÀN TẤT THÀNH CÔNG!")
    print("Nếu avatar trên màn hình VNyan của bạn đã cử động môi, thay đổi biểu cảm và phản hồi tất cả hành động mới, kết nối đã hoạt động hoàn hảo!")

if __name__ == "__main__":
    run_avatar_test()
