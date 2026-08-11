import subprocess
import logging
from pathlib import Path
from .models import VNyanInstance
from .detector import VNyanDetector

logger = logging.getLogger("VnyanDiscovery")

class VNyanDiscovery:
    def __init__(self, detector: VNyanDetector):
        self.detector = detector

    def discover(self) -> VNyanInstance:
        """Thực hiện dò quét và trả về thông tin thực tế của VNyanInstance."""
        executable_path = self.detector.detect_vnyan_exe()
        
        running = False
        pid = None
        
        # Kiểm tra qua tasklist trên Windows
        try:
            output = subprocess.check_output(
                'tasklist /FI "IMAGENAME eq VNyan.exe" /FO CSV /NH',
                shell=True,
                text=True
            )
            if "VNyan.exe" in output:
                running = True
                # Parse PID from CSV format e.g. "VNyan.exe","1234","Console","1",...
                parts = output.split(",")
                if len(parts) > 1:
                    pid_str = parts[1].strip('"')
                    if pid_str.isdigit():
                        pid = int(pid_str)
        except Exception as e:
            logger.error(f"Lỗi khi dò quét PID của VNyan: {e}")
            
        settings_path = self.detector.get_settings_path()
        api_port = None
        vmc_port = None
        osc_port = None
        
        if settings_path.exists():
            import json
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    api_port = data.get("RESTPort")
                    vmc_port = data.get("VMCPort")
                    osc_port = data.get("OSCPort")
            except Exception:
                pass
                
        return VNyanInstance(
            executable_path=executable_path,
            pid=pid,
            host="127.0.0.1",
            api_port=api_port,
            vmc_port=vmc_port,
            osc_port=osc_port,
            running=running,
            version=None  # Sẽ được cập nhật khi API sẵn sàng
        )
