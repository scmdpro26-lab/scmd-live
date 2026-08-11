import logging
from pathlib import Path
from ..models import AvatarProfile
from .profile import AvatarProfileManager
from .inspector import VRMInspector

logger = logging.getLogger("AvatarRegistry")

class AvatarRegistry:
    def __init__(self, profile_manager: AvatarProfileManager, inspector: VRMInspector):
        self.profile_manager = profile_manager
        self.inspector = inspector
        self._current_profile = None

    def get_profile(self, filepath: Path) -> AvatarProfile:
        """Lấy profile của tệp avatar, nạp từ cache hoặc inspect mới."""
        profile = self.profile_manager.load_profile(filepath)
        if profile:
            logger.info(f"Đã tìm thấy Avatar Profile sẵn có từ cache cho {filepath.name}")
            self._current_profile = profile
            return profile
            
        # Inspect mới
        logger.info(f"Không tìm thấy cache. Tiến hành phân tích mới tệp {filepath.name}...")
        profile = self.inspector.inspect(filepath)
        self.profile_manager.save_profile(profile)
        self._current_profile = profile
        return profile

    @property
    def current_profile(self) -> AvatarProfile | None:
        return self._current_profile
