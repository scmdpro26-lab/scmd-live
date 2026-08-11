import os
import json
import logging
from pathlib import Path
from ..detector import VNyanDetector
from .reader import VNyanConfigReader

logger = logging.getLogger("VnyanConfigWriter")

class VNyanConfigWriter:
    def __init__(self, detector: VNyanDetector, reader: VNyanConfigReader):
        self.detector = detector
        self.reader = reader

    def write_settings(self, data: dict) -> bool:
        """Ghi tệp tin settings.json an toàn (Atomic write)."""
        path = self.detector.get_settings_path()
        try:
            temp_path = str(path) + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            os.replace(temp_path, str(path))
            return True
        except Exception as e:
            logger.error(f"Lỗi khi ghi tệp tin settings.json: {e}")
            return False

    def sync_network_settings(self, vmc_port: int, rest_port: int, ws_port: int) -> list[str]:
        """Đồng bộ các thông số cổng mạng VMC/REST/WS trong settings.json. Trả về danh sách các thay đổi."""
        data = self.reader.read_settings()
        if not data:
            logger.warning("Không thể đồng bộ vì không đọc được settings.json.")
            return []
            
        changes = []
        
        if data.get("RESTPort") != rest_port:
            old = data.get("RESTPort")
            data["RESTPort"] = rest_port
            changes.append(f"RESTPort: {old} -> {rest_port}")
            
        if data.get("VMCPort") != vmc_port:
            old = data.get("VMCPort")
            data["VMCPort"] = vmc_port
            changes.append(f"VMCPort: {old} -> {vmc_port}")
            
        if data.get("OSCPort") != vmc_port - 1:
            old = data.get("OSCPort")
            data["OSCPort"] = vmc_port - 1
            changes.append(f"OSCPort: {old} -> {vmc_port - 1}")
            
        if data.get("WebSocketPort") != ws_port:
            old = data.get("WebSocketPort")
            data["WebSocketPort"] = ws_port
            changes.append(f"WebSocketPort: {old} -> {ws_port}")
            
        if data.get("VMCSenderActive") is not True:
            data["VMCSenderActive"] = True
            changes.append("VMCSenderActive: OFF -> ON (Kích hoạt cổng feedback 39540)")

        # Cấu hình VMC Layers
        layers = data.get("VMCLayers", [])
        if layers and isinstance(layers, list) and len(layers) > 0:
            if str(layers[0].get("port")) != str(vmc_port) or float(layers[0].get("trackBlendshapes", 0.0)) != 1.0:
                layers[0]["port"] = str(vmc_port)
                layers[0]["trackBlendshapes"] = 1.0
                changes.append(f"VMCLayers[0]: port={vmc_port}, trackBlendshapes=1.0")
                    
        if changes:
            self.write_settings(data)
            logger.info(f"Đã đồng bộ cấu hình mạng VNyan. Các thay đổi: {changes}")
            
        return changes
