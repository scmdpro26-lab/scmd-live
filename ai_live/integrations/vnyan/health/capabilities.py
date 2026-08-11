import logging
from ..avatar.registry import AvatarRegistry

logger = logging.getLogger("VNyanCapabilities")

class VNyanCapabilities:
    def __init__(self, registry: AvatarRegistry):
        self.registry = registry

    def check_capabilities(self) -> dict[str, bool]:
        """Kiểm tra các năng lực (capability) của avatar hiện tại."""
        profile = self.registry.current_profile
        result = {
            "viseme": False,
            "emotion": False,
            "blink": False
        }
        if not profile:
            return result
            
        expr = profile.expressions
        
        if expr.viseme_a and expr.viseme_e and expr.viseme_i and expr.viseme_o and expr.viseme_u:
            result["viseme"] = True
            
        if expr.happy and expr.sad and expr.angry:
            result["emotion"] = True
            
        if expr.blink or (expr.blink_left and expr.blink_right):
            result["blink"] = True
            
        return result
