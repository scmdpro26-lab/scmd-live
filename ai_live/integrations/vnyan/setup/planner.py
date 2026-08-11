import logging
from ..detector import VNyanDetector
from ..config.reader import VNyanConfigReader

logger = logging.getLogger("VNyanPlanner")

class VNyanPlanner:
    def __init__(self, detector: VNyanDetector, reader: VNyanConfigReader):
        self.detector = detector
        self.reader = reader

    def plan_changes(self, vmc_port: int, rest_port: int, ws_port: int) -> list[str]:
        """Lập kế hoạch các thay đổi cấu hình cần áp dụng."""
        data = self.reader.read_settings()
        if not data:
            return ["Tạo mới file settings.json và đồng bộ cổng mạng."]
            
        plans = []
        if data.get("RESTPort") != rest_port:
            plans.append(f"Thay đổi cổng REST: {data.get('RESTPort')} -> {rest_port}")
            
        if data.get("VMCPort") != vmc_port:
            plans.append(f"Thay đổi cổng VMC: {data.get('VMCPort')} -> {vmc_port}")
            
        if data.get("OSCPort") != vmc_port - 1:
            plans.append(f"Thay đổi cổng OSC: {data.get('OSCPort')} -> {vmc_port - 1}")
            
        if data.get("WebSocketPort") != ws_port:
            plans.append(f"Thay đổi cổng WebSocket: {data.get('WebSocketPort')} -> {ws_port}")
            
        if data.get("VMCSenderActive") is not True:
            plans.append("Bật VMCSenderActive (kích hoạt cổng UDP 39540)")
            
        return plans
