import time
import logging
import threading
import json
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("ActionEngine")


class ActionSource:
    WEB = 3         # Cử chỉ kích hoạt thủ công từ Dashboard - Ưu tiên cao nhất
    AI_EVENT = 2    # Sự kiện mua hàng, chốt đơn, live event - Ưu tiên trung bình
    SPEECH = 1      # Cử chỉ tự động sinh ra từ câu thoại AI - Ưu tiên thấp nhất


class ActionPriority:
    P0 = 0  # Safety / System (Reset, Stop)
    P1 = 1  # E-commerce events (Checkout, Voucher, Cart)
    P2 = 2  # AI speech commerce directives (PointDown, Present)
    P3 = 3  # Cosmetic (Clap, Heart, Greeting, Dance)


class ActionEngine:
    """Bộ điều phối hành động MC ảo duy nhất (Centralized Action Engine).

    Chịu trách nhiệm validate, lọc trùng, cooldown, độ ưu tiên và cắt ngang cử chỉ.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ActionEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, animation_controller=None):
        if self._initialized:
            return
        self.controller = animation_controller
        self.last_action_time = 0.0
        self.last_action_name = None
        self.current_source = None
        self.current_action = None
        self.last_triggered = {}  # Key: (action_id, source), Value: timestamp
        self.state = "IDLE"       # IDLE, PLAYING, COOLDOWN
        self.queue = []           # Hàng đợi cử chỉ chờ thực thi: list of (action_id, source, arguments)
        self.command_counter = 0  # Bộ đếm Command ID
        self._lock = threading.RLock() # Reentrant Lock bảo vệ state machine

        
        # Nạp Manifest cấu hình trung tâm
        manifest_path = Path("profiles/action_manifest.json")
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
                    for act, cfg in manifest_data.items():
                        self.ACTION_CONFIGS[act] = cfg
                logger.info("ActionEngine: Nạp cấu hình thành công từ profiles/action_manifest.json")
            except Exception as e:
                logger.error(f"ActionEngine: Lỗi nạp action_manifest.json: {e}")
                
        self._initialized = True


    def generate_command_id(self) -> str:
        """Sinh Command ID duy nhất dạng CMD-YYYYMMDD-XXXXXX."""
        self.command_counter += 1
        date_str = time.strftime("%Y%m%d")
        return f"CMD-{date_str}-{self.command_counter:06d}"


    ACTION_CONFIGS = {
        "AI_LIVE_RESET":           {"priority": 0, "interruptible": True, "queueable": False, "duration": 1.0, "cooldown": 1.0},
        "AI_LIVE_STOP":            {"priority": 0, "interruptible": True, "queueable": False, "duration": 1.0, "cooldown": 1.0},
        
        "AI_LIVE_CHECKOUT_SUCCESS":{"priority": 1, "interruptible": True, "queueable": False, "duration": 4.0, "cooldown": 4.0},
        "AI_LIVE_VOUCHER_DROP":    {"priority": 1, "interruptible": True, "queueable": False, "duration": 3.0, "cooldown": 3.0},
        "AI_LIVE_CART_PIN":        {"priority": 1, "interruptible": True, "queueable": False, "duration": 3.0, "cooldown": 3.0},
        "AI_LIVE_VOUCHER_SHOW":    {"priority": 1, "interruptible": True, "queueable": False, "duration": 3.0, "cooldown": 3.0},
        
        "AI_LIVE_POINT_DOWN":      {"priority": 2, "interruptible": True, "queueable": False, "duration": 3.0, "cooldown": 3.0},
        "AI_LIVE_PRESENT_LEFT":    {"priority": 2, "interruptible": True, "queueable": False, "duration": 3.0, "cooldown": 3.0},
        "AI_LIVE_PRESENT_RIGHT":   {"priority": 2, "interruptible": True, "queueable": False, "duration": 3.0, "cooldown": 3.0},
        
        "AI_LIVE_GREETING":        {"priority": 3, "interruptible": True, "queueable": False, "duration": 2.5, "cooldown": 2.0},
        "AI_LIVE_CLAP":            {"priority": 3, "interruptible": True, "queueable": False, "duration": 2.5, "cooldown": 2.0},
        "AI_LIVE_HEART":           {"priority": 3, "interruptible": True, "queueable": False, "duration": 2.5, "cooldown": 2.0},
        "AI_LIVE_POINT_UP":        {"priority": 3, "interruptible": True, "queueable": False, "duration": 2.5, "cooldown": 2.0},
        "AI_LIVE_DANCE":           {"priority": 3, "interruptible": True, "queueable": False, "duration": 5.0, "cooldown": 5.0},
        "AI_LIVE_APOLOGY":         {"priority": 3, "interruptible": True, "queueable": False, "duration": 2.5, "cooldown": 2.0},
        "AI_LIVE_MINIGAME_START":  {"priority": 3, "interruptible": True, "queueable": False, "duration": 3.0, "cooldown": 3.0},
        "AI_LIVE_CELEBRATE":       {"priority": 3, "interruptible": True, "queueable": False, "duration": 3.0, "cooldown": 3.0},
    }

    DEFAULT_CONFIG = {"priority": 3, "interruptible": True, "queueable": False, "duration": 2.5, "cooldown": 2.0}

    def set_controller(self, animation_controller):
        """Liên kết với AnimationController tại thời điểm runtime."""
        self.controller = animation_controller

    def get_action_priority(self, action_id: str) -> int:
        """Trả về mức độ ưu tiên tương ứng của Action ID."""
        config = self.ACTION_CONFIGS.get(action_id, self.DEFAULT_CONFIG)
        return config["priority"]

    def normalize_to_canonical_id(self, action_name: str) -> Optional[str]:
        """Chuẩn hóa các dạng tên action về Action ID canonical duy nhất.

        Ví dụ:
        - "point_down" -> "AI_LIVE_POINT_DOWN"
        - "PointDown" -> "AI_LIVE_POINT_DOWN"
        - "AI_LIVE_POINT_DOWN" -> "AI_LIVE_POINT_DOWN"
        
        Trả về None nếu action không hợp lệ hoặc không có trong CANONICAL_ACTIONS.
        """
        if not action_name:
            return None

        name_clean = str(action_name).strip().lower().replace("-", "_")

        from ai_live.integrations.vnyan.constants import CANONICAL_ACTIONS

        # 1. Khớp trực tiếp với key (ví dụ "point_down")
        if name_clean in CANONICAL_ACTIONS:
            return f"AI_LIVE_{name_clean.upper()}"

        # 2. Khớp với value (ví dụ "pointdown" hoặc "pointup")
        for key, val in CANONICAL_ACTIONS.items():
            if val.lower() == name_clean or val.lower().replace("_", "") == name_clean.replace("_", ""):
                return f"AI_LIVE_{key.upper()}"

        # 3. Khớp định dạng canonical Action ID (ví dụ "ai_live_point_down")
        if name_clean.startswith("ai_live_"):
            canonical_key = name_clean[8:]
            if canonical_key in CANONICAL_ACTIONS:
                return f"AI_LIVE_{canonical_key.upper()}"

        return None

    def update_state(self) -> str:
        """Đồng bộ trạng thái Gesture State Machine dựa trên thời gian chạy thực tế."""
        with self._lock:
            if not self.current_action:
                self.state = "IDLE"
                return self.state

            now = time.time()
            config = self.ACTION_CONFIGS.get(self.current_action, self.DEFAULT_CONFIG)
            duration = config["duration"]
            cooldown = config["cooldown"]
            elapsed = now - self.last_action_time

            if self.state == "PLAYING" and elapsed >= duration:
                self.state = "COOLDOWN"
                logger.info(f"StateMachine: Cử chỉ '{self.current_action}' hoàn thành. Chuyển PLAYING -> COOLDOWN.")

            if self.state == "COOLDOWN" and elapsed >= (duration + cooldown):
                self.state = "IDLE"
                logger.info(f"StateMachine: Chuyển COOLDOWN -> IDLE. Giải phóng cử chỉ cũ '{self.current_action}'.")
                self.current_action = None
                self.current_source = None

                # Tự động dequeue và kích hoạt phần tử chờ đợi tiếp theo nếu có
                if self.queue:
                    next_action, next_source, next_args = self.queue.pop(0)
                    logger.info(f"StateMachine: Tự động Dequeue và kích hoạt cử chỉ '{next_action}' từ hàng đợi.")
                    self.dispatch(next_action, next_source, next_args)

            return self.state


    def dispatch(self, action_name: str, source: int, arguments: list | None = None) -> bool:
        """Kiểm duyệt, chuẩn hóa và chuyển tiếp lệnh cử chỉ đến AnimationController.

        Args:
            action_name: Tên action (ví dụ: 'dance', 'Greeting')
            source: Nguồn kích hoạt từ ActionSource
            arguments: Danh sách đối số truyền kèm cử chỉ

        Returns:
            True nếu cử chỉ được duyệt và thực thi thành công, ngược lại False.
        """
        if arguments is None:
            arguments = []

        if not self.controller:
            logger.warning("ActionEngine: Chưa liên kết với AnimationController.")
            return False

        with self._lock:
            # 1. Validate & Normalize to Canonical Action ID
            action_id = self.normalize_to_canonical_id(action_name)
            if not action_id:
                logger.warning(
                    f"ActionEngine: Từ chối cử chỉ không hợp lệ hoặc tự suy diễn: '{action_name}'"
                )
                return False

            # Sinh Command ID
            cmd_id = self.generate_command_id()

            # Đồng bộ trạng thái State Machine hiện thời trước khi xử lý
            self.update_state()

            initial_state = self.state
            initial_action = self.current_action if self.current_action else "IDLE"

            now = time.time()

            # 2. Cooldown & Dedupe (same action + same source + trong cooldown window -> DROP)
            key = (action_id, source)
            last_time = self.last_triggered.get(key, 0.0)
            config = self.ACTION_CONFIGS.get(action_id, self.DEFAULT_CONFIG)
            cooldown_limit = config["cooldown"]

            if now - last_time < cooldown_limit:
                self._log_command_trace(
                    cmd_id=cmd_id,
                    source=source,
                    action_id=action_id,
                    priority=config["priority"],
                    state=initial_action,
                    interrupt="None",
                    transport="None",
                    result=f"DROPPED_COOLDOWN (limit {cooldown_limit}s)"
                )
                return False

            # 3. State Machine & Priority Interrupt Policy
            interrupt_action = "None"
            new_priority = config["priority"]

            if self.state == "PLAYING" and self.current_action:
                old_config = self.ACTION_CONFIGS.get(self.current_action, self.DEFAULT_CONFIG)
                old_priority = old_config["priority"]

                # Ngoại lệ: Lệnh từ Dashboard WEB luôn có quyền ngắt P2, P3 (nâng ưu tiên lên tối thiểu P1)
                if source == ActionSource.WEB and new_priority > ActionPriority.P1:
                    new_priority = ActionPriority.P1

                # Kiểm tra khả năng ngắt (Interruptible) của cử chỉ cũ
                if not old_config.get("interruptible", True):
                    self._log_command_trace(
                        cmd_id=cmd_id,
                        source=source,
                        action_id=action_id,
                        priority=new_priority,
                        state=initial_action,
                        interrupt="None",
                        transport="None",
                        result="DROPPED_NON_INTERRUPTIBLE"
                    )
                    if config.get("queueable", False) and len(self.queue) < 3:
                        self.queue.append((action_id, source, arguments))
                        logger.info(f"ActionEngine: Đưa '{action_id}' vào hàng chờ queue.")
                    return False

                # So sánh độ ưu tiên (số nhỏ hơn ưu tiên cao hơn)
                if new_priority < old_priority:
                    interrupt_action = self.current_action
                else:
                    self._log_command_trace(
                        cmd_id=cmd_id,
                        source=source,
                        action_id=action_id,
                        priority=new_priority,
                        state=initial_action,
                        interrupt="None",
                        transport="None",
                        result=f"DROPPED_PRIORITY (current priority: {old_priority})"
                    )
                    if config.get("queueable", False) and len(self.queue) < 3:
                        self.queue.append((action_id, source, arguments))
                        logger.info(f"ActionEngine: Đưa '{action_id}' vào hàng chờ queue.")
                    return False

            # Kích hoạt qua Controller và nhận kết quả trước khi cập nhật trạng thái
            success, transport = self.controller.trigger_animation(action_id, arguments)
            result_str = "SUCCESS" if success else "FAILED"

            if success:
                # Chỉ cập nhật trạng thái sang PLAYING khi transport thành công
                self.state = "PLAYING"
                self.last_action_time = now
                self.last_action_name = action_id
                self.current_source = source
                self.current_action = action_id
                self.last_triggered[key] = now
            else:
                logger.warning(
                    f"ActionEngine: Kích hoạt cử chỉ '{action_id}' thất bại trên transport {transport}. Trạng thái MC giữ nguyên: {initial_state}."
                )

            # Ghi nhật ký trace
            self._log_command_trace(
                cmd_id=cmd_id,
                source=source,
                action_id=action_id,
                priority=new_priority,
                state=initial_action,
                interrupt=interrupt_action,
                transport=transport,
                result=result_str
            )
            return success


    def _log_command_trace(self, cmd_id: str, source: int, action_id: str, priority: int, state: str, interrupt: str, transport: str, result: str):
        """Ghi nhận log trace định danh duy nhất phục vụ debug cử chỉ."""
        source_name = "SPEECH"
        if source == ActionSource.WEB:
            source_name = "WEB"
        elif source == ActionSource.AI_EVENT:
            source_name = "TIKTOK"
            
        now_str = time.strftime("%H:%M:%S") + f".{int((time.time() % 1) * 1000):03d}"
        
        trace_msg = (
            f"\n========================================\n"
            f"[COMMAND TRACE] {cmd_id}\n"
            f"Timestamp: {now_str}\n"
            f"Source: {source_name}\n"
            f"Action: {action_id}\n"
            f"Priority: {priority}\n"
            f"State: {state}\n"
            f"Interrupt: {interrupt}\n"
            f"Transport: {transport}\n"
            f"Result: {result}\n"
            f"========================================"
        )
        logger.info(trace_msg)


    def submit(self, action: str, source: int, arguments: list | None = None) -> bool:
        """Đệ trình cử chỉ lên ActionEngine (alias của dispatch)."""
        with self._lock:
            return self.dispatch(action, source, arguments)






