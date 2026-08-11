import logging
from ..transport.http import HTTPTransport

logger = logging.getLogger("VNyanEventBridge")

class VNyanEventBridge:
    def __init__(self, transport: HTTPTransport):
        self.transport = transport

    def send(self, action: str, payload: dict | None = None) -> bool:
        """Gửi sự kiện trigger tập trung thông qua HTTP REST API."""
        if payload is None:
            payload = {}
            
        logger.info(f"VNyanEventBridge: Gửi sự kiện '{action}' với payload: {payload}")
        return self.transport.send_post(action, payload)
