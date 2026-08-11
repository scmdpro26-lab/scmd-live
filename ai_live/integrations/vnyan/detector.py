import os
import winreg
import logging
from pathlib import Path
from src.config import Config

logger = logging.getLogger("VnyanDetector")

class VNyanDetector:
    def __init__(self):
        self.user_profile = os.environ.get("USERPROFILE", "C:/Users/quanying_zhang")
        self.config_dir = Path(self.user_profile) / "AppData" / "LocalLow" / "Suvidriel" / "VNyan"

    def get_config_dir(self) -> Path:
        return self.config_dir

    def get_settings_path(self) -> Path:
        return self.config_dir / "settings.json"

    def detect_vnyan_exe(self) -> Path | None:
        """Dò quét đường dẫn chạy file VNyan.exe từ cấu hình hoặc các vị trí mặc định."""
        # 1. Kiểm tra cấu hình trong Config
        config_path = Config.VNYAN_EXE_PATH
        if config_path and Path(config_path).exists():
            return Path(config_path)

        # 2. Kiểm tra thư mục dự án cục bộ vnyan/
        local_path = Path(os.getcwd()) / "vnyan" / "VNyan.exe"
        if local_path.exists():
            return local_path

        # 3. Dò tìm trong các ổ đĩa thông dụng
        common_paths = [
            Path("C:/Program Files/VNyan/VNyan.exe"),
            Path("C:/Program Files (x86)/VNyan/VNyan.exe"),
            Path("D:/VNyan/VNyan.exe"),
            Path("E:/VNyan/VNyan.exe"),
        ]
        for path in common_paths:
            if path.exists():
                return path

        # 4. Thử tìm từ registry Windows (Uninstall info)
        registry_path = self._detect_from_registry()
        if registry_path:
            return registry_path

        return None

    def _detect_from_registry(self) -> Path | None:
        """Dò tìm đường dẫn VNyan từ registry của Windows."""
        for hive, key_path in [
            (winreg.HKEY_CURRENT_USER, r"Software\Suvidriel\VNyan"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\VNyan")
        ]:
            try:
                with winreg.OpenKey(hive, key_path) as key:
                    val, _ = winreg.QueryValueEx(key, "InstallLocation")
                    if val:
                        exe = Path(val) / "VNyan.exe"
                        if exe.exists():
                            return exe
            except Exception:
                pass
        return None
