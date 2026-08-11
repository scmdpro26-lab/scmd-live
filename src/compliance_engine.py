import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("ComplianceEngine")

class VoiceMode(Enum):
    AI_TTS_AVATAR = "ai_tts_avatar"       # MC ảo đầy đủ (giọng AI + avatar hiển thị lớn)
    AI_COPILOT_HUMAN = "ai_copilot_human" # AI chỉ soạn kịch bản -> Teleprompter cho người thật đọc
    AI_SUBTITLE_ONLY = "ai_subtitle_only" # AI trả lời bằng phụ đề, không giọng nói, không avatar lớn

@dataclass
class PlatformPolicy:
    platform: str
    voice_mode: VoiceMode
    max_avatar_screen_ratio: float   # 0.0 - 1.0
    require_ai_disclosure_label: bool
    require_responsible_person: bool

# Ma trận tuân thủ - nguồn: nghiên cứu chính sách 2026 (audit định kỳ theo dõi thay đổi)
COMPLIANCE_MATRIX = {
    "TikTok": PlatformPolicy(
        platform="TikTok",
        voice_mode=VoiceMode.AI_TTS_AVATAR,       # Cho phép dùng TTS đầy đủ tại Việt Nam
        max_avatar_screen_ratio=1.0,
        require_ai_disclosure_label=True,
        require_responsible_person=True,
    ),
    "TikTok_US": PlatformPolicy(
        platform="TikTok_US",
        voice_mode=VoiceMode.AI_COPILOT_HUMAN,    # Giới hạn dùng TTS của thị trường Mỹ
        max_avatar_screen_ratio=0.45,
        require_ai_disclosure_label=True,
        require_responsible_person=True,
    ),
    "Facebook": PlatformPolicy(
        platform="Facebook",
        voice_mode=VoiceMode.AI_TTS_AVATAR,
        max_avatar_screen_ratio=1.0,
        require_ai_disclosure_label=True,
        require_responsible_person=True,
    ),
    "YouTube": PlatformPolicy(
        platform="YouTube",
        voice_mode=VoiceMode.AI_TTS_AVATAR,
        max_avatar_screen_ratio=1.0,
        require_ai_disclosure_label=True,
        require_responsible_person=True,
    ),
}

def get_policy(platform: str) -> PlatformPolicy:
    """Lấy chính sách tuân thủ theo nền tảng.
    Mặc định chế độ khắt khe nhất (TikTok) làm fail-safe nếu platform không khớp.
    """
    if not platform:
        return COMPLIANCE_MATRIX["TikTok"]
    
    # Tìm kiếm không phân biệt chữ hoa thường
    for key, policy in COMPLIANCE_MATRIX.items():
        if key.lower() == platform.lower():
            return policy
            
    return COMPLIANCE_MATRIX["TikTok"]

def apply_disclosure_overlay(obs_client, platform: str):
    """Tự động bật/tắt nhãn minh bạch AI trên OBS dựa theo chính sách của nền tảng."""
    policy = get_policy(platform)
    if not obs_client or not obs_client.is_connected:
        return
        
    try:
        if policy.require_ai_disclosure_label:
            logger.info(f"Kích hoạt hiển thị nhãn minh bạch AI trên OBS cho nền tảng: {platform}")
            obs_client.set_source_visibility("Live Scene", "AI_Disclosure_Badge", True)
        else:
            logger.info(f"Ẩn nhãn minh bạch AI trên OBS cho nền tảng: {platform}")
            obs_client.set_source_visibility("Live Scene", "AI_Disclosure_Badge", False)
    except Exception as e:
        logger.error(f"Lỗi khi điều khiển nhãn AI trên OBS: {e}")
