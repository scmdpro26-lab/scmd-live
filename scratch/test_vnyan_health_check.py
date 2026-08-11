import sys
import os
import asyncio
import socket
import time
import threading

# Thêm thư mục gốc vào PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vmc_client import VMCClient

# Hàm chạy mock TCP server để chấp nhận kết nối và đóng ngay
def run_mock_server(server_sock, stop_event):
    server_sock.settimeout(0.5)
    while not stop_event.is_set():
        try:
            conn, addr = server_sock.accept()
            try:
                conn.recv(1024)
            except Exception:
                pass
            response = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 2\r\n\r\n{}"
            conn.sendall(response)
            conn.close()
        except socket.timeout:
            continue
        except Exception:
            break

async def main():
    print("=== START TEST: VNYAN TCP HEALTH-CHECK V2 ===")
    
    # Khởi tạo VMCClient với cổng test khác để tránh đè cổng chạy thật
    test_rest_port = 8899
    vmc = VMCClient(rest_port=test_rest_port)
    vmc.check_vnyan_connection = lambda: vmc.manager.health_checker.is_api_online()
    
    # 1. Ban đầu không có server lắng nghe trên cổng test_rest_port, kết nối phải là False
    print(f"1. Ban đầu (chưa bật server): renderer_online = {vmc.renderer_online}")
    await asyncio.sleep(1.2) # Chờ luồng background chạy lần đầu tiên
    assert vmc.renderer_online is False, "Lỗi: Lẽ ra phải báo offline khi cổng chưa mở!"
    
    # 2. Bật TCP server giả lập trên cổng test_rest_port
    print(f"\n2. [Giả lập] Khởi tạo TCP listener trên cổng {test_rest_port}...")
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(("127.0.0.1", test_rest_port))
    server_sock.listen(5)
    
    stop_event = threading.Event()
    server_thread = threading.Thread(target=run_mock_server, args=(server_sock, stop_event), daemon=True)
    server_thread.start()
    
    # Chờ luồng background cập nhật renderer_online
    print("   Đợi luồng background cập nhật trạng thái...")
    for _ in range(60):
        await asyncio.sleep(0.1)
        if vmc.renderer_online:
            break
            
    print(f"   Trạng thái sau khi mở cổng: renderer_online = {vmc.renderer_online} (Phải là True)")
    assert vmc.renderer_online is True, "Lỗi: Luồng background chưa cập nhật renderer_online thành True!"
    print("✅ Thành công: Nhận diện Renderer Online thông qua TCP connection.")
    
    # 3. Đóng server để mô phỏng mất kết nối
    print(f"\n3. [Giả lập] Đóng TCP listener trên cổng {test_rest_port}...")
    stop_event.set()
    server_sock.close()
    server_thread.join(timeout=1.0)
    
    # Chờ luồng background cập nhật renderer_online thành False
    print("   Đợi luồng background cập nhật trạng thái...")
    for _ in range(60):
        await asyncio.sleep(0.1)
        if not vmc.renderer_online:
            break
            
    print(f"   Trạng thái sau khi đóng cổng: renderer_online = {vmc.renderer_online} (Phải là False)")
    assert vmc.renderer_online is False, "Lỗi: Luồng background chưa cập nhật renderer_online thành False!"
    print("✅ Thành công: Tự động chuyển Renderer sang Offline khi ngắt kết nối.")
    
    # Dừng luồng health check
    vmc.disconnect()
    print("\n✅ KẾT QUẢ: Hệ thống TCP health-check VNyan hoạt động hoàn hảo 100%!")
    sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
