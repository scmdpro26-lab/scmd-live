import os
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from ..models import AvatarProfile, AvatarExpressionProfile

logger = logging.getLogger("AvatarProfileManager")

class AvatarProfileManager:
    def __init__(self):
        self.profiles_dir = Path("profiles/avatars")
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_hash(self, filepath: Path) -> str:
        if not filepath.exists():
            return ""
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def get_profile_path(self, avatar_path: Path) -> Path:
        h = self._get_file_hash(avatar_path)
        return self.profiles_dir / f"{h}.json"

    def save_profile(self, profile: AvatarProfile) -> bool:
        """Lưu profile avatar vào tệp tin JSON profiles/avatars/<hash>.json."""
        dest_path = self.get_profile_path(profile.source_path)
        try:
            # Chuyển đổi AvatarProfile sang dict
            expr = profile.expressions
            data = {
                "schema_version": 1,
                "avatar_hash": dest_path.stem,
                "source_path": str(profile.source_path),
                "format": profile.format,
                "version": profile.version,
                "height": profile.height,
                "bones": profile.bones,
                "materials": profile.materials,
                "textures": profile.textures,
                "detected_at": profile.detected_at.isoformat(),
                "expressions": {
                    "available": expr.available,
                    "viseme_a": expr.viseme_a,
                    "viseme_e": expr.viseme_e,
                    "viseme_i": expr.viseme_i,
                    "viseme_o": expr.viseme_o,
                    "viseme_u": expr.viseme_u,
                    "happy": expr.happy,
                    "sad": expr.sad,
                    "angry": expr.angry,
                    "surprised": expr.surprised,
                    "relaxed": expr.relaxed,
                    "neutral": expr.neutral,
                    "blink": expr.blink,
                    "blink_left": expr.blink_left,
                    "blink_right": expr.blink_right,
                    "custom": expr.custom
                }
            }
            # Ghi an toàn
            temp_path = str(dest_path) + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            os.replace(temp_path, str(dest_path))
            logger.info(f"Đã lưu tệp cấu hình Avatar Profile tại {dest_path}")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi lưu tệp cấu hình Avatar Profile: {e}")
            return False

    def load_profile(self, avatar_path: Path) -> AvatarProfile | None:
        """Nạp profile avatar từ tệp tin JSON nếu tồn tại."""
        dest_path = self.get_profile_path(avatar_path)
        if not dest_path.exists():
            return None
        try:
            with open(dest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            expr_data = data.get("expressions", {})
            expr = AvatarExpressionProfile(
                available=expr_data.get("available", []),
                viseme_a=expr_data.get("viseme_a"),
                viseme_e=expr_data.get("viseme_e"),
                viseme_i=expr_data.get("viseme_i"),
                viseme_o=expr_data.get("viseme_o"),
                viseme_u=expr_data.get("viseme_u"),
                happy=expr_data.get("happy"),
                sad=expr_data.get("sad"),
                angry=expr_data.get("angry"),
                surprised=expr_data.get("surprised"),
                relaxed=expr_data.get("relaxed"),
                neutral=expr_data.get("neutral"),
                blink=expr_data.get("blink"),
                blink_left=expr_data.get("blink_left"),
                blink_right=expr_data.get("blink_right"),
                custom=expr_data.get("custom", [])
            )
            
            return AvatarProfile(
                source_path=Path(data["source_path"]),
                format=data["format"],
                version=data["version"],
                height=data["height"],
                bones=data["bones"],
                materials=data["materials"],
                textures=data["textures"],
                expressions=expr,
                detected_at=datetime.fromisoformat(data["detected_at"])
            )
        except Exception as e:
            logger.error(f"Lỗi khi nạp tệp cấu hình Avatar Profile từ {dest_path}: {e}")
            return None
