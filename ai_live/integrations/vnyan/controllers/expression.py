import logging
from ..transport.vmc import VMCTransport
from ..avatar.registry import AvatarRegistry
from ..exceptions import CapabilityUnavailable

logger = logging.getLogger("ExpressionController")

class ExpressionController:
    def __init__(self, transport: VMCTransport, registry: AvatarRegistry):
        self.transport = transport
        self.registry = registry

    def set_expression(self, semantic_name: str, value: float) -> bool:
        """Kích hoạt biểu cảm thông qua tên biểu cảm ngữ nghĩa (semantic)."""
        profile = self.registry.current_profile
        if not profile:
            raise CapabilityUnavailable("Chưa có thông tin Avatar Profile được tải.")
            
        expr = profile.expressions
        
        # 1. Tìm ánh xạ ngữ nghĩa trực tiếp
        actual_name = getattr(expr, semantic_name, None)
        if not actual_name:
            actual_name = getattr(expr, f"viseme_{semantic_name.lower()}", None)
            
        # 2. Nếu không tìm thấy, thử tra cứu ngược từ danh sách EXPRESSION_CANDIDATES
        if not actual_name:
            from ..constants import EXPRESSION_CANDIDATES
            name_lower = semantic_name.lower()
            for key, candidates in EXPRESSION_CANDIDATES.items():
                if name_lower in candidates:
                    actual_name = getattr(expr, key, None)
                    if actual_name:
                        break
                        
        # 3. Nếu vẫn không tìm thấy, kiểm tra xem chính tên truyền vào có trong available không
        if not actual_name:
            # Kiểm tra khớp không phân biệt hoa thường trong available
            matched_avail = None
            for avail in expr.available:
                if avail.lower() == semantic_name.lower():
                    matched_avail = avail
                    break
            if matched_avail:
                actual_name = matched_avail
            else:
                raise CapabilityUnavailable(f"Biểu cảm '{semantic_name}' không khả dụng cho avatar này.")
            
        logger.info(f"ExpressionController: Ánh xạ '{semantic_name}' -> '{actual_name}' (Giá trị: {value:.2f})")
        return self.transport.send_blendshape(actual_name, value)
