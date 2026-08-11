import subprocess
import time
import logging
from pathlib import Path
from .models import VNyanInstance
from .discovery import VNyanDiscovery

logger = logging.getLogger("VnyanProcess")

class VNyanProcessManager:
    def __init__(self, discovery: VNyanDiscovery):
        self.discovery = discovery
        self._process = None

    def start(self, timeout_sec: int = 15, vmc_port: int = 3333) -> VNyanInstance:
        """Kích hoạt tiến trình VNyan và đợi cho đến khi nó chạy."""
        instance = self.discovery.discover()
        if instance.running:
            logger.info(f"VNyan đã chạy sẵn từ trước (PID: {instance.pid}).")
            return instance
            
        if not instance.executable_path:
            raise RuntimeError("Không tìm thấy tệp chạy VNyan.exe trong hệ thống.")
            
        # Kiểm tra xem cổng UDP có đang bị chiếm không trước khi khởi chạy
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        port_free = False
        try:
            s.bind(("127.0.0.1", vmc_port))
            port_free = True
        except Exception:
            pass
        finally:
            s.close()

        if not port_free:
            owner_pid = "Unknown"
            try:
                output = subprocess.check_output("netstat -ano", shell=True).decode("utf-8", errors="ignore")
                for line in output.splitlines():
                    if f":{vmc_port} " in line or f":{vmc_port}\t" in line or line.strip().endswith(f":{vmc_port}"):
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            owner_pid = parts[-1]
                            break
            except Exception:
                pass
            raise RuntimeError(
                f"Cổng UDP {vmc_port} (VMC) đang bị chiếm bởi tiến trình PID: {owner_pid}. "
                f"Có thể là do một tiến trình VNyan ẩn hoặc phần mềm khác. Hãy tắt nó trước khi chạy tiếp."
            )
            
        try:
            logger.info(f"Khởi chạy VNyan.exe: {instance.executable_path}...")
            self._process = subprocess.Popen([str(instance.executable_path)], shell=False)
            
            # Đợi cho tiến trình hiển thị trong danh sách process
            start_time = time.time()
            while time.time() - start_time < timeout_sec:
                time.sleep(0.5)
                instance = self.discovery.discover()
                if instance.running:
                    logger.info(f"Khởi chạy VNyan thành công (PID: {instance.pid}).")
                    return instance
                    
            raise TimeoutError("Đã quá thời gian chờ (timeout) khởi chạy VNyan.exe.")
        except Exception as e:
            logger.error(f"Lỗi khi bắt đầu khởi chạy VNyan: {e}")
            raise

    def stop(self, vmc_port: int = 3333) -> None:
        """Tắt tiến trình VNyan."""
        instance = self.discovery.discover()
        if not instance.running:
            return
            
        try:
            logger.info(f"Tắt tiến trình VNyan (PID: {instance.pid})...")
            subprocess.run(f"taskkill /F /IM VNyan.exe", shell=True, check=True)
            logger.info("Đã gửi lệnh tắt VNyan thành công. Chờ cổng mạng được giải phóng...")
            
            # Poll để đợi OS thực sự giải phóng cổng UDP
            import socket
            start_wait = time.time()
            while time.time() - start_wait < 5.0:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    s.bind(("127.0.0.1", vmc_port))
                    s.close()
                    logger.info(f"Cổng UDP {vmc_port} đã được giải phóng hoàn toàn.")
                    break
                except Exception:
                    s.close()
                    time.sleep(0.5)
            else:
                logger.warning(f"Cảnh báo: Cổng {vmc_port} vẫn bận sau khi tắt VNyan! Các phiên mới có thể bị lỗi bind().")
                

        except Exception as e:
            logger.error(f"Lỗi khi tắt tiến trình VNyan: {e}")
            raise

    def is_running(self) -> bool:
        return self.discovery.discover().running
