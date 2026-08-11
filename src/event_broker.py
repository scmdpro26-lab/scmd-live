import asyncio
import logging
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EventBroker")

class EventBroker:
    def __init__(self):
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, event_type: str) -> asyncio.Queue:
        """Đăng ký nhận sự kiện của một loại cụ thể. Trả về một Queue bất đồng bộ."""
        async with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            queue = asyncio.Queue()
            self._subscribers[event_type].append(queue)
            logger.info(f"Đã đăng ký nhận sự kiện '{event_type}' (Tổng số subscriber: {len(self._subscribers[event_type])})")
            return queue

    async def unsubscribe(self, event_type: str, queue: asyncio.Queue):
        """Hủy đăng ký nhận sự kiện."""
        async with self._lock:
            if event_type in self._subscribers and queue in self._subscribers[event_type]:
                self._subscribers[event_type].remove(queue)
                logger.info(f"Đã hủy đăng ký sự kiện '{event_type}'")

    async def publish(self, event_type: str, data: Any):
        """Gửi sự kiện tới tất cả các subscriber đã đăng ký loại sự kiện này."""
        async with self._lock:
            if event_type in self._subscribers:
                # Tạo bản sao danh sách để tránh thay đổi trong lúc lặp
                targets = list(self._subscribers[event_type])
                logger.info(f"DEBUG: publish {event_type} gửi tới {len(targets)} subscriber.")
                for queue in targets:
                    await queue.put(data)
            else:
                logger.info(f"DEBUG: publish {event_type} nhưng không có subscriber nào.")
            logger.debug(f"Đã gửi sự kiện '{event_type}' với dữ liệu: {data}")

# Tạo một thực thể toàn cục (Singleton Pattern)
global_broker = EventBroker()
