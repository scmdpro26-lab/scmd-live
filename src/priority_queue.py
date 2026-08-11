import re
import json
import time
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Callable, Optional
import src.database as db
from ai_live.integrations.vnyan.exceptions import CapabilityUnavailable
from src.action_engine import ActionSource

logger = logging.getLogger("PriorityQueueProcessor")



class LiveEventActionMapper:
    """Nạp và áp dụng cấu hình ánh xạ sự kiện phòng livestream sang hành động MC ảo.

    Cấu hình được đọc từ ``profiles/live_event_actions.json``.
    Nếu file không tồn tại, tự động dùng defaults giống hành vi hiện tại — không crash.
    """

    _DEFAULT_CONFIG = {
        "event_actions": {
            "follow":     {"action": "greeting", "expression": "happy"},
            "share":      {"action": "heart",    "expression": "happy"},
            "gift": {
                "high_value": {"action": "dance", "expression": "happy", "threshold": 5},
                "normal":     {"action": "clap",  "expression": "happy"},
            },
            "cart_click": {"action": "point_up", "expression": "surprised"},
        },
        "sentiment_actions": {
            "khó chịu": {"action": "apology", "duration": 3.0},
        },
    }

    def __init__(self, config_path: Path = Path("profiles/live_event_actions.json")):
        self.config_path = config_path
        self._config: dict = {}
        self._load()

    def _load(self) -> None:
        """Nạp file cấu hình JSON. Dùng defaults nếu file thiếu hoặc lỗi."""
        if not self.config_path.exists():
            logger.info(
                f"LiveEventActionMapper: Không tìm thấy '{self.config_path}', sử dụng cấu hình mặc định."
            )
            self._config = self._DEFAULT_CONFIG
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
            logger.info(f"LiveEventActionMapper: Đã nạp cấu hình từ '{self.config_path}'.")
        except Exception as e:
            logger.warning(f"LiveEventActionMapper: Lỗi đọc file cấu hình: {e}. Dùng defaults.")
            self._config = self._DEFAULT_CONFIG

    def reload(self) -> None:
        """Tải lại cấu hình từ disk (hot-reload không cần restart)."""
        self._load()

    def get_event_action(self, event_type: str, comment: str = "") -> str | None:
        """Trả về tên action cho sự kiện và nội dung bình luận tương ứng.

        Hỗ trợ phân loại gift theo giá trị (high_value vs normal).
        Trả về None nếu event_type không có trong cấu hình.
        """
        event_cfg = self._config.get("event_actions", {}).get(event_type)
        if not event_cfg:
            return None

        # Gift có cấu hình phân tầng (high_value / normal)
        if event_type == "gift" and isinstance(event_cfg, dict) and "high_value" in event_cfg:
            high_val_cfg = event_cfg["high_value"]
            threshold = high_val_cfg.get("threshold", 5)
            # Kiểm tra số lượng quà trong comment
            words = comment.split()
            is_high_value = any(
                w.isdigit() and int(w) >= threshold for w in words
            )
            cfg = high_val_cfg if is_high_value else event_cfg.get("normal", {})
        elif isinstance(event_cfg, dict) and "action" in event_cfg:
            cfg = event_cfg
        else:
            return None

        return cfg.get("action")

    def get_sentiment_action(self, sentiment: str) -> tuple[str | None, float]:
        """Trả về (action, duration) cho sentiment tương ứng, hoặc (None, 0) nếu không có."""
        sentiment_cfg = self._config.get("sentiment_actions", {}).get(sentiment)
        if not sentiment_cfg:
            return None, 0.0
        return sentiment_cfg.get("action"), float(sentiment_cfg.get("duration", 3.0))


class PriorityQueueProcessor:
    def __init__(self, ai_brain, tts_engine, obs_client, on_queue_change_callback: Optional[Callable] = None, app_signals: Optional[Any] = None):
        self.ai = ai_brain
        self.tts = tts_engine
        self.obs = obs_client
        self.on_queue_change = on_queue_change_callback
        self.signals = app_signals
        
        # 3 levels of priority queues (bounded to 100 elements to prevent OOM)
        self.high_queue = asyncio.Queue(maxsize=100)     # Priority 1: Mua hàng / Hỏi giá
        self.medium_queue = asyncio.Queue(maxsize=100)   # Priority 2: Ship / Chất liệu / Hỏi han chi tiết
        self.low_queue = asyncio.Queue(maxsize=100)      # Priority 3: Chào hỏi xã giao / Nhận xét chung
        
        self.is_running = False
        self._loop_task = None
        self._live_events_task = None

        
        # Cấu hình text source mặc định để cập nhật OBS
        self.subtitle_source = "Subtitle_Source"
        self.comment_source = "Comment_Source"
        self.auto_scene = True
        self.auto_show_source = True

        # Callback thông báo kết quả trả lời AI về GUI
        self.on_ai_response_callback: Optional[Callable[[str, str, str], None]] = None

        # Tích hợp MC ảo VMC và Bộ nhớ MemoryStore
        from src.memory_store import MemoryStore
        from src.vmc_service import get_vmc_client
        from src.teleprompter import TeleprompterService
        self.memory_store = MemoryStore()
        self.vmc_client = get_vmc_client()
        self.teleprompter = TeleprompterService()

        # Bộ ánh xạ sự kiện -> hành động (cấu hình từ JSON)
        self.event_action_mapper = LiveEventActionMapper()

        # Bộ phân tích Speech-to-Gesture
        from src.speech_gesture import SpeechGestureParser
        self.speech_gesture_parser = SpeechGestureParser()

        # Autopilot Mode Configuration
        self.autopilot_level = 3
        self.last_sensitive_action_time = 0.0
        self.on_pending_approval_callback: Optional[Callable[[Dict[str, Any]], None]] = None

        # Spam checkout block configuration & state
        self.last_checkout_by_user: Dict[str, float] = {}
        self.last_checkout_product_by_user: Dict[tuple, float] = {}


    def get_loop(self):
        """Lấy asyncio event loop đang chạy của processor."""
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.get_event_loop()

    def moderate_ai_output(self, text: str) -> str:
        """Kiểm duyệt đầu ra của AI trước khi phát qua TTS.
        Nếu phát hiện từ ngữ thô tục/nhạy cảm, lọc bỏ (hoặc thay thế) để đảm bảo MC không nói bậy.
        """
        if not text:
            return ""
            
        # Danh sách từ tục tĩu/nhạy cảm cần lọc
        bad_words = [
            "địt", "đéo", "lồn", "cặc", "chửi", "ngu", "khốn nạn", "đĩ", "điếm",
            "đ.é.o", "d e o", "đjt", "l0n", "c*c"
        ]
        
        moderated_text = text
        
        # Quét tìm và thay thế các từ tục tĩu bằng ***
        for word in bad_words:
            # Nếu từ chỉ chứa chữ cái/số, dùng word boundaries \b để tránh thay thế nhầm substring (ví dụ Nguyễn chứa ngu)
            if word.isalnum():
                pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
            else:
                pattern = re.compile(re.escape(word), re.IGNORECASE)
            moderated_text = pattern.sub("***", moderated_text)
            
        # Nếu có sự thay đổi (chứa ***), log cảnh báo
        if moderated_text != text:
            logger.warning(f"⚠️ [Output Moderation] Đã lọc từ ngữ nhạy cảm trong câu trả lời AI: '{text}' -> '{moderated_text}'")
            
        return moderated_text

    def _dispatch_speech(self, platform: str, clean_answer: str, tts_rate: str, tts_pitch: str, vmc_expression: str):
        """Điều phối câu thoại theo ma trận tuân thủ của nền tảng."""
        from src.compliance_engine import get_policy, VoiceMode, apply_disclosure_overlay
        policy = get_policy(platform)
        
        # 1. Tự động áp dụng nhãn minh bạch AI trên OBS
        if self.obs and self.obs.is_connected:
            apply_disclosure_overlay(self.obs, platform)
            
        # 2. Xử lý giọng nói / avatar dựa trên chế độ tuân thủ
        if policy.voice_mode == VoiceMode.AI_TTS_AVATAR:
            try:
                self.vmc_client.trigger_expression(vmc_expression, 3.0)
            except CapabilityUnavailable as e:
                logger.warning(f"Không thể kích hoạt biểu cảm: {e}")

            # Speech-to-Gesture: phân tích câu nói để kích hoạt cử chỉ phù hợp
            self.speech_gesture_parser.parse_and_trigger(clean_answer, self.vmc_client)


            def tts_start(audio_path=None):
                try:
                    self.vmc_client.start_talking(audio_path)
                except CapabilityUnavailable as e:
                    logger.warning(f"Không thể bắt đầu lipsync: {e}")
                
            def tts_stop():
                try:
                    self.vmc_client.stop_talking()
                except CapabilityUnavailable as e:
                    logger.warning(f"Không thể dừng lipsync: {e}")
                
            self.tts.speak(clean_answer, on_start=tts_start, on_finished=tts_stop, rate=tts_rate, pitch=tts_pitch)
            
        elif policy.voice_mode == VoiceMode.AI_COPILOT_HUMAN:
            # TikTok Live / Shop: Chỉ hiển thị lời thoại lên màn hình gợi ý nhắc chữ cho người thật đọc
            logger.info(f"Compliance: Đẩy kịch bản vào Teleprompter cho người thật đọc trên {platform}")
            self.teleprompter.push_line(clean_answer)
            
        elif policy.voice_mode == VoiceMode.AI_SUBTITLE_ONLY:
            # Không phát âm thanh, không chuyển cử chỉ avatar
            logger.info(f"Compliance: Chỉ hiển thị phụ đề cho {platform}")

    def classify_comment(self, comment: str) -> int:
        """Phân loại bình luận dựa trên từ khóa. Trả về mức độ ưu tiên từ 1 (Cao) đến 3 (Thấp)."""
        comment_lower = comment.lower()
        
        # Thay thế ký tự đặc biệt bằng khoảng trắng và đệm khoảng trắng ở hai đầu
        clean_comment = re.sub(r'[^\w\s]', ' ', comment_lower)
        comment_spaced = f" {clean_comment} "
        
        # 1. Từ khóa ƯU TIÊN CAO: Mua bán, chốt đơn, giá cả, mã sản phẩm
        has_product_code = bool(re.search(r"sp\d+", comment_lower))
        high_keywords = ["giá", "bao nhiêu", "nhiêu", "chốt", "mua", "bao nhieu", "đơn", "don", "nhieu", "gia"]
        
        if has_product_code or any(f" {kw} " in comment_spaced for kw in high_keywords):
            return 1
            
        # 2. Từ khóa ƯU TIÊN TRUNG BÌNH: Vận chuyển, chất liệu, size
        med_keywords = ["ship", "giao", "gửi", "gui", "chất", "chat", "vải", "vai", "size", "kích", "kich", "màu", "mau"]
        if any(f" {kw} " in comment_spaced for kw in med_keywords):
            return 2
            
        # 3. Mặc định là ƯU TIÊN THẤP: Chào hỏi, khen ngợi xã giao
        return 3

    def _is_moderated_regex_basic(self, comment: str) -> bool:
        """Kiểm tra nhanh bằng regex cơ bản để tăng hiệu năng."""
        comment_lower = comment.lower()
        bad_words = [
            "địt", "đéo", "lồn", "cặc", "chửi", "ngu", "khốn nạn", "đĩ", "điếm",
            "http://", "https://", "www.", ".com", ".vn", ".net", "zalo.me"
        ]
        
        clean_comment = re.sub(r'[^\w\s]', ' ', comment_lower)
        comment_spaced = f" {clean_comment} "
        
        for word in bad_words:
            # Kiểm tra url/link trực tiếp
            if word in ["http://", "https://", "www.", "zalo.me", ".com", ".vn", ".net"]:
                if word in comment_lower:
                    return True
            # Kiểm tra từ ngữ thô tục độc lập
            elif f" {word} " in comment_spaced:
                return True
        return False

    async def is_moderated(self, comment: str) -> bool:
        """Kiểm tra xem bình luận có chứa từ ngữ thô tục hoặc spam link/quảng cáo hay không (Guardrail #1).
        
        Sử dụng kết hợp regex cơ bản và bộ phân loại AI (Gemini) để bắt biến thể tinh vi.
        """
        # 1. Fast path: regex cơ bản
        if self._is_moderated_regex_basic(comment):
            return True
            
        # 2. Slow path: Phân loại bằng AI (hoặc offline rule-based nâng cấp)
        loop = asyncio.get_running_loop()
        label = await loop.run_in_executor(None, self.ai.classify_moderation, comment)
        return label == "SPAM"

    async def enqueue(self, comment_data: Dict[str, Any]):
        """Thêm bình luận vào hàng đợi phù hợp sau khi lọc kiểm duyệt."""
        comment = comment_data.get("comment", "")
        
        # Kiểm duyệt bình luận trước khi đưa vào hệ thống xử lý (Guardrail #1)
        if await self.is_moderated(comment):
            logger.warning(f"🚫 [Moderation] Chặn bình luận nhạy cảm/spam: {comment_data['username']}: '{comment}'")
            return
            
        priority = self.classify_comment(comment)
        comment_data["priority"] = priority
        
        target_queue = self.low_queue
        if priority == 1:
            target_queue = self.high_queue
        elif priority == 2:
            target_queue = self.medium_queue
            
        # Nếu hàng đợi đầy, giải phóng phần tử cũ nhất để tránh OOM (Risk-MEM-01)
        if target_queue.full():
            try:
                dropped = target_queue.get_nowait()
                logger.warning(f"⚠️ [Queue Full] Hàng đợi {priority} đầy! Đã bỏ bình luận cũ nhất của {dropped.get('username')}.")
            except asyncio.QueueEmpty:
                pass
                
        target_queue.put_nowait(comment_data)
            
        logger.info(f"Đã thêm vào Hàng đợi {priority}: {comment_data['username']} - '{comment}'")
        
        if self.on_queue_change:
            self.on_queue_change(self.get_queue_sizes())

    def get_queue_sizes(self) -> Dict[str, int]:
        """Lấy kích thước hiện tại của các hàng đợi."""
        return {
            "high": self.high_queue.qsize(),
            "medium": self.medium_queue.qsize(),
            "low": self.low_queue.qsize()
        }

    async def start(self):
        """Khởi động bộ xử lý hàng đợi chạy nền."""
        if self.is_running:
            return
        self.is_running = True
        self._loop_task = asyncio.create_task(self._process_loop())
        self._live_events_task = asyncio.create_task(self._subscribe_live_events_loop())
        logger.info("Bộ xử lý Hàng đợi ưu tiên bắt đầu chạy...")

    async def stop(self):
        """Dừng bộ xử lý hàng đợi."""
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
            
        if self._live_events_task:
            self._live_events_task.cancel()
            try:
                await self._live_events_task
            except asyncio.CancelledError:
                pass
            self._live_events_task = None
            
        logger.info("Bộ xử lý Hàng đợi ưu tiên đã dừng.")

    async def _subscribe_live_events_loop(self):
        """Đăng ký nhận và xử lý các sự kiện livestream (Gift, Follow, Share, Click Cart)."""
        from src.event_broker import global_broker
        gift_queue = await global_broker.subscribe("gift_received")
        follow_queue = await global_broker.subscribe("follow_received")
        share_queue = await global_broker.subscribe("share_received")
        cart_click_queue = await global_broker.subscribe("cart_click_received")
        
        try:
            while self.is_running:
                await asyncio.sleep(0.1)
                
                # Check gift
                while not gift_queue.empty():
                    event_data = gift_queue.get_nowait()
                    username = event_data["username"]
                    gift_name = event_data["gift_name"]
                    gift_count = event_data["gift_count"]
                    comment_data = {
                        "platform": event_data.get("platform", "TikTok"),
                        "username": username,
                        "comment": f"đã tặng {gift_count} {gift_name}",
                        "event_type": "gift"
                    }
                    await self.enqueue(comment_data)
                    
                # Check follow
                while not follow_queue.empty():
                    event_data = follow_queue.get_nowait()
                    username = event_data["username"]
                    comment_data = {
                        "platform": event_data.get("platform", "TikTok"),
                        "username": username,
                        "comment": "đã follow shop",
                        "event_type": "follow"
                    }
                    await self.enqueue(comment_data)
                    
                # Check share
                while not share_queue.empty():
                    event_data = share_queue.get_nowait()
                    username = event_data["username"]
                    comment_data = {
                        "platform": event_data.get("platform", "TikTok"),
                        "username": username,
                        "comment": "đã chia sẻ livestream",
                        "event_type": "share"
                    }
                    await self.enqueue(comment_data)
                    
                # Check cart click
                while not cart_click_queue.empty():
                    event_data = cart_click_queue.get_nowait()
                    username = event_data["username"]
                    product_code = event_data["product_code"]
                    comment_data = {
                        "platform": event_data.get("platform", "TikTok"),
                        "username": username,
                        "comment": f"đã click xem sản phẩm {product_code}",
                        "event_type": "cart_click"
                    }
                    await self.enqueue(comment_data)
                    
                    # Tự động ghim sản phẩm đó vào giỏ hàng
                    from src.tiktok_shop import global_tiktok_shop
                    await global_tiktok_shop.pin_product(product_code)
                    
        except asyncio.CancelledError:
            pass
        finally:
            await global_broker.unsubscribe("gift_received", gift_queue)
            await global_broker.unsubscribe("follow_received", follow_queue)
            await global_broker.unsubscribe("share_received", share_queue)
            await global_broker.unsubscribe("cart_click_received", cart_click_queue)


    async def _process_loop(self):
        try:
            while self.is_running:
                # 1. Kiểm tra hàng đợi theo thứ tự ưu tiên
                comment_data = None
                
                if not self.high_queue.empty():
                    comment_data = await self.high_queue.get()
                elif not self.medium_queue.empty():
                    comment_data = await self.medium_queue.get()
                elif not self.low_queue.empty():
                    comment_data = await self.low_queue.get()
                
                # 2. Nếu có comment, xử lý nó (hỗ trợ gom batch ở Level 2, 3)
                if comment_data:
                    batch_comments = [comment_data]
                    
                    if self.autopilot_level in [2, 3]:
                        # Chờ thêm 1.0 giây để gom các comment khác trong hàng đợi
                        await asyncio.sleep(1.0)
                        
                        while len(batch_comments) < 3:
                            next_comment = None
                            if not self.high_queue.empty():
                                next_comment = self.high_queue.get_nowait()
                            elif not self.medium_queue.empty():
                                next_comment = self.medium_queue.get_nowait()
                            elif not self.low_queue.empty():
                                next_comment = self.low_queue.get_nowait()
                            
                            if next_comment:
                                batch_comments.append(next_comment)
                            else:
                                break
                    
                    if self.on_queue_change:
                        self.on_queue_change(self.get_queue_sizes())
                    
                    # Áp dụng Cooldown 10s cho các thao tác nhạy cảm ở Level 2
                    if self.autopilot_level == 2 and any(c.get("priority") == 1 for c in batch_comments):
                        import time
                        current_time = time.time()
                        time_since_last = current_time - self.last_sensitive_action_time
                        if time_since_last < 10.0:
                            wait_time = 10.0 - time_since_last
                            logger.info(f"⏳ [Autopilot L2] Đang chờ cooldown nhạy cảm: {wait_time:.1f} giây...")
                            await asyncio.sleep(wait_time)
                        self.last_sensitive_action_time = time.time()

                    # Nếu gom được nhiều comment, chạy xử lý gộp
                    if len(batch_comments) > 1:
                        await self._process_batch_comments(batch_comments)
                    else:
                        await self._process_comment(comment_data)
                    
                    # 3. Đợi cho đến khi giọng đọc TTS kết thúc để tránh nói chồng chéo
                    while self.tts.is_playing:
                        await asyncio.sleep(0.5)
                        
                    # Thêm khoảng thời gian giãn cách 3 giây để tạo nhịp tự nhiên (Guardrail #2)
                    await asyncio.sleep(3.0)
                else:
                    # Nếu hàng đợi rỗng, nghỉ ngắn rồi kiểm tra lại
                    await asyncio.sleep(0.5)
                    
        except asyncio.CancelledError:
            pass

    async def _process_batch_comments(self, batch_comments: list[dict[str, Any]]):
        logger.info(f"Đang xử lý BATCH gồm {len(batch_comments)} comments đa nền tảng.")
        
        # 1. Tổng hợp thông tin từ tất cả comment trong batch
        prompt_parts = []
        usernames = []
        platforms = []
        matched_products = []
        
        for idx, c in enumerate(batch_comments):
            user = c.get("username", "")
            plat = c.get("platform", "Local")
            comm = c.get("comment", "")
            
            usernames.append(user)
            platforms.append(plat)
            prompt_parts.append(f"Bình luận {idx+1} từ {plat} - Người dùng '{user}': \"{comm}\"")
            
            # Tìm kiếm sản phẩm liên quan cho comment con
            matched_product = None
            words = comm.split()
            for word in words:
                clean_word = "".join(ch for ch in word if ch.isalnum())
                matched_product = await asyncio.to_thread(db.find_product_by_query, clean_word)
                if matched_product:
                    break
            if not matched_product:
                matched_product = await asyncio.to_thread(db.find_product_by_query, comm)
            
            if matched_product:
                matched_products.append(matched_product)
                # Ghi nhận lượt tương tác sản phẩm (Analytics)
                await asyncio.to_thread(db.increment_product_interactions, matched_product["code"])

        # 2. Xây dựng prompt bình luận gộp
        combined_comment = "\n".join(prompt_parts)
        combined_username = " & ".join(usernames)
        
        # Chọn thông tin sản phẩm đại diện (hoặc sản phẩm đầu tiên tìm thấy)
        repr_product = matched_products[0] if matched_products else None
        
        # Tự động ghim sản phẩm đại diện lên giỏ hàng TikTok Shop
        if repr_product:
            from src.tiktok_shop import global_tiktok_shop
            if repr_product["quantity"] > 0:
                await global_tiktok_shop.pin_product(repr_product["code"])
            else:
                if global_tiktok_shop.pinned_product_code == repr_product["code"]:
                    await global_tiktok_shop.unpin_product()

        
        # 3. Phân tích chốt đơn hàng nháp cho từng comment trong batch
        for c in batch_comments:
            comm_lower = c.get("comment", "").lower()
            checkout_keywords = ["chốt", "chot", "mua", "lấy", "lay", "order"]
            
            # Tìm sản phẩm cho riêng comment này
            c_product = None
            words = c.get("comment", "").split()
            for word in words:
                clean_word = "".join(ch for ch in word if ch.isalnum())
                c_product = await asyncio.to_thread(db.find_product_by_query, clean_word)
                if c_product:
                    break
            if not c_product:
                c_product = await asyncio.to_thread(db.find_product_by_query, c.get("comment", ""))
                
            if c_product and any(kw in comm_lower for kw in checkout_keywords):
                quantity_to_buy = 1
                
                # Check spam chốt đơn cho batch
                now = time.time()
                last_user_time = self.last_checkout_by_user.get(c["username"], 0)
                last_prod_time = self.last_checkout_product_by_user.get((c["username"], c_product["code"]), 0)
                
                if now - last_user_time < 10:
                    logger.warning(f"⚠️ [Batch Spam Block] Chặn {c['username']} chốt đơn quá nhanh ({now - last_user_time:.1f}s < 10s)")
                    continue
                if now - last_prod_time < 30:
                    logger.warning(f"⚠️ [Batch Spam Block] Chặn {c['username']} chốt đơn trùng sản phẩm {c_product['code']} ({now - last_prod_time:.1f}s < 30s)")
                    continue
                
                if c_product["quantity"] >= quantity_to_buy:
                    # Tạo đơn hàng thật và trừ kho trong DB
                    success = await asyncio.to_thread(
                        db.create_order,
                        customer_name=c["username"],
                        platform=c["platform"],
                        product_code=c_product["code"],
                        price=c_product["price"],
                        quantity=quantity_to_buy,
                        status="Chờ xác nhận"
                    )
                    if success:
                        self.last_checkout_by_user[c["username"]] = now
                        self.last_checkout_product_by_user[(c["username"], c_product["code"])] = now
                        logger.info(f"✅ [Batch Checkout] Tự động chốt đơn thành công sản phẩm {c_product['code']} cho {c['username']} ({c['platform']})!")
                        self.vmc_client.trigger_checkout_success(c_product["name"])
                        # Cập nhật lại tồn kho trong local cache nếu cần
                        c_product["quantity"] -= quantity_to_buy
                        
                        # Kích hoạt sự kiện ẩn source OBS nếu tồn kho về 0
                        if c_product["quantity"] <= 0:
                            logger.warning(f"⚠️ Sản phẩm {c_product['code']} đã hết hàng. Kích hoạt ẩn hình ảnh trên OBS.")
                            if self.obs.is_connected:
                                loop = asyncio.get_running_loop()
                                await loop.run_in_executor(
                                    None,
                                    self.obs.set_source_visibility,
                                    "Live Scene",
                                    f"Product_{c_product['code']}",
                                    False
                                )
                else:
                    logger.warning(f"⚠️ [Batch Checkout] Không thể tự động chốt đơn cho {c['username']} vì hết hàng!")

        # 4. Gọi AI sinh câu trả lời gộp
        loop = asyncio.get_running_loop()
        all_prods_list = await asyncio.to_thread(db.get_all_products)
        answer = await loop.run_in_executor(
            None, 
            self.ai.generate_response, 
            combined_username, 
            combined_comment, 
            repr_product,
            None, # context history
            False, # is_checkout
            False, 
            "",
            None, # order_history
            all_prods_list
        )
        
        # 5. Phân tích Sentiment, làm sạch và phát ngôn
        sentiment = "bình thường"
        clean_answer = answer
        match = re.match(r"^\[SENTIMENT:\s*([^\]]+)\]\s*(.*)", answer, re.DOTALL)
        if match:
            sentiment = match.group(1).strip().lower()
            clean_answer = match.group(2).strip()

        # Kiểm duyệt đầu ra AI trước khi xử lý tiếp
        clean_answer = self.moderate_ai_output(clean_answer)

        # Lưu bộ nhớ cho từng khách hàng
        for c in batch_comments:
            await asyncio.to_thread(self.memory_store.save_memory, c["username"], c["comment"], clean_answer)
            # Cập nhật log sự kiện lên GUI cho từng comment
            if self.on_ai_response_callback:
                self.on_ai_response_callback(c["username"], c["comment"], f"[{c['platform']}] {clean_answer}")

        # Đẩy phụ đề lên OBS
        if self.obs.is_connected:
            await loop.run_in_executor(None, self.obs.update_text_source, self.subtitle_source, clean_answer)

        # Cấu hình rate, pitch và biểu cảm VMC tương ứng
        tts_rate = "+0%"
        tts_pitch = "+0Hz"
        vmc_expression = "neutral"
        
        if sentiment == "vui":
            tts_rate = "+5%"
            tts_pitch = "+1Hz"
            vmc_expression = "happy"
        elif sentiment == "khó chịu":
            tts_rate = "-8%"
            tts_pitch = "-3Hz"
            vmc_expression = "sad"
            try:
                self.vmc_client.trigger_apology(3.0)
            except CapabilityUnavailable as e:
                logger.warning(f"Không thể xin lỗi: {e}")
        elif sentiment == "nghi ngờ":
            tts_rate = "-3%"
            tts_pitch = "+1Hz"
            vmc_expression = "surprised"

        # Kích hoạt cử chỉ đặc thù dựa trên loại tương tác phòng livestream trong lô gộp
        for c in batch_comments:
            e_type = c.get("event_type")
            action = self.event_action_mapper.get_event_action(e_type, c.get("comment", ""))
            if action:
                try:
                    self.vmc_client.send_action_trigger(f"/VMC/Ext/Action/{action}", [], source=ActionSource.AI_EVENT)
                    break
                except CapabilityUnavailable as e:
                    logger.warning(f"Không thể kích hoạt động tác '{action}' cho event {e_type}: {e}")
                except Exception as e:
                    logger.warning(f"Lỗi kích hoạt động tác '{action}' cho event {e_type}: {e}")



        # Lấy nền tảng đại diện từ bình luận đầu tiên trong lô gộp
        batch_platform = batch_comments[0].get("platform", "Local") if batch_comments else "Local"
        self._dispatch_speech(batch_platform, clean_answer, tts_rate, tts_pitch, vmc_expression)



    async def _process_comment(self, comment_data: Dict[str, Any]):
        username = comment_data.get("username", "")
        comment = comment_data.get("comment", "")
        platform = comment_data.get("platform", "Local")
        
        logger.info(f"Đang xử lý comment từ {platform}: {username} -> '{comment}'")
        
        # 1. Tìm kiếm sản phẩm liên quan
        matched_product = None
        words = comment.split()
        for word in words:
            clean_word = "".join(c for c in word if c.isalnum())
            matched_product = await asyncio.to_thread(db.find_product_by_query, clean_word)
            if matched_product:
                break
        if not matched_product:
            matched_product = await asyncio.to_thread(db.find_product_by_query, comment)

        # Ghi nhận lượt tương tác sản phẩm (Analytics)
        if matched_product:
            await asyncio.to_thread(db.increment_product_interactions, matched_product["code"])

        # 2. Phân tích chốt đơn hàng nháp
        is_checkout = False
        order_success = False
        order_error_reason = ""
        
        if matched_product:
            comment_lower = comment.lower()
            checkout_keywords = ["chốt", "chot", "mua", "lấy", "lay", "order"]
            if any(kw in comment_lower for kw in checkout_keywords):
                is_checkout = True
                quantity_to_buy = 1
                
                # Check spam chốt đơn
                now = time.time()
                last_user_time = self.last_checkout_by_user.get(username, 0)
                last_prod_time = self.last_checkout_product_by_user.get((username, matched_product["code"]), 0)
                
                if now - last_user_time < 10:
                    order_success = False
                    order_error_reason = "Bạn đang chốt đơn quá nhanh. Vui lòng đợi 10 giây giữa các lần chốt đơn!"
                    logger.warning(f"⚠️ [Spam Block] Chặn {username} chốt đơn quá nhanh ({now - last_user_time:.1f}s < 10s)")
                elif now - last_prod_time < 30:
                    order_success = False
                    order_error_reason = f"Bạn đã chốt sản phẩm {matched_product['code']} gần đây. Vui lòng đợi 30 giây!"
                    logger.warning(f"⚠️ [Spam Block] Chặn {username} chốt đơn trùng sản phẩm {matched_product['code']} ({now - last_prod_time:.1f}s < 30s)")
                elif matched_product["quantity"] >= quantity_to_buy:
                    order_success = True
                else:
                    order_error_reason = "Sản phẩm đã hết hàng trong kho."

        # 3. Gọi AI sinh câu trả lời gợi ý
        history_context = await asyncio.to_thread(self.memory_store.recall_memory, username, comment)
        order_history = await asyncio.to_thread(db.get_orders_by_customer, username)
        all_products = await asyncio.to_thread(db.get_all_products)
        
        loop = asyncio.get_running_loop()
        answer = await loop.run_in_executor(
            None, 
            self.ai.generate_response, 
            username, 
            comment, 
            matched_product,
            history_context,
            is_checkout,
            order_success,
            order_error_reason,
            order_history,
            all_products
        )
        
        # Lưu vào payload
        comment_data["answer"] = answer
        comment_data["is_checkout"] = is_checkout
        comment_data["order_success"] = order_success
        comment_data["order_error_reason"] = order_error_reason
        comment_data["matched_product"] = matched_product

        # NẾU Ở LEVEL 1 (DUYỆT TRƯỚC KHI PHÁT): GỬI LÊN WEB DASHBOARD VÀ KẾT THÚC
        if self.autopilot_level == 1:
            if self.on_pending_approval_callback:
                self.on_pending_approval_callback(comment_data)
            return

        # --- LEVEL 2 & 3: TỰ ĐỘNG THỰC THI NGAY ---
        
        # 1. Cập nhật comment lên OBS Text Source
        if self.obs.is_connected:
            await loop.run_in_executor(
                None, 
                self.obs.update_text_source, 
                self.comment_source, 
                f"[{platform}] {username}: {comment}"
            )

        # 2. Tương tác OBS tự động (Scene / Source) nếu tìm thấy sản phẩm & Tự động ghim giỏ hàng
        if matched_product:
            from src.tiktok_shop import global_tiktok_shop
            if matched_product["quantity"] <= 0:
                logger.warning(f"⚠️ [Low-Stock Alert] Sản phẩm {matched_product['name']} ({matched_product['code']}) đã hết hàng! Tự động ẩn trên OBS.")
                if global_tiktok_shop.pinned_product_code == matched_product["code"]:
                    await global_tiktok_shop.unpin_product()
                if matched_product["obs_scene"] and matched_product["obs_source"] and self.obs.is_connected:
                    await loop.run_in_executor(
                        None,
                        self.obs.set_source_visibility,
                        matched_product["obs_scene"],
                        matched_product["obs_source"],
                        False
                    )
            else:
                # Tự động ghim sản phẩm lên giỏ hàng TikTok Shop
                await global_tiktok_shop.pin_product(matched_product["code"])
                if self.obs.is_connected:
                    if self.auto_scene and matched_product["obs_scene"]:
                        await loop.run_in_executor(None, self.obs.change_scene, matched_product["obs_scene"])
                    if self.auto_show_source and matched_product["obs_scene"] and matched_product["obs_source"]:
                        await loop.run_in_executor(
                            None, 
                            self.obs.set_source_visibility, 
                            matched_product["obs_scene"], 
                            matched_product["obs_source"], 
                            True
                        )


        # 3. Ghi nhận đơn hàng thực tế
        if is_checkout and order_success and matched_product:
            # Gọi tạo đơn hàng thực tế trong Database
            real_success = await asyncio.to_thread(
                db.create_order,
                customer_name=username,
                platform=platform,
                product_code=matched_product["code"],
                price=matched_product["price"],
                quantity=1,
                status="Chờ xác nhận"
            )
            if real_success:
                now = time.time()
                self.last_checkout_by_user[username] = now
                self.last_checkout_product_by_user[(username, matched_product["code"])] = now
                matched_product["quantity"] -= 1
                logger.info(f"🛒 [Tự động chốt đơn] Đã tạo đơn hàng thành công cho {username}: 1x {matched_product['name']}")
                self.vmc_client.trigger_checkout_success(matched_product["name"])
                
                # Check nếu tồn kho vừa về 0
                if matched_product["quantity"] <= 0:
                    logger.warning(f"⚠️ [Low-Stock Alert] Sản phẩm {matched_product['name']} ({matched_product['code']}) đã hết hàng sau chốt đơn! Tự động ẩn trên OBS.")
                    if matched_product["obs_scene"] and matched_product["obs_source"] and self.obs.is_connected:
                        await loop.run_in_executor(
                            None,
                            self.obs.set_source_visibility,
                            matched_product["obs_scene"],
                            matched_product["obs_source"],
                            False
                        )
                if self.signals:
                    self.signals.order_created.emit()
            else:
                logger.error(f"Lỗi lưu đơn hàng vào Database cho khách: {username}")
                comment_data["order_success"] = False
                comment_data["order_error_reason"] = "Không thể lưu đơn vào Database."
                # Gọi lại AI sinh lời thoại xin lỗi
                answer = await loop.run_in_executor(
                    None, 
                    self.ai.generate_response, 
                    username, 
                    comment, 
                    matched_product,
                    history_context,
                    is_checkout,
                    False,
                    "Không thể lưu đơn vào Database."
                )
                comment_data["answer"] = answer

        # Bóc tách Sentiment để điều chỉnh tông giọng và biểu cảm VMC
        sentiment = "bình thường"
        clean_answer = comment_data["answer"]
        match = re.match(r"^\[SENTIMENT:\s*([^\]]+)\]\s*(.*)", comment_data["answer"], re.DOTALL)
        if match:
            sentiment = match.group(1).strip().lower()
            clean_answer = match.group(2).strip()
            
        # Kiểm duyệt đầu ra AI trước khi xử lý tiếp
        clean_answer = self.moderate_ai_output(clean_answer)
        comment_data["answer"] = clean_answer

        # Lưu câu trả lời của AI vào bộ nhớ khách hàng
        await asyncio.to_thread(self.memory_store.save_memory, username, comment, clean_answer)

        # Gọi callback cập nhật GUI
        if self.on_ai_response_callback:
            self.on_ai_response_callback(username, comment, clean_answer)

        # Đẩy phụ đề (Subtitle) lên OBS (không chứa thẻ SENTIMENT)
        if self.obs.is_connected:
            await loop.run_in_executor(None, self.obs.update_text_source, self.subtitle_source, clean_answer)

        # Cấu hình rate, pitch và biểu cảm VMC tương ứng với cảm xúc
        tts_rate = "+0%"
        tts_pitch = "+0Hz"
        vmc_expression = "neutral"
        
        if sentiment == "vui":
            tts_rate = "+5%"
            tts_pitch = "+1Hz"
            vmc_expression = "happy"
        elif sentiment == "khó chịu":
            tts_rate = "-8%"
            tts_pitch = "-3Hz"
            vmc_expression = "sad"
            try:
                self.vmc_client.trigger_apology(3.0)
            except CapabilityUnavailable as e:
                logger.warning(f"Không thể xin lỗi: {e}")
        elif sentiment == "nghi ngờ":
            tts_rate = "-3%"
            tts_pitch = "+1Hz"
            vmc_expression = "surprised"

        # Kích hoạt cử chỉ đặc thù dựa trên loại tương tác phòng livestream
        event_type = comment_data.get("event_type")
        action = self.event_action_mapper.get_event_action(event_type, comment_data.get("comment", ""))
        if action:
            try:
                self.vmc_client.send_action_trigger(f"/VMC/Ext/Action/{action}", [], source=ActionSource.AI_EVENT)

            except CapabilityUnavailable as e:
                logger.warning(f"Không thể kích hoạt động tác '{action}' cho event {event_type}: {e}")
            except Exception as e:
                logger.warning(f"Lỗi kích hoạt động tác '{action}' cho event {event_type}: {e}")


        self._dispatch_speech(platform, clean_answer, tts_rate, tts_pitch, vmc_expression)


    async def execute_approved_comment(self, comment_data: Dict[str, Any]):
        """Thực thi bình luận đã được duyệt bởi người vận hành (Level 1 Autopilot)."""
        username = comment_data.get("username", "")
        comment = comment_data.get("comment", "")
        platform = comment_data.get("platform", "Local")
        answer = comment_data.get("answer", "")
        is_checkout = comment_data.get("is_checkout", False)
        order_success = comment_data.get("order_success", False)
        matched_product = comment_data.get("matched_product")

        logger.info(f"🚀 [Autopilot L1] Đang thực thi bình luận đã duyệt của {username}: '{comment}'")
        
        loop = asyncio.get_running_loop()

        # 1. Cập nhật comment lên OBS
        if self.obs.is_connected:
            await loop.run_in_executor(
                None, 
                self.obs.update_text_source, 
                self.comment_source, 
                f"[{platform}] {username}: {comment}"
            )

        # 2. Tương tác OBS tự động (Scene / Source) nếu tìm thấy sản phẩm & Tự động ghim giỏ hàng
        if matched_product:
            from src.tiktok_shop import global_tiktok_shop
            if matched_product["quantity"] <= 0:
                logger.warning(f"⚠️ [Low-Stock Alert] Sản phẩm {matched_product['name']} ({matched_product['code']}) đã hết hàng! Tự động ẩn trên OBS.")
                if global_tiktok_shop.pinned_product_code == matched_product["code"]:
                    await global_tiktok_shop.unpin_product()
                if matched_product["obs_scene"] and matched_product["obs_source"] and self.obs.is_connected:
                    await loop.run_in_executor(
                        None,
                        self.obs.set_source_visibility,
                        matched_product["obs_scene"],
                        matched_product["obs_source"],
                        False
                    )
            else:
                # Tự động ghim sản phẩm lên giỏ hàng TikTok Shop
                await global_tiktok_shop.pin_product(matched_product["code"])
                if self.obs.is_connected:
                    if self.auto_scene and matched_product["obs_scene"]:
                        await loop.run_in_executor(None, self.obs.change_scene, matched_product["obs_scene"])
                    if self.auto_show_source and matched_product["obs_scene"] and matched_product["obs_source"]:
                        await loop.run_in_executor(
                            None, 
                            self.obs.set_source_visibility, 
                            matched_product["obs_scene"], 
                            matched_product["obs_source"], 
                            True
                        )


        # 3. Ghi nhận đơn hàng thực tế
        if is_checkout and order_success and matched_product:
            # Đọc lại tồn kho thực tế từ Database để đảm bảo an toàn giao dịch
            current_product = await asyncio.to_thread(db.find_product_by_query, matched_product["code"])
            if current_product and current_product["quantity"] >= 1:
                
                # Check spam chốt đơn lúc duyệt (trường hợp duyệt chậm hoặc spam nút bấm)
                now = time.time()
                last_user_time = self.last_checkout_by_user.get(username, 0)
                last_prod_time = self.last_checkout_product_by_user.get((username, matched_product["code"]), 0)
                
                if now - last_user_time < 10 or now - last_prod_time < 30:
                    logger.warning(f"⚠️ Hủy chốt đơn tự động của {username} vì phát hiện spam chốt đơn tại thời điểm duyệt!")
                    comment_data["order_success"] = False
                    if now - last_user_time < 10:
                        comment_data["order_error_reason"] = "Bạn đang chốt đơn quá nhanh. Vui lòng đợi 10 giây giữa các lần chốt đơn!"
                    else:
                        comment_data["order_error_reason"] = f"Bạn đã chốt sản phẩm {matched_product['code']} gần đây. Vui lòng đợi 30 giây!"
                        
                    # Tái sinh câu trả lời
                    history_context = await asyncio.to_thread(self.memory_store.recall_memory, username, comment)
                    order_history = await asyncio.to_thread(db.get_orders_by_customer, username)
                    all_products = await asyncio.to_thread(db.get_all_products)
                    answer = await loop.run_in_executor(
                        None, 
                        self.ai.generate_response, 
                        username, 
                        comment, 
                        matched_product,
                        history_context,
                        is_checkout,
                        False,
                        comment_data["order_error_reason"],
                        order_history,
                        all_products
                    )
                else:
                    real_success = await asyncio.to_thread(
                        db.create_order,
                        customer_name=username,
                        platform=platform,
                        product_code=matched_product["code"],
                        price=matched_product["price"],
                        quantity=1,
                        status="Chờ xác nhận"
                    )
                    if real_success:
                        self.last_checkout_by_user[username] = now
                        self.last_checkout_product_by_user[(username, matched_product["code"])] = now
                        matched_product["quantity"] = current_product["quantity"] - 1
                        logger.info(f"🛒 [Autopilot L1] Tạo đơn thành công cho {username}: 1x {matched_product['name']}")
                        self.vmc_client.trigger_checkout_success(matched_product["name"])
                        
                        if matched_product["quantity"] <= 0:
                            logger.warning(f"⚠️ [Low-Stock Alert] Sản phẩm {matched_product['name']} ({matched_product['code']}) đã hết hàng sau chốt đơn! Tự động ẩn trên OBS.")
                            if matched_product["obs_scene"] and matched_product["obs_source"] and self.obs.is_connected:
                                await loop.run_in_executor(
                                    None,
                                    self.obs.set_source_visibility,
                                    matched_product["obs_scene"],
                                    matched_product["obs_source"],
                                    False
                                )
                        if self.signals:
                            self.signals.order_created.emit()
                    else:
                        logger.error(f"Lỗi lưu đơn Database cho {username}")
                        comment_data["order_success"] = False
                        comment_data["order_error_reason"] = "Không thể lưu đơn vào Database."
                        
                        # Tái sinh câu trả lời
                        history_context = await asyncio.to_thread(self.memory_store.recall_memory, username, comment)
                        order_history = await asyncio.to_thread(db.get_orders_by_customer, username)
                        all_products = await asyncio.to_thread(db.get_all_products)
                        answer = await loop.run_in_executor(
                            None, 
                            self.ai.generate_response, 
                            username, 
                            comment, 
                            matched_product,
                            history_context,
                            is_checkout,
                            False,
                            comment_data["order_error_reason"],
                            order_history,
                            all_products
                        )
            else:
                logger.warning(f"⚠️ Hủy chốt đơn tự động của {username} vì sản phẩm {matched_product['name']} đã hết hàng tại thời điểm duyệt!")
                comment_data["order_success"] = False
                comment_data["order_error_reason"] = "Sản phẩm đã hết hàng trong kho."
                
                # Tái sinh câu trả lời
                history_context = await asyncio.to_thread(self.memory_store.recall_memory, username, comment)
                order_history = await asyncio.to_thread(db.get_orders_by_customer, username)
                all_products = await asyncio.to_thread(db.get_all_products)
                answer = await loop.run_in_executor(
                    None, 
                    self.ai.generate_response, 
                    username, 
                    comment, 
                    matched_product,
                    history_context,
                    is_checkout,
                    False,
                    comment_data["order_error_reason"],
                    order_history,
                    all_products
                )

        # Bóc tách Sentiment để điều chỉnh tông giọng và biểu cảm VMC
        sentiment = "bình thường"
        clean_answer = answer
        match = re.match(r"^\[SENTIMENT:\s*([^\]]+)\]\s*(.*)", answer, re.DOTALL)
        if match:
            sentiment = match.group(1).strip().lower()
            clean_answer = match.group(2).strip()

        # Kiểm duyệt đầu ra AI trước khi xử lý tiếp
        clean_answer = self.moderate_ai_output(clean_answer)

        # Lưu vào bộ nhớ
        await asyncio.to_thread(self.memory_store.save_memory, username, comment, clean_answer)

        # Cập nhật GUI
        if self.on_ai_response_callback:
            self.on_ai_response_callback(username, comment, clean_answer)

        # Đẩy phụ đề (Subtitle) lên OBS
        if self.obs.is_connected:
            await loop.run_in_executor(None, self.obs.update_text_source, self.subtitle_source, clean_answer)

        # Cấu hình rate, pitch và biểu cảm VMC tương ứng với cảm xúc
        tts_rate = "+0%"
        tts_pitch = "+0Hz"
        vmc_expression = "neutral"
        
        if sentiment == "vui":
            tts_rate = "+5%"
            tts_pitch = "+1Hz"
            vmc_expression = "happy"
        elif sentiment == "khó chịu":
            tts_rate = "-8%"
            tts_pitch = "-3Hz"
            vmc_expression = "sad"
        elif sentiment == "nghi ngờ":
            tts_rate = "-3%"
            tts_pitch = "+1Hz"
            vmc_expression = "surprised"

        self._dispatch_speech(platform, clean_answer, tts_rate, tts_pitch, vmc_expression)
