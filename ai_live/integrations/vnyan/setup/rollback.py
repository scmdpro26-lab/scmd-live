import os
import logging
from ..config.backup import VNyanBackupManager
from ..bridge.installer import NodeGraphInstaller

logger = logging.getLogger("VNyanRollback")

class VNyanRollback:
    def __init__(self, backup_manager: VNyanBackupManager, installer: NodeGraphInstaller):
        self.backup_manager = backup_manager
        self.installer = installer

    def rollback(self) -> bool:
        """Thực hiện khôi phục hoàn toàn cấu hình VNyan từ bản sao lưu gần nhất."""
        logger.info("Bắt đầu quy trình Rollback cấu hình VNyan...")
        
        self.installer.rollback()
        
        success = self.backup_manager.restore_backup()
        if success:
            logger.info("Rollback cấu hình VNyan hoàn thành thành công.")
        else:
            logger.error("Rollback cấu hình VNyan thất bại.")
        return success
