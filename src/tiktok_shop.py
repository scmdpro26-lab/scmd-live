import logging
import asyncio
from typing import Dict, Any, Optional
import src.database as db
from src.event_broker import global_broker
from src.vmc_service import get_vmc_client

logger = logging.getLogger("TikTokShopCart")

class TikTokShopCart:
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(TikTokShopCart, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.pinned_product_code: Optional[str] = None

    async def pin_product(self, product_code: str) -> bool:
        """Ghim sản phẩm trong giỏ hàng TikTok Live Shop."""
        if not product_code:
            return await self.unpin_product()

        async with self._lock:
            if self.pinned_product_code == product_code:
                # Đã ghim sản phẩm này rồi
                return True

            # Tìm kiếm thông tin sản phẩm trong database
            product = await asyncio.to_thread(db.find_product_by_query, product_code)
            if not product:
                logger.warning(f"Không thể ghim sản phẩm vì không tìm thấy mã '{product_code}' trong cơ sở dữ liệu.")
                return False

            if product.get("quantity", 0) <= 0:
                logger.warning(f"Sản phẩm {product_code} đã hết hàng. Không thể ghim.")
                return False

            self.pinned_product_code = product_code
            logger.info(f"📍 Đã ghim sản phẩm: {product['name']} ({product_code}) vào giỏ hàng TikTok Live.")

            # Gửi lệnh VMC OSC cho MC ảo nhép cử chỉ chỉ tay vào giỏ hàng
            try:
                vmc_client = get_vmc_client()
                if hasattr(vmc_client, "trigger_cart_pin"):
                    vmc_client.trigger_cart_pin(product_code, product["name"])
            except Exception as e:
                logger.error(f"Lỗi gửi OSC ghim giỏ hàng: {e}")

            # Gửi sự kiện cập nhật giỏ hàng lên Event Broker
            event_data = {
                "pinned_product_code": self.pinned_product_code,
                "product_name": product["name"],
                "product_price": product["price"]
            }
            await global_broker.publish("tiktok_cart_updated", event_data)
            
            # Gửi log thông báo
            system_log = f"📍 [TikTok Shop] Ghim sản phẩm '{product['name']}' ({product_code}) vào giỏ hàng thành công!"
            await global_broker.publish("system_log_event", system_log)
            
            return True


    async def unpin_product(self) -> bool:
        """Hủy ghim sản phẩm khỏi giỏ hàng TikTok Live Shop."""
        async with self._lock:
            if self.pinned_product_code is None:
                return True

            old_code = self.pinned_product_code
            self.pinned_product_code = None
            logger.info(f"📍 Hủy ghim sản phẩm ({old_code}) khỏi giỏ hàng TikTok Live.")

            # Gửi sự kiện cập nhật lên Event Broker
            event_data = {
                "pinned_product_code": None,
                "product_name": None,
                "product_price": None
            }
            await global_broker.publish("tiktok_cart_updated", event_data)

            # Gửi log thông báo
            system_log = f"📍 [TikTok Shop] Hủy ghim sản phẩm khỏi giỏ hàng TikTok Live."
            await global_broker.publish("system_log_event", system_log)

            return True

    async def get_pinned_product(self) -> Optional[Dict[str, Any]]:
        """Lấy thông tin chi tiết của sản phẩm đang được ghim."""
        if not self.pinned_product_code:
            return None
        return await asyncio.to_thread(db.find_product_by_query, self.pinned_product_code)

# Singleton global instance
global_tiktok_shop = TikTokShopCart()
