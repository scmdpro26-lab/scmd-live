import json
import logging
from pathlib import Path
from ..detector import VNyanDetector

logger = logging.getLogger("VnyanConfigReader")

class VNyanConfigReader:
    def __init__(self, detector: VNyanDetector):
        self.detector = detector

    def read_settings(self) -> dict:
        """Đọc và giải nén tệp tin settings.json."""
        path = self.detector.get_settings_path()
        if not path.exists():
            logger.warning(f"Tệp tin settings.json không tồn tại tại {path}.")
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Lỗi khi đọc settings.json: {e}")
            return {}
