import os
import json
import time
import asyncio
import logging
import random
from typing import List, Dict, Any, Optional
from src.event_broker import global_broker
from ai_live.integrations.vnyan.exceptions import CapabilityUnavailable

logger = logging.getLogger("AIDirector")

class AIDirector:
    def __init__(self, obs_client, ai_brain, tts_engine, timeline_path="timeline.json"):
        self.obs = obs_client
        self.ai = ai_brain
        self.tts = tts_engine
        self.timeline_path = timeline_path
        
        from src.vmc_service import get_vmc_client
        self.vmc_client = get_vmc_client()
        
        self.timeline_events: List[Dict[str, Any]] = []
        self.is_running = False
        self._timeline_task = None
        self._silence_task = None
        
        self.last_comment_time = time.time()
        self.silence_threshold = 30.0  # Số giây im lặng để kích hoạt tự động
        self.elapsed_time = 0
        
        # Thống kê tim và mốc tim (Likes Milestones)
        self.like_count = 0
        self.like_milestone = 100  # Cứ sau 100 tim tự động tung voucher
        self.last_triggered_milestone = 0
        
        # Cấu hình Scene/Source OBS cho Minigame và Voucher
        self.minigame_scene = "Live_Scene"
        self.minigame_source = "Minigame_Source"
        self.voucher_scene = "Live_Scene"
        self.voucher_source = "Voucher_Source"
        
        self.load_timeline()

    def load_timeline(self):
        """Đọc kịch bản timeline từ file JSON."""
        if os.path.exists(self.timeline_path):
            try:
                with open(self.timeline_path, "r", encoding="utf-8") as f:
                    self.timeline_events = json.load(f)
                # Sắp xếp các sự kiện theo thời gian tăng dần
                self.timeline_events.sort(key=lambda x: x.get("time_seconds", 0))
                logger.info(f"Đã nạp {len(self.timeline_events)} sự kiện kịch bản từ {self.timeline_path}")
            except Exception as e:
                logger.error(f"Lỗi đọc kịch bản timeline: {e}")
        else:
            logger.warning(f"Không tìm thấy file kịch bản {self.timeline_path}. Sử dụng kịch bản rỗng.")
            self.timeline_events = []

    async def start(self):
        """Khởi động bộ Đạo diễn AI."""
        if self.is_running:
            return
        self.is_running = True
        self.elapsed_time = 0
        self.last_comment_time = time.time()
        self.like_count = 0
        self.last_triggered_milestone = 0
        
        # Chạy song song vòng lặp kịch bản và vòng lặp giám sát tương tác
        self._timeline_task = asyncio.create_task(self._timeline_loop())
        self._silence_task = asyncio.create_task(self._silence_monitor_loop())
        
        # Đăng ký nhận sự kiện comment và like
        asyncio.create_task(self._subscribe_comments())
        asyncio.create_task(self._subscribe_likes())
        
        logger.info("Đạo diễn AI đã được kích hoạt!")

    async def stop(self):
        """Dừng bộ Đạo diễn AI."""
        if not self.is_running:
            return
        self.is_running = False
        
        if self._timeline_task:
            self._timeline_task.cancel()
            try:
                await self._timeline_task
            except asyncio.CancelledError:
                pass
            self._timeline_task = None
            
        if self._silence_task:
            self._silence_task.cancel()
            try:
                await self._silence_task
            except asyncio.CancelledError:
                pass
            self._silence_task = None
            
        logger.info("Đạo diễn AI đã dừng.")

    async def _subscribe_comments(self):
        """Đăng ký sự kiện comment để reset bộ đếm thời gian im lặng."""
        queue = await global_broker.subscribe("comment_received")
        try:
            while self.is_running:
                await queue.get()
                self.last_comment_time = time.time()
        except asyncio.CancelledError:
            pass
        finally:
            await global_broker.unsubscribe("comment_received", queue)

    async def _subscribe_likes(self):
        """Đăng ký nhận sự kiện thả tim để tích lũy và tự động tung voucher theo mốc tim."""
        queue = await global_broker.subscribe("like_received")
        try:
            while self.is_running:
                event_data = await queue.get()
                count = 1
                if isinstance(event_data, dict):
                    count = event_data.get("like_count", event_data.get("count", 1))
                
                self.like_count += count
                
                # Tính toán và kiểm tra mốc tim
                current_milestone = (self.like_count // self.like_milestone) * self.like_milestone
                if current_milestone > self.last_triggered_milestone:
                    self.last_triggered_milestone = current_milestone
                    logger.info(f"🎉 Mốc tim đạt {current_milestone}! Tự động kích hoạt Voucher khuyến mãi.")
                    
                    # Gọi giới thiệu voucher
                    msg = f"Cảm ơn cả nhà đã thả tim rất nhiệt tình! Đạt mốc {current_milestone} tim rồi, shop xin gửi tặng cả nhà voucher giảm giá cực kỳ hấp dẫn ngay trên màn hình nhé!"
                    await self.trigger_voucher(msg)
        except asyncio.CancelledError:
            pass
        finally:
            await global_broker.unsubscribe("like_received", queue)

    async def _timeline_loop(self):
        """Vòng lặp chạy kịch bản tự động theo thời gian (Timeline)."""
        try:
            event_idx = 0
            while self.is_running:
                await asyncio.sleep(1.0)
                self.elapsed_time += 1
                
                # Kiểm tra nếu có sự kiện khớp với thời gian trôi qua
                while event_idx < len(self.timeline_events) and self.timeline_events[event_idx].get("time_seconds", 0) <= self.elapsed_time:
                    event = self.timeline_events[event_idx]
                    await self._execute_timeline_event(event)
                    event_idx += 1
                    
                # Nếu đã hết sự kiện kịch bản, lặp lại từ đầu
                if event_idx >= len(self.timeline_events):
                    logger.info("Kịch bản kết thúc. Reset timeline quay lại từ đầu.")
                    self.elapsed_time = 0
                    event_idx = 0
        except asyncio.CancelledError:
            pass

    async def _execute_timeline_event(self, event: Dict[str, Any]):
        action = event.get("action")
        params = event.get("params", {})
        desc = event.get("description", "")
        
        logger.info(f"[Đạo Diễn AI] Thực thi kịch bản (Thời điểm {event.get('time_seconds')}s): {desc}")
        
        if action == "change_scene" and self.obs.is_connected:
            scene = params.get("scene_name")
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.obs.change_scene, scene)
            
        elif action == "show_source" and self.obs.is_connected:
            scene = params.get("scene_name")
            source = params.get("source_name")
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.obs.set_source_visibility, scene, source, True)
            
        elif action == "trigger_interact":
            # Kêu gọi tương tác qua giọng đọc (Chỉ phát khi TTS rảnh để tránh ngắt ngang - Guardrail #2)
            text = params.get("text", "")
            if text and not self.tts.is_playing:
                # Kích hoạt cử chỉ nói VMC
                try:
                    self.vmc_client.trigger_expression("happy", 1.5)
                except CapabilityUnavailable as e:
                    logger.warning(f"Không thể kích hoạt biểu cảm: {e}")
                
                def tts_start():
                    try:
                        self.vmc_client.start_talking()
                    except CapabilityUnavailable as e:
                        logger.warning(f"Không thể bắt đầu nói: {e}")
                def tts_stop():
                    try:
                        self.vmc_client.stop_talking()
                    except CapabilityUnavailable as e:
                        logger.warning(f"Không thể dừng nói: {e}")
                self.tts.speak(text, on_start=tts_start, on_finished=tts_stop)

        elif action == "trigger_minigame":
            text = params.get("text")
            await self.trigger_minigame(text)

        elif action == "trigger_voucher":
            text = params.get("text")
            await self.trigger_voucher(text)

    async def trigger_minigame(self, custom_text: Optional[str] = None):
        """Kích hoạt vòng quay may mắn."""
        logger.info("🎮 Kích hoạt minigame Vòng quay may mắn!")
        
        # Gửi lệnh OSC tới VMC
        try:
            self.vmc_client.trigger_minigame_start()
        except CapabilityUnavailable as e:
            logger.warning(f"Không thể kích hoạt minigame: {e}")
        
        # 1. Bật hiển thị source trên OBS
        if self.obs.is_connected:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, 
                self.obs.set_source_visibility, 
                self.minigame_scene, 
                self.minigame_source, 
                True
            )
            
        # 2. Phát ngôn của MC kêu gọi tương tác
        text = custom_text or "Cả nhà ơi! Vòng quay may mắn đã chính thức bắt đầu rồi nhé! Hãy comment nhiệt tình để nhận quà tặng cực khủng từ shop nào!"
        if not self.tts.is_playing:
            try:
                self.vmc_client.trigger_expression("happy", 3.0)
            except CapabilityUnavailable as e:
                logger.warning(f"Không thể kích hoạt biểu cảm: {e}")
            def tts_start():
                try:
                    self.vmc_client.start_talking()
                except CapabilityUnavailable as e:
                    logger.warning(f"Không thể bắt đầu nói: {e}")
            def tts_stop():
                try:
                    self.vmc_client.stop_talking()
                except CapabilityUnavailable as e:
                    logger.warning(f"Không thể dừng nói: {e}")
            self.tts.speak(text, on_start=tts_start, on_finished=tts_stop)
            
        # 3. Hẹn giờ tự động ẩn minigame sau 15 giây
        async def auto_hide():
            await asyncio.sleep(15.0)
            if self.obs.is_connected:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None, 
                    self.obs.set_source_visibility, 
                    self.minigame_scene, 
                    self.minigame_source, 
                    False
                )
                logger.info("🎮 Đã tự động ẩn minigame.")
                
        asyncio.create_task(auto_hide())

    async def trigger_voucher(self, custom_text: Optional[str] = None):
        """Tung voucher giảm giá."""
        logger.info("🎫 Kích hoạt tung voucher giảm giá!")
        
        # Gửi lệnh OSC tới VMC
        try:
            self.vmc_client.trigger_voucher_drop()
        except CapabilityUnavailable as e:
            logger.warning(f"Không thể kích hoạt voucher drop: {e}")
        
        # 1. Bật hiển thị source trên OBS
        if self.obs.is_connected:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, 
                self.obs.set_source_visibility, 
                self.voucher_scene, 
                self.voucher_source, 
                True
            )
            
        # 2. Phát ngôn giới thiệu voucher
        text = custom_text or "Nhanh tay săn ngay voucher giảm giá cực hot vừa được tung ra ở góc màn hình cả nhà ơi! Số lượng vô cùng giới hạn, chậm tay là hết đó nha!"
        if not self.tts.is_playing:
            try:
                self.vmc_client.trigger_expression("happy", 3.0)
            except CapabilityUnavailable as e:
                logger.warning(f"Không thể kích hoạt biểu cảm: {e}")
            def tts_start():
                try:
                    self.vmc_client.start_talking()
                except CapabilityUnavailable as e:
                    logger.warning(f"Không thể bắt đầu nói: {e}")
            def tts_stop():
                try:
                    self.vmc_client.stop_talking()
                except CapabilityUnavailable as e:
                    logger.warning(f"Không thể dừng nói: {e}")
            self.tts.speak(text, on_start=tts_start, on_finished=tts_stop)
            
        # 3. Hẹn giờ tự động ẩn voucher banner sau 15 giây
        async def auto_hide():
            await asyncio.sleep(15.0)
            if self.obs.is_connected:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None, 
                    self.obs.set_source_visibility, 
                    self.voucher_scene, 
                    self.voucher_source, 
                    False
                )
                logger.info("🎫 Đã tự động ẩn voucher banner.")
                
        asyncio.create_task(auto_hide())

    async def _silence_monitor_loop(self):
        """Vòng lặp phát hiện phòng live bị 'nguội' và tự động hâm nóng."""
        try:
            while self.is_running:
                await asyncio.sleep(2.0)
                current_time = time.time()
                
                # Nếu phòng live bị im lặng quá lâu
                if current_time - self.last_comment_time > self.silence_threshold:
                    logger.warning(f"[Hâm nóng Live] Phát hiện phòng live im lặng quá {self.silence_threshold}s!")
                    
                    # Reset bộ đếm để không lặp lại liên tục
                    self.last_comment_time = current_time
                    
                    # Chọn ngẫu nhiên một hình thức khuấy động
                    mode = random.choice([0, 1, 2])
                    
                    if mode == 0:
                        # Đặt câu hỏi hâm nóng phòng livestream
                        system_prompt_comment = {
                            "platform": "System",
                            "username": "Đạo Diễn AI",
                            "comment": "Hãy đặt một câu hỏi giao lưu ngắn hâm nóng phòng livestream bán hàng."
                        }
                        await global_broker.publish("comment_received", system_prompt_comment)
                    elif mode == 1:
                        # Kích hoạt minigame
                        msg = "Phòng live hôm nay trầm quá cả nhà ơi! Shop xin kích hoạt minigame Vòng quay may mắn để khuấy động không khí nhé! Tham gia ngay nào mọi người ơi!"
                        await self.trigger_minigame(msg)
                    elif mode == 2:
                        # Tung voucher
                        msg = "Mọi người đi đâu hết rồi ta? Để hâm nóng không khí, shop xin tặng nóng voucher giảm giá đặc biệt ngay trên màn hình. Nhanh tay săn nhé cả nhà!"
                        await self.trigger_voucher(msg)
        except asyncio.CancelledError:
            pass
