import json
import os
import shutil

def main():
    user_profile = os.environ.get("USERPROFILE", "C:/Users/quanying_zhang")
    vnyan_config_dir = os.path.join(user_profile, "AppData", "LocalLow", "Suvidriel", "VNyan")
    settings_path = os.path.join(vnyan_config_dir, "settings.json")
    
    if not os.path.exists(settings_path):
        print(f"❌ Không tìm thấy tệp settings.json của VNyan tại: {settings_path}")
        print("Vui lòng khởi chạy phần mềm VNyan ít nhất một lần để tạo cấu hình mặc định.")
        return
        
    print(f"🔍 Tìm thấy cấu hình VNyan tại: {settings_path}")
    
    # Tạo bản sao lưu trước khi chỉnh sửa
    backup_path = settings_path + ".bak_autolive"
    shutil.copy2(settings_path, backup_path)
    print(f"📦 Đã tạo bản sao lưu tại: {backup_path}")
    
    try:
        # Đọc dữ liệu cấu hình hiện tại
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # Cập nhật các thông số OSC & VMC Client Ports
        print("⚙️ Đang cấu hình tự động các cổng mạng...")
        data["OSCPort"] = "39539"            # Cổng nhận OSC của VNyan
        data["VMCSenderPort"] = 39540        # Cổng gửi Feedback về cho AI Live Studio
        data["VMCSenderActive"] = True       # Kích hoạt tính năng gửi Feedback
        data["VMCSenderIP"] = "127.0.0.1"    # Địa chỉ IP nội bộ
        
        # Ghi đè lại tệp cấu hình một cách an toàn (Atomic write)
        temp_path = settings_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
            
        os.replace(temp_path, settings_path)
        print("✅ Đã cấu hình thành công các thông số mạng cho VNyan!")
        print("ℹ️ Chi tiết cấu hình:")
        print("   - OSC Port (Cổng nhận tín hiệu): 39539")
        print("   - Feedback Port (Cổng gửi phản hồi): 39540")
        print("   - Feedback Status: Active (Đã kích hoạt)")
        print("\n👉 Hãy khởi động lại VNyan để các thay đổi có hiệu lực.")
        
    except Exception as e:
        print(f"❌ Lỗi khi tự động cấu hình VNyan: {e}")
        # Khôi phục từ bản sao lưu nếu có lỗi
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, settings_path)
            print("🔄 Đã khôi phục lại cấu hình gốc từ bản sao lưu.")

if __name__ == "__main__":
    main()
