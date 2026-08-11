import os
import asyncio
import logging
import random
from src.connectors.base import BaseConnector

logger = logging.getLogger("YoutubeConnector")

try:
    import pytchat
    PYTCHAT_AVAILABLE = True
except ImportError:
    PYTCHAT_AVAILABLE = False
    logger.warning("Thư viện pytchat chưa được cài đặt. YouTube Connector sẽ hoạt động ở chế độ giả lập offline.")

class YoutubeConnector(BaseConnector):
    def __init__(self):
        super().__init__("YouTube")
        # Đọc ID của video live YouTube từ .env hoặc mặc định
        self.video_id = os.getenv("YOUTUBE_VIDEO_ID", "live_video_id")
        self.chat_client = None

    async def _run_loop(self):
        # Trình cào chat YouTube thực tế sử dụng pytchat
        if PYTCHAT_AVAILABLE and self.video_id != "live_video_id" and self.video_id:
            logger.info(f"YouTube Connector khởi động cào chat cho Live Video ID: {self.video_id}")
            while self.is_running:
                try:
                    self.chat_client = pytchat.create(video_id=self.video_id)
                    while self.chat_client.is_alive() and self.is_running:
                        for c in self.chat_client.get().sync_items():
                            if not self.is_running:
                                break
                            logger.info(f"[YouTube Chat] Comment từ {c.author.name}: {c.message}")
                            await self.emit_comment(c.author.name, c.message)
                        await asyncio.sleep(1.0)
                except Exception as e:
                    logger.error(f"Lỗi khi cào chat YouTube: {e}")
                    await asyncio.sleep(5.0)
                if not self.is_running:
                    break
        else:
            # Fallback chế độ giả lập cào comment YouTube
            logger.info("YouTube Connector chạy ở chế độ giả lập cào comment ngẫu nhiên.")
            mock_names = ["Thanh Tùng", "Vy Nguyễn", "Hoàng Nam", "Bảo Trâm", "Quốc Bảo", "Thuỳ Chi"]
            mock_comments = [
                "sản phẩm SP001 còn hàng không em ơi?",
                "Áo thun SP001 có những màu nào thế shop?",
                "chào MC xinh đẹp nha, chúc shop bão đơn",
                "quần SP002 chất vải co giãn tốt không?",
                "chốt SP001 size L màu đen nhé shop",
                "shop uy tín quá, giao nhanh chất vải đẹp cực kỳ luôn",
                "hàng giao lâu thế shop chán thật sự",
                "Không biết vải SP001 có đúng là cotton xịn thật không?"
            ]

            while self.is_running:
                # Đợi ngẫu nhiên 8 đến 12 giây sinh 1 comment YouTube
                wait_time = random.uniform(8.0, 12.0)
                for _ in range(int(wait_time)):
                    if not self.is_running:
                        break
                    await asyncio.sleep(1.0)
                
                if not self.is_running:
                    break
                    
                username = random.choice(mock_names)
                comment = random.choice(mock_comments)
                
                logger.info(f"[YouTube Mock Chat] Comment từ {username}: {comment}")
                await self.emit_comment(username, comment)
                
        logger.info("YouTube Connector đã dừng hoàn toàn.")
