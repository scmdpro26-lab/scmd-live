import os
import asyncio
import logging
from src.connectors.base import BaseConnector

logger = logging.getLogger("TikTokConnector")

try:
    from TikTokLive import TikTokLiveClient
    from TikTokLive.events import CommentEvent
    from TikTokLive.client.errors import UserOfflineError, UserNotFoundError, TikTokLiveError
    TIKTOK_LIVE_AVAILABLE = True
except ImportError:
    TIKTOK_LIVE_AVAILABLE = False
    logger.warning("Thư viện TikTokLive chưa được cài đặt hoặc import thất bại. TikTok Connector sẽ hoạt động ở chế độ offline fallback.")

class TikTokConnector(BaseConnector):
    def __init__(self):
        super().__init__("TikTok")
        # Đọc tên tài khoản streamer từ .env hoặc mặc định
        self.username = os.getenv("TIKTOK_USERNAME", "@live_username")
        self.client = None

    async def _run_loop(self):
        if not TIKTOK_LIVE_AVAILABLE:
            logger.error("Không thể khởi động TikTok Webcast Connector thực tế vì thiếu thư viện TikTokLive.")
            # Chờ vô hạn cho đến khi dừng để tương thích
            while self.is_running:
                await asyncio.sleep(3600)
            return

        logger.info(f"TikTok Webcast Connector khởi động cho tài khoản: {self.username}")
        
        retry_delay = 10.0  # Thời gian chờ mặc định khi retry
        max_retry_delay = 60.0
        
        while self.is_running:
            try:
                logger.info(f"Đang kết nối tới TikTok Live chat Webcast của: {self.username}...")
                self.client = TikTokLiveClient(unique_id=self.username)
                
                @self.client.on("comment")
                async def on_comment(event: CommentEvent):
                    if self.is_running:
                        logger.info(f"[TikTok Webcast] Comment từ {event.user.nickname}: {event.comment}")
                        await self.emit_comment(event.user.nickname, event.comment)
                        
                @self.client.on("like")
                async def on_like(event):
                    if self.is_running:
                        logger.info(f"[TikTok Webcast] Tim từ {event.user.nickname} (x{event.likeCount})")
                        event_data = {
                            "platform": "TikTok",
                            "username": event.user.nickname,
                            "like_count": event.likeCount
                        }
                        from src.event_broker import global_broker
                        await global_broker.publish("like_received", event_data)

                @self.client.on("follow")
                async def on_follow(event):
                    if self.is_running:
                        logger.info(f"[TikTok Webcast] Follow từ {event.user.nickname}")
                        event_data = {
                            "platform": "TikTok",
                            "username": event.user.nickname
                        }
                        from src.event_broker import global_broker
                        await global_broker.publish("follow_received", event_data)

                @self.client.on("share")
                async def on_share(event):
                    if self.is_running:
                        logger.info(f"[TikTok Webcast] Share từ {event.user.nickname}")
                        event_data = {
                            "platform": "TikTok",
                            "username": event.user.nickname
                        }
                        from src.event_broker import global_broker
                        await global_broker.publish("share_received", event_data)

                @self.client.on("gift")
                async def on_gift(event):
                    if self.is_running:
                        gift_name = "quà tặng"
                        if hasattr(event, "gift"):
                            gift_name = getattr(event.gift, "name", getattr(getattr(event.gift, "info", None), "name", "quà tặng"))
                        gift_count = getattr(event, "repeat_count", getattr(event, "count", 1))
                        logger.info(f"[TikTok Webcast] Quà tặng từ {event.user.nickname}: {gift_count}x {gift_name}")
                        event_data = {
                            "platform": "TikTok",
                            "username": event.user.nickname,
                            "gift_name": gift_name,
                            "gift_count": gift_count
                        }
                        from src.event_broker import global_broker
                        await global_broker.publish("gift_received", event_data)
                        
                @self.client.on("disconnect")
                async def on_disconnect(event):
                    logger.warning("Kết nối WebSocket của TikTok Webcast đã bị ngắt từ xa.")

                
                # Bắt đầu kết nối (start() block cho đến khi client dừng hoặc lỗi)
                await self.client.start()
                
                # Nếu kết nối thành công và ngắt bình thường (ví dụ do tắt connector), reset retry delay
                retry_delay = 10.0
                
            except (UserOfflineError, UserNotFoundError):
                logger.warning(f"Kênh TikTok {self.username} hiện đang offline hoặc không tìm thấy. Đang chờ livestream bắt đầu...")
                retry_delay = min(retry_delay * 1.5, max_retry_delay)
            except TikTokLiveError as e:
                logger.warning(f"Lỗi TikTokLive client (có thể do protocol thay đổi hoặc mất kết nối): {e}")
                retry_delay = min(retry_delay * 1.5, max_retry_delay)
            except Exception as e:
                logger.error(f"Lỗi không xác định trong TikTok Webcast loop: {e}")
                retry_delay = min(retry_delay * 1.5, max_retry_delay)
                
            if not self.is_running:
                break
                
            logger.info(f"Đang tiến hành kết nối lại sau {retry_delay:.1f} giây...")
            # Sử dụng vòng lặp sleep nhỏ để có thể ngắt ngay lập tức khi user bấm dừng
            for _ in range(int(retry_delay)):
                if not self.is_running:
                    break
                await asyncio.sleep(1.0)
                
        logger.info("TikTok Webcast Connector đã dừng hoàn toàn.")
