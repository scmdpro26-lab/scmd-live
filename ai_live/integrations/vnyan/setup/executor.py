import logging
from pathlib import Path
from ..models import AvatarProfile
from ..process import VNyanProcessManager
from ..config.backup import VNyanBackupManager
from ..config.writer import VNyanConfigWriter
from ..avatar.registry import AvatarRegistry
from ..bridge.installer import NodeGraphInstaller
from ..transport.vmc import VMCTransport
from ..health.status import VNyanStatus

logger = logging.getLogger("VNyanExecutor")

class VNyanExecutor:
    def __init__(
        self,
        process_manager: VNyanProcessManager,
        backup_manager: VNyanBackupManager,
        config_writer: VNyanConfigWriter,
        registry: AvatarRegistry,
        installer: NodeGraphInstaller,
        vmc_transport: VMCTransport,
        health_status: VNyanStatus
    ):
        self.process_manager = process_manager
        self.backup_manager = backup_manager
        self.config_writer = config_writer
        self.registry = registry
        self.installer = installer
        self.vmc_transport = vmc_transport
        self.health_status = health_status

    def execute_setup(self, avatar_path: Path, vmc_port: int, rest_port: int, ws_port: int, changes: list[str]) -> bool:
        """Thực thi các bước cấu hình và cài đặt."""
        self.backup_manager.create_backup()
        
        synced_changes = self.config_writer.sync_network_settings(vmc_port, rest_port, ws_port)
        changes.extend(synced_changes)
        
        profile = self.registry.get_profile(avatar_path)
        
        self.installer.install_ai_live_bridge()
        
        self.process_manager.start()
        
        self.vmc_transport.connect()
        
        return True
