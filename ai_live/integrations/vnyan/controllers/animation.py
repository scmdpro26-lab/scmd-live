import logging
from ..transport.vmc import VMCTransport
from ..bridge.events import VNyanEventBridge
from ..constants import CANONICAL_ACTIONS

logger = logging.getLogger("AnimationController")

class AnimationController:
    def __init__(self, vmc: VMCTransport, bridge: VNyanEventBridge = None):
        self.vmc = vmc
        self.bridge = bridge

    def resolve_action_name(self, action_name: str) -> str:
        """Đồng bộ và ánh xạ tên action về danh mục duy nhất CANONICAL_ACTIONS."""
        name_lower = action_name.lower().replace("-", "_")
        return CANONICAL_ACTIONS.get(name_lower, action_name)

    def trigger_animation(self, action_id: str, arguments: list | None = None) -> tuple[bool, str]:
        """Kích hoạt hoạt ảnh động tác MC thông qua REST HTTP (chính) và VMC UDP (fallback).

        Returns:
            Tuple (success, transport_protocol)
        """
        if arguments is None:
            arguments = []

        # 1. Gửi qua Event Bridge (REST HTTP - Kênh chính)
        http_success = False
        if self.bridge:
            payload = {}
            for i, arg in enumerate(arguments):
                payload[f"text{i+1}"] = str(arg)
            try:
                http_success = self.bridge.send(action_id, payload)
            except Exception as e:
                logger.warning(f"REST HTTP dispatch failed for {action_id}: {e}. Falling back to VMC UDP.")
                http_success = False

        # Nếu kênh chính HTTP thành công, kết thúc ngay lập tức (Single Execution)
        if http_success:
            return True, "HTTP"

        # 2. Gửi qua VMC UDP (Kênh phụ) - Chỉ kích hoạt làm fallback
        logger.info(f"REST HTTP not available or failed. Falling back to VMC UDP for {action_id}.")
        udp_success = self.vmc.send_trigger(action_id, arguments)
        return udp_success, "UDP_FALLBACK" if udp_success else "NONE"




    # --- 10 ACTION MAPPING DUY NHẤT ---
    def trigger_greeting(self) -> bool:
        return self.trigger_animation("greeting")

    def trigger_clap(self) -> bool:
        return self.trigger_animation("clap")

    def trigger_heart(self) -> bool:
        return self.trigger_animation("heart")

    def trigger_point_up(self) -> bool:
        return self.trigger_animation("point_up")

    def trigger_dance(self) -> bool:
        return self.trigger_animation("dance")

    def trigger_apology(self, duration: float = 3.0) -> bool:
        return self.trigger_animation("apology", [float(duration)])

    def trigger_voucher_drop(self) -> bool:
        return self.trigger_animation("voucher_drop")

    def trigger_minigame_start(self) -> bool:
        return self.trigger_animation("minigame_start")

    def trigger_cart_pin(self, product_code: str, product_name: str) -> bool:
        return self.trigger_animation("cart_pin", [product_code, product_name])

    def trigger_checkout_success(self, product_name: str) -> bool:
        return self.trigger_animation("checkout_success", [product_name])

    # --- 5 ACTION E-COMMERCE MỚI ---
    def trigger_point_down(self) -> bool:
        """Chỉ tay xuống giỏ hàng / khu vực mua hàng phía dưới màn hình."""
        return self.trigger_animation("point_down")

    def trigger_present_left(self) -> bool:
        """Giới thiệu sản phẩm/slide bên trái màn hình."""
        return self.trigger_animation("present_left")

    def trigger_present_right(self) -> bool:
        """Giới thiệu sản phẩm/slide bên phải màn hình."""
        return self.trigger_animation("present_right")

    def trigger_celebrate(self) -> bool:
        """Ăn mừng lớn khi có đơn hàng giá trị cao hoặc đạt milestone."""
        return self.trigger_animation("celebrate")

    def trigger_voucher_show(self) -> bool:
        """Trưng bày voucher/mã giảm giá trước camera."""
        return self.trigger_animation("voucher_show")

