import logging
from ..models import AvatarExpressionProfile
from ..constants import EXPRESSION_CANDIDATES

logger = logging.getLogger("ExpressionMapper")

class ExpressionMapper:
    def map_expressions(self, available_names: list[str], blendshape_groups: list[dict] = None) -> AvatarExpressionProfile:
        """Thực hiện tính toán scoring độ tương đồng để tự động map các biểu cảm và miệng."""
        if blendshape_groups is None:
            blendshape_groups = []
            
        groups_by_name = {g.get("name", ""): g for g in blendshape_groups if g.get("name")}
        
        mapping = {}
        targets = list(EXPRESSION_CANDIDATES.keys())
        
        MIN_CONFIDENCE_THRESHOLD = 0.65
        
        for target in targets:
            candidates = EXPRESSION_CANDIDATES[target]
            best_name = None
            best_score = -1.0
            
            for name in available_names:
                preset_name = ""
                if name in groups_by_name:
                    preset_name = groups_by_name[name].get("presetName", "")
                    
                score = self._calculate_score(name, preset_name, target, candidates)
                if score > best_score and score >= MIN_CONFIDENCE_THRESHOLD:
                    best_score = score
                    best_name = name
                    
            mapping[target] = best_name
            if best_name:
                logger.info(f"Expression Map: {target} -> {best_name} (Confidence Score: {best_score:.2f})")
            else:
                logger.warning(f"Expression Map Skipped: {target} (Không tìm thấy match đạt ngưỡng tin cậy >= {MIN_CONFIDENCE_THRESHOLD})")
            
        # Tìm các biểu cảm tùy chỉnh khác (custom) không được map vào core
        mapped_values = set(mapping.values())
        custom_expressions = [name for name in available_names if name not in mapped_values]
        
        return AvatarExpressionProfile(
            available=available_names,
            viseme_a=mapping.get("viseme_a"),
            viseme_e=mapping.get("viseme_e"),
            viseme_i=mapping.get("viseme_i"),
            viseme_o=mapping.get("viseme_o"),
            viseme_u=mapping.get("viseme_u"),
            
            happy=mapping.get("happy"),
            sad=mapping.get("sad"),
            angry=mapping.get("angry"),
            surprised=mapping.get("surprised"),
            relaxed=mapping.get("relaxed"),
            neutral=mapping.get("neutral"),
            
            blink=mapping.get("blink"),
            blink_left=mapping.get("blink_left"),
            blink_right=mapping.get("blink_right"),
            
            custom=custom_expressions
        )

    def _calculate_score(self, name: str, preset_name: str, semantic: str, candidates: list[str]) -> float:
        name_lower = name.lower()
        preset_lower = preset_name.lower() if preset_name else ""
        semantic_lower = semantic.lower()
        
        # 1. Khớp chính xác hoàn toàn (Case-sensitive)
        if name == semantic:
            return 1.0
            
        # 2. Khớp chính xác không phân biệt hoa thường
        if name_lower == semantic_lower:
            return 0.95
            
        # Tránh khớp chớp mắt một bên vào chớp mắt tổng thể
        if semantic == "blink":
            if "left" in name_lower or "right" in name_lower or name_lower.endswith("_l") or name_lower.endswith("_r") or name_lower.endswith("l") or name_lower.endswith("r"):
                return 0.0
            
        # 3. Khớp PresetName của VRM 0.x
        if preset_lower:
            if semantic_lower.startswith("viseme_") and len(preset_lower) == 1:
                if semantic_lower.endswith(preset_lower):
                    return 0.90
            preset_map = {
                "joy": ["happy", "joy"],
                "angry": ["angry"],
                "sorrow": ["sad", "sorrow"],
                "fun": ["happy", "fun"],
                "blink": ["blink"],
                "blink_l": ["blink_left", "blinkleft"],
                "blink_r": ["blink_right", "blinkright"],
                "neutral": ["neutral"]
            }
            for p_key, p_sem_list in preset_map.items():
                if preset_lower == p_key and semantic_lower in p_sem_list:
                    return 0.90

        # 4. Khớp trực tiếp trong danh sách candidates
        if name_lower in candidates:
            return 0.85
            
        # 5. Khớp từ khóa con (substring) - tránh khớp sai các ký tự ngắn như 'a', 'e'
        for cand in candidates:
            if len(cand) > 2:
                if cand in name_lower:
                    return 0.75
            else:
                if name_lower == cand or name_lower.startswith(cand + "_") or name_lower.endswith("_" + cand):
                    return 0.80
                
        # 6. Tính khoảng cách tương tự theo ký tự trùng lặp
        if len(name_lower) > 2:
            common = set(name_lower).intersection(set(semantic_lower))
            if common:
                return 0.2 + (len(common) / max(len(name_lower), len(semantic_lower))) * 0.3

        return 0.0
