import json
import urllib.request
import logging

logger = logging.getLogger("HTTPTransport")

class HTTPTransport:
    def __init__(self, ip: str, port: int):
        self.ip = ip
        self.port = port
        self.url = f"http://{self.ip}:{self.port}/"

    def send_post(self, action_name: str, payload_dict: dict = None) -> bool:
        """Gửi HTTP POST JSON và chờ kết quả thực tế để kiểm tra trạng thái thành công."""
        if payload_dict is None:
            payload_dict = {}
            
        payload = {
            "action": action_name,
            "payload": payload_dict
        }
        
        req_body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.url,
            data=req_body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=1.0) as response:
                if response.status == 200:
                    return True
                else:
                    logger.warning(f"HTTPTransport: REST API trả về status {response.status} cho '{action_name}'")
                    return False
        except Exception as e:
            logger.error(f"HTTPTransport: Gửi thất bại event '{action_name}' tới {self.url}: {e}")
            return False
