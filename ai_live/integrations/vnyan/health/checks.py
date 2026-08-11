import socket
import logging

logger = logging.getLogger("VNyanHealthChecker")

class VNyanHealthChecker:
    def __init__(self, host: str, rest_port: int, vmc_port: int):
        self.host = host
        self.rest_port = rest_port
        self.vmc_port = vmc_port

    def check_tcp_port(self, port: int) -> bool:
        """Kiểm tra xem một cổng TCP có phản hồi kết nối trên host hay không."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        try:
            s.connect((self.host, port))
            s.close()
            return True
        except Exception:
            return False

    def is_api_online(self) -> bool:
        """Kiểm tra xem REST API của VNyan có thực sự hoạt động và phản hồi yêu cầu POST hay không (round-trip check)."""
        import urllib.request
        import json
        url = f"http://{self.host}:{self.rest_port}/"
        payload = {"action": "ping", "payload": {}}
        req_body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=1.0) as response:
                return response.status == 200
        except Exception:
            return False

    def is_vmc_online(self) -> bool:
        """Kiểm tra xem VMC UDP Port có đang được lắng nghe mà KHÔNG bind gây xung đột cổng với VNyan.exe."""
        try:
            import subprocess
            output = subprocess.check_output("netstat -ano", shell=True, text=True, stderr=subprocess.DEVNULL)
            for line in output.splitlines():
                if "UDP" in line and f":{self.vmc_port}" in line:
                    return True
            return False
        except Exception:
            pass

        # Fallback phụ nếu subprocess không khả thi
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.bind(("127.0.0.1", self.vmc_port))
            s.close()
            return False
        except Exception:
            return True
