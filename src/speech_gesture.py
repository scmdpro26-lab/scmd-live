"""
Speech-to-Gesture Parser: Phân tích câu nói của AI và kích hoạt cử chỉ
diễn giải phù hợp trước khi TTS phát âm, làm MC ảo tự nhiên hơn.
"""
import re
import json
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING
from src.action_engine import ActionSource

if TYPE_CHECKING:
    from src.vmc_adapter import VirtualMCAdapter

logger = logging.getLogger("SpeechGestureParser")


# Đường dẫn mặc định đến file cấu hình rules
_DEFAULT_RULES_PATH = Path("profiles/speech_gesture_rules.json")


class SpeechGestureParser:
    """Phân tích câu nói để kích hoạt cử chỉ diễn giải phù hợp.

    - Load rules từ ``profiles/speech_gesture_rules.json``.
    - Nếu file không tồn tại, tự động tắt im lặng (không crash).
    - Kích hoạt cử chỉ trong luồng nền (non-blocking) để không gây
      trễ luồng TTS.
    """

    def __init__(self, rules_path: Path = _DEFAULT_RULES_PATH):
        self.rules_path = rules_path
        self._rules: list[dict] = []
        self._load_rules()

    def _load_rules(self) -> None:
        """Nạp rules từ file JSON. Không raise exception nếu file thiếu."""
        if not self.rules_path.exists():
            logger.info(
                f"SpeechGestureParser: file rules không tồn tại tại "
                f"'{self.rules_path}'. Speech-to-gesture bị tắt."
            )
            self._rules = []
            return
        try:
            with open(self.rules_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._rules = data.get("rules", [])
            logger.info(
                f"SpeechGestureParser: Đã nạp {len(self._rules)} rules từ '{self.rules_path}'."
            )
        except Exception as e:
            logger.warning(f"SpeechGestureParser: Lỗi khi đọc file rules: {e}")
            self._rules = []

    def reload_rules(self) -> None:
        """Tải lại rules từ disk (hot-reload không cần restart)."""
        self._load_rules()

    def find_gesture(self, text: str) -> str | None:
        """Tìm action tối ưu nhất dựa trên điểm tin cậy, ngữ cảnh và độ ưu tiên."""
        if not text or not self._rules:
            return None

        # Thiết lập ngữ cảnh hiện tại (có thể được thay đổi động tại runtime)
        current_context = getattr(self, "current_context", "default")
        text_lower = text.lower()
        matched_rules = []

        for rule in self._rules:
            action = rule.get("action")
            keywords = rule.get("keywords", [])
            if not action or not keywords:
                continue

            # Kiểm tra Context
            rule_contexts = rule.get("context", [])
            # Nếu rule có định nghĩa context và context hiện tại không nằm trong đó -> bỏ qua
            if rule_contexts and current_context not in rule_contexts:
                continue

            # Tính toán Confidence & Match Keywords
            matched_kws = []
            for kw in keywords:
                pattern = re.compile(rf"\b{re.escape(kw.lower())}\b" if len(kw) <= 2 else re.escape(kw.lower()))
                if pattern.search(text_lower):
                    matched_kws.append(kw)

            if matched_kws:
                # Điểm tin cậy cơ bản + thưởng 0.1 cho mỗi keyword khớp thêm
                base_conf = float(rule.get("confidence", 1.0))
                extra_conf = (len(matched_kws) - 1) * 0.1
                final_score = min(base_conf + extra_conf, 1.0)
                
                matched_rules.append({
                    "action": action,
                    "priority": int(rule.get("priority", 1)),
                    "score": final_score,
                    "matched_kw": matched_kws[0]
                })

        if not matched_rules:
            return None

        # Sắp xếp theo: 1. Priority (giảm dần), 2. Score (giảm dần)
        matched_rules.sort(key=lambda r: (-r["priority"], -r["score"]))

        best_rule = matched_rules[0]
        # Ngưỡng tin cậy tối thiểu 0.5
        if best_rule["score"] >= 0.5:
            logger.info(
                f"SpeechGestureParser: Chọn '{best_rule['action']}' (Score: {best_rule['score']:.2f}, "
                f"Priority: {best_rule['priority']}, Context: {current_context}) từ khóa khớp '{best_rule['matched_kw']}'"
            )
            return best_rule["action"]

        logger.info(f"SpeechGestureParser: Cử chỉ '{best_rule['action']}' bị loại bỏ do score {best_rule['score']:.2f} < 0.5")
        return None


    def parse_and_trigger(self, text: str, vmc_client: "VirtualMCAdapter") -> None:
        """Phân tích text và kích hoạt cử chỉ phù hợp trong luồng nền.

        Không block luồng gọi (TTS / hàng đợi). Nếu vmc_client là None
        hoặc không có action khớp, không làm gì cả.

        Args:
            text:       Câu nói AI sinh ra (clean_answer).
            vmc_client: Instance VirtualMCAdapter để gọi trigger.
        """
        if not vmc_client or not text:
            return

        action = self.find_gesture(text)
        if not action:
            return

        # Kích hoạt trong thread daemon riêng để không block luồng TTS
        def _trigger():
            try:
                # Gọi thẳng send_action_trigger với source=ActionSource.SPEECH
                success = vmc_client.send_action_trigger(f"/VMC/Ext/Action/{action}", [], source=ActionSource.SPEECH)
                if success:
                    logger.info(
                        f"SpeechGestureParser: Đã kích hoạt cử chỉ '{action}' dựa trên nội dung câu nói."
                    )
                else:
                    logger.info(
                        f"SpeechGestureParser: Cử chỉ '{action}' bị từ chối bởi ActionEngine (cooldown/priority)."
                    )

            except Exception as e:
                logger.error(f"SpeechGestureParser: Lỗi khi kích hoạt gesture '{action}': {e}")

        threading.Thread(target=_trigger, daemon=True, name="speech-gesture").start()
