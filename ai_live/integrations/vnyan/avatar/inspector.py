import os
import struct
import json
import logging
from pathlib import Path
from datetime import datetime
from ..models import AvatarProfile, AvatarExpressionProfile
from ..exceptions import VRMInspectError
from .expression_mapper import ExpressionMapper

logger = logging.getLogger("VRMInspector")

class VRMInspector:
    def __init__(self):
        self.mapper = ExpressionMapper()

    def inspect(self, filepath: Path) -> AvatarProfile:
        """Phân tích tệp tin avatar .vrm nhị phân (GLB) và trích xuất cấu hình AvatarProfile."""
        if not filepath.exists():
            raise VRMInspectError(f"Không tìm thấy tệp avatar VRM tại: {filepath}")
            
        try:
            # 1. Đọc và phân giải JSON chunk từ tệp GLB nhị phân
            json_data = self._parse_glb_json(filepath)
            if not json_data:
                raise VRMInspectError(f"Không thể giải nén JSON chunk từ tệp GLB: {filepath}")
                
            # 2. Lấy thông tin VRM extension
            extensions = json_data.get("extensions", {})
            vrm_ext = extensions.get("VRM") or extensions.get("vrm")
            if not vrm_ext:
                raise VRMInspectError("Không tìm thấy dữ liệu mở rộng VRM extension trong tệp glTF.")
                
            exporter_version = vrm_ext.get("exporterVersion", "Unknown")
            meta = vrm_ext.get("meta", {})
            
            version = meta.get("version", "Unknown")
            
            # 3. Đọc danh sách blendshapes (blendShapeGroups)
            blend_shape_master = vrm_ext.get("blendShapeMaster", {})
            groups = blend_shape_master.get("blendShapeGroups", [])
            
            # Danh sách các expression có sẵn
            available_expressions = []
            for g in groups:
                name = g.get("name")
                if name:
                    available_expressions.append(name)
                    
            # 4. Sử dụng ExpressionMapper để map động biểu cảm theo scoring
            expr_profile = self.mapper.map_expressions(available_expressions, groups)
            
            # 5. Phân tích thống kê từ glTF JSON
            materials_count = len(json_data.get("materials", []))
            textures_count = len(json_data.get("textures", []))
            
            # Đếm số bones từ skins
            bones_count = 0
            skins = json_data.get("skins", [])
            for skin in skins:
                bones_count += len(skin.get("joints", []))
            if bones_count == 0:
                bones_count = len(json_data.get("nodes", []))
                
            height = 1.63
            
            return AvatarProfile(
                source_path=filepath,
                format="VRM",
                version=version,
                height=height,
                bones=bones_count,
                materials=materials_count,
                textures=textures_count,
                expressions=expr_profile,
                detected_at=datetime.now()
            )
        except Exception as e:
            logger.error(f"Lỗi phân tích tệp VRM {filepath}: {e}")
            raise VRMInspectError(f"Thất bại khi phân tích VRM: {e}")

    def _parse_glb_json(self, filepath: Path) -> dict | None:
        """Đọc JSON chunk 0 của tệp GLB nhị phân."""
        with open(filepath, "rb") as f:
            magic = f.read(4)
            if magic != b"glTF":
                return None
                
            version, length = struct.unpack("<II", f.read(8))
            
            # Chunk 0
            chunk_length, chunk_type = struct.unpack("<II", f.read(8))
            if chunk_type != 0x4E4F534A:  # b'JSON'
                return None
                
            json_bytes = f.read(chunk_length)
            json_str = json_bytes.decode("utf-8", errors="ignore")
            return json.loads(json_str)
