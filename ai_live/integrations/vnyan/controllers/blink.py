import time
import logging
import threading
from ..transport.vmc import VMCTransport
from ..avatar.registry import AvatarRegistry
from ..exceptions import CapabilityUnavailable

logger = logging.getLogger("BlinkController")

class BlinkController:
    def __init__(self, transport: VMCTransport, registry: AvatarRegistry):
        self.transport = transport
        self.registry = registry

    def blink(self, duration_ms: int = 120):
        """Kích hoạt hiệu ứng nháy mắt nháy mắt."""
        profile = self.registry.current_profile
        if not profile:
            raise CapabilityUnavailable("Chưa có thông tin Avatar Profile được tải.")
            
        expr = profile.expressions
        
        # Xác định các blendshape nháy mắt khả dụng
        blendshapes = []
        if expr.blink:
            blendshapes.append(expr.blink)
        elif expr.blink_left and expr.blink_right:
            blendshapes.append(expr.blink_left)
            blendshapes.append(expr.blink_right)
            
        if not blendshapes:
            logger.warning("BlinkController: Cả blink lẫn blink_left/right đều không khả dụng cho avatar này.")
            raise CapabilityUnavailable("Khả năng nháy mắt không khả dụng trên avatar này.")
            
        def run_blink():
            for bs in blendshapes:
                self.transport.send_blendshape(bs, 1.0)
            time.sleep(duration_ms / 1000.0)
            for bs in blendshapes:
                self.transport.send_blendshape(bs, 0.0)
                
        threading.Thread(target=run_blink, daemon=True).start()
        return True
