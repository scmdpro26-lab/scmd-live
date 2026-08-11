import os
import time
import asyncio
import logging
from typing import Any, Optional
from src.event_broker import global_broker
from src.obs_client import OBSClient

logger = logging.getLogger("HighlightDirector")

class HighlightDirector:
    _background_tasks = set()

    def __init__(self, obs_client: OBSClient, app_signals: Optional[Any] = None):
        self.obs = obs_client
        self.signals = app_signals
        self.is_running = False
        
        # Đọc cấu hình từ .env
        self.enabled = os.getenv("ENABLE_AUTO_CLIP", "True").lower() == "true"
        self.threshold = int(os.getenv("HIGHLIGHT_THRESHOLD", "5")) # Tương tác/10s để coi là highlight
        self.cooldown = int(os.getenv("HIGHLIGHT_COOLDOWN", "30")) # Cooldown giữa các lần cắt (giây)
        
        # State tracking
        self.interaction_timestamps = []
        self.last_clip_time = 0.0
        self._loop_task = None
        self._broker_queues = {}

    async def start(self):
        """Khởi động Highlight Director, lắng nghe các tương tác livestream."""
        if not self.enabled:
            logger.info("Highlight Director đã bị vô hiệu hóa trong cấu hình.")
            return
            
        if self.is_running:
            return
        self.is_running = True
        
        # Đăng ký nhận sự kiện từ EventBroker và lưu tham chiếu mạnh để tránh GC hủy
        task = asyncio.create_task(self._event_listener_loop())
        self._loop_task = task
        HighlightDirector._background_tasks.add(task)
        task.add_done_callback(HighlightDirector._background_tasks.discard)
        
        logger.info(f"Highlight Director đã khởi chạy (Threshold: {self.threshold} tương tác/10s, Cooldown: {self.cooldown}s).")

    async def stop(self):
        """Dừng Highlight Director."""
        if not self.is_running:
            return
        self.is_running = False
        
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None
            
        logger.info("Highlight Director đã dừng.")

    async def _event_listener_loop(self):
        """Vòng lặp lắng nghe comment_received và like_received song song."""
        try:
            # Subscribe các queue từ global_broker
            comment_queue = await global_broker.subscribe("comment_received")
            like_queue = await global_broker.subscribe("like_received")
            
            self._broker_queues["comment_received"] = comment_queue
            self._broker_queues["like_received"] = like_queue

            async def process_queue(queue, name):
                logger.info(f"DEBUG: process_queue {name} started. self.is_running={self.is_running}")
                try:
                    while self.is_running:
                        event_data = await queue.get()
                        await self.on_interaction(name, event_data)
                except asyncio.CancelledError:
                    logger.info(f"DEBUG: process_queue {name} cancelled.")
                except Exception as e:
                    logger.error(f"DEBUG: process_queue {name} error: {e}", exc_info=e)
                finally:
                    logger.info(f"DEBUG: process_queue {name} finally. self.is_running={self.is_running}")
                    await global_broker.unsubscribe(name, queue)

            # Chạy song song dọn dẹp tương tác cũ trượt trơn tru
            async def cleanup_loop():
                logger.info(f"DEBUG: cleanup_loop started. self.is_running={self.is_running}")
                try:
                    while self.is_running:
                        await asyncio.sleep(1.0)
                        await self._check_highlight()
                except asyncio.CancelledError:
                    logger.info("DEBUG: cleanup_loop cancelled.")
                except Exception as e:
                    logger.error(f"DEBUG: cleanup_loop error: {e}", exc_info=e)
                finally:
                    logger.info(f"DEBUG: cleanup_loop finally. self.is_running={self.is_running}")

            results = await asyncio.gather(
                process_queue(comment_queue, "comment_received"),
                process_queue(like_queue, "like_received"),
                cleanup_loop(),
                return_exceptions=True
            )
            for r in results:
                if isinstance(r, Exception):
                    logger.error(f"❌ Exception in HighlightDirector loop: {r}", exc_info=r)
        except asyncio.CancelledError:
            import traceback
            logger.warning("⚠️ HighlightDirector _event_listener_loop received CancelledError!")
            logger.warning(traceback.format_exc())
            raise

    async def on_interaction(self, event_name: str, data: dict):
        """Xử lý khi có tương tác (bình luận hoặc like) gửi tới Event Broker."""
        if not self.is_running:
            return
            
        now = time.time()
        # Đếm tim/like thực tế
        count = 1
        if event_name == "like_received":
            count = data.get("like_count", 1)
            
        for _ in range(count):
            self.interaction_timestamps.append(now)
            
        await self._check_highlight()

    async def _check_highlight(self):
        """Kiểm tra xem mật độ tương tác có vượt ngưỡng để cắt highlight hay không."""
        now = time.time()
        # Lọc giữ lại tương tác trong 10 giây gần nhất
        self.interaction_timestamps = [t for t in self.interaction_timestamps if now - t <= 10.0]
        
        current_rate = len(self.interaction_timestamps)
        
        # Nếu vượt ngưỡng tương tác và ngoài thời gian cooldown
        if current_rate >= self.threshold and (now - self.last_clip_time) >= self.cooldown:
            self.last_clip_time = now
            logger.warning(f"🔥 [Highlight Detected] Đột biến tương tác đạt: {current_rate} tương tác/10s (Ngưỡng: {self.threshold})!")
            
            # Gửi tín hiệu log lên GUI
            if self.signals:
                self.signals.log_event.emit(f"🔥 [Auto-clip] Phát hiện Highlight tương tác đạt {current_rate} tương tác/10s!")
                
            if self.obs.is_connected:
                if self.signals:
                    self.signals.log_event.emit("📸 [Auto-clip] Gửi lệnh lưu OBS Replay Buffer (Highlight clip) thành công.")
                
                # Gọi OBS save replay buffer
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self.obs.save_replay_buffer)
            else:
                if self.signals:
                    self.signals.log_event.emit("⚠️ [Auto-clip] OBS chưa kết nối, không thể lưu Highlight clip.")
