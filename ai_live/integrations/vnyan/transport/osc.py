import logging

logger = logging.getLogger("OSCTransport")

class OSCTransport:
    def __init__(self, ip: str, port: int):
        self.ip = ip
        self.port = port
        logger.warning("OSCTransport đã bị phản đối (Deprecated). Vui lòng sử dụng HTTPTransport hoặc VMCTransport.")

    def send_osc_message(self, path: str, arguments: list) -> bool:
        logger.warning(f"OSCTransport: Đang gửi tin nhắn OSC dự phòng: {path} -> {arguments}")
        return False
