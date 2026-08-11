import os
import shutil
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from ..detector import VNyanDetector

logger = logging.getLogger("VnyanBackupManager")

class VNyanBackupManager:
    def __init__(self, detector: VNyanDetector):
        self.detector = detector
        self.backup_root = Path("backups/vnyan")

    def _get_file_hash(self, filepath: Path) -> str:
        if not filepath.exists():
            return ""
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def create_backup(self) -> str:
        """Tạo sao lưu và manifest trong backups/vnyan/YYYYMMDD_HHMMSS/."""
        config_dir = self.detector.get_config_dir()
        if not config_dir.exists():
            logger.warning("Thư mục cấu hình VNyan không tồn tại. Không thể backup.")
            return ""
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_dir = self.backup_root / timestamp
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        manifest = {
            "timestamp": datetime.now().isoformat(),
            "files": []
        }
        
        # Sao lưu settings.json và các tệp đồ thị node graph
        files_to_backup = ["settings.json", "asredeems.json", "asredeems1.json", "redeems.json", "redeems1.json"]
        for filename in files_to_backup:
            src = config_dir / filename
            if src.exists():
                dest = dest_dir / filename
                shutil.copy2(src, dest)
                h = self._get_file_hash(src)
                manifest["files"].append({
                    "name": filename,
                    "hash": h,
                    "size": src.stat().st_size
                })
                
        # Ghi manifest
        manifest_path = dest_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=4)
            
        logger.info(f"Đã tạo sao lưu thành công tại {dest_dir}")
        return str(dest_dir)

    def restore_backup(self, backup_dir_path: str = None) -> bool:
        """Khôi phục cấu hình từ bản sao lưu cụ thể hoặc bản mới nhất."""
        if not backup_dir_path:
            backup_dir_path = self.find_latest_backup()
            
        if not backup_dir_path:
            logger.warning("Không tìm thấy bản sao lưu nào để khôi phục.")
            return False
            
        src_dir = Path(backup_dir_path)
        manifest_path = src_dir / "manifest.json"
        if not manifest_path.exists():
            logger.error(f"Tệp manifest.json không tồn tại ở thư mục backup {src_dir}.")
            return False
            
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            
        config_dir = self.detector.get_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        
        for file_info in manifest.get("files", []):
            filename = file_info["name"]
            expected_hash = file_info.get("hash", "")
            src_file = src_dir / filename
            dest_file = config_dir / filename
            if src_file.exists():
                shutil.copy2(src_file, dest_file)
                restored_hash = self._get_file_hash(dest_file)
                
                # Kiểm chứng SHA256(before) == SHA256(after rollback)
                if expected_hash and restored_hash != expected_hash:
                    logger.error(f"Lỗi kiểm định SHA256 khi khôi phục {filename}: SHA256(gốc) {expected_hash} != SHA256(sau khôi phục) {restored_hash}")
                    return False
                    
                logger.info(f"Đã khôi phục và xác minh SHA256 chuẩn xác cho file: {filename} (Hash: {restored_hash[:8]}...)")
                
        logger.info(f"Đã khôi phục và kiểm chứng thành công SHA256(before) == SHA256(after rollback) từ {src_dir}.")
        return True

    def find_latest_backup(self) -> str:
        """Dò tìm thư mục sao lưu mới nhất trong backups/vnyan."""
        if not self.backup_root.exists():
            return ""
        dirs = [self.backup_root / d for d in os.listdir(self.backup_root) if (self.backup_root / d).is_dir()]
        if not dirs:
            return ""
        # Sắp xếp theo tên thư mục (YYYYMMDD_HHMMSS)
        dirs.sort()
        return str(dirs[-1])
