import asyncio
import logging
from src.event_broker import global_broker

logger = logging.getLogger("BaseConnector")

class BaseConnector:
    def __init__(self, name: str):
        self.name = name
        self.is_running = False
        self._task = None

    async def start(self):
        """Khởi động bộ kết nối."""
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Đã khởi động connector: {self.name}")

    async def stop(self):
        """Dừng bộ kết nối."""
        if not self.is_running:
            return
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info(f"Đã dừng connector: {self.name}")

    async def _run_loop(self):
        """Vòng lặp lắng nghe/giả lập của bộ kết nối (cần ghi đè ở lớp con)."""
        raise NotImplementedError

    async def emit_comment(self, username: str, comment: str):
        """Đẩy sự kiện comment_received vào Event Broker."""
        event_data = {
            "platform": self.name,
            "username": username,
            "comment": comment
        }
        await global_broker.publish("comment_received", event_data)
