import logging
from ..transport.vmc import VMCTransport
from ..avatar.registry import AvatarRegistry
from ..exceptions import CapabilityUnavailable

logger = logging.getLogger("VisemeController")

class VisemeController:
    def __init__(self, transport: VMCTransport, registry: AvatarRegistry):
        self.transport = transport
        self.registry = registry

    def set_viseme(self, viseme: str, intensity: float) -> bool:
        """Thiết lập khẩu hình miệng phát âm (viseme: A, E, I, O, U)."""
        profile = self.registry.current_profile
        if not profile:
            raise CapabilityUnavailable("Chưa có thông tin Avatar Profile được tải.")
            
        expr = profile.expressions
        # Trực quan hóa tên viseme ngữ nghĩa sang key trong dataclass (viseme_a, viseme_e...)
        viseme_key = f"viseme_{viseme.lower()}"
        actual_name = getattr(expr, viseme_key, None)
        
        if not actual_name:
            logger.warning(f"VisemeController: Không tìm thấy mapping cho khẩu hình '{viseme}'")
            raise CapabilityUnavailable(f"Khả năng nhép miệng '{viseme}' không khả dụng cho avatar này.")
            
        return self.transport.send_blendshape(actual_name, intensity)
