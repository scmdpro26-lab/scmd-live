import asyncio
import logging
from src.connectors.base import BaseConnector

logger = logging.getLogger("FacebookConnector")

class FacebookConnector(BaseConnector):
    def __init__(self):
        super().__init__("Facebook")

    async def _run_loop(self):
        logger.info("Facebook Webhook Connector đang hoạt động và lắng nghe các sự kiện webhook...")
        try:
            # Vòng lặp chờ vô hạn cho đến khi connector bị dừng
            while self.is_running:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            logger.info("Facebook Webhook Connector đã dừng lắng nghe.")

    async def handle_webhook_comment(self, username: str, comment: str):
        """Hàm nhận thông tin comment được xác thực từ webhook endpoint và gửi vào hệ thống."""
        if not self.is_running:
            logger.warning(f"Bỏ qua comment từ {username} vì Facebook Connector chưa được bật trên giao diện.")
            return
            
        logger.info(f"[Facebook Webhook Feed] Bình luận từ {username}: {comment}")
        await self.emit_comment(username, comment)
