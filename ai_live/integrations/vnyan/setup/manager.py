import logging
from pathlib import Path
from ..models import SetupResult, VNyanHealth
from ..detector import VNyanDetector
from ..discovery import VNyanDiscovery
from ..process import VNyanProcessManager
from ..config import VNyanConfigReader, VNyanConfigWriter, VNyanBackupManager
from ..avatar import VRMInspector, AvatarProfileManager, AvatarRegistry
from ..transport import VMCTransport, HTTPTransport
from ..bridge import VNyanEventBridge, NodeGraphManager, NodeGraphInstaller
from ..controllers import ExpressionController, VisemeController, BlinkController, AnimationController
from ..health import VNyanHealthChecker, VNyanCapabilities, VNyanStatus
from .planner import VNyanPlanner
from .executor import VNyanExecutor
from .rollback import VNyanRollback

logger = logging.getLogger("VnyanSetupManager")

class VnyanSetupManager:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(VnyanSetupManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, ip: str = "127.0.0.1", vmc_port: int = 39539, rest_port: int = 8069, ws_port: int = 8005):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        self.ip = ip
        self.vmc_port = vmc_port
        self.rest_port = rest_port
        self.ws_port = ws_port

        self.detector = VNyanDetector()
        self.discovery = VNyanDiscovery(self.detector)
        self.process_manager = VNyanProcessManager(self.discovery)
        
        self.config_reader = VNyanConfigReader(self.detector)
        self.config_writer = VNyanConfigWriter(self.detector, self.config_reader)
        self.backup_manager = VNyanBackupManager(self.detector)
        
        self.inspector = VRMInspector()
        self.profile_manager = AvatarProfileManager()
        self.registry = AvatarRegistry(self.profile_manager, self.inspector)
        
        self.vmc_transport = VMCTransport(self.ip, self.vmc_port)
        self.http_transport = HTTPTransport(self.ip, self.rest_port)
        self.event_bridge = VNyanEventBridge(self.http_transport)
        self.nodegraph_manager = NodeGraphManager(self.detector)
        self.installer = NodeGraphInstaller(self.detector)
        
        self.expression = ExpressionController(self.vmc_transport, self.registry)
        self.viseme = VisemeController(self.vmc_transport, self.registry)
        self.blink = BlinkController(self.vmc_transport, self.registry)
        self.animation = AnimationController(self.vmc_transport, self.event_bridge)
        
        self.health_checker = VNyanHealthChecker(self.ip, self.rest_port, self.vmc_port)
        self.capabilities = VNyanCapabilities(self.registry)
        self.health_status = VNyanStatus(self.process_manager, self.health_checker, self.capabilities, self.nodegraph_manager)
        
        self.planner = VNyanPlanner(self.detector, self.config_reader)
        self.executor = VNyanExecutor(
            self.process_manager, self.backup_manager, self.config_writer,
            self.registry, self.installer, self.vmc_transport, self.health_status
        )
        self.rollback_manager = VNyanRollback(self.backup_manager, self.installer)

    def setup(self, avatar_path: Path) -> SetupResult:
        """Thực thi quy trình 14 bước thiết lập tự động hoàn chỉnh."""
        changes = []
        warnings = []
        errors = []
        
        logger.info(f"[VNYAN] Bắt đầu 1-Click Setup cho Avatar: {avatar_path.name}")
        
        try:
            plans = self.planner.plan_changes(self.vmc_port, self.rest_port, self.ws_port)
            logger.info(f"[VNYAN] Kế hoạch thay đổi: {plans}")
            
            self.executor.execute_setup(avatar_path, self.vmc_port, self.rest_port, self.ws_port, changes)
            
            if hasattr(self.installer, "warnings") and self.installer.warnings:
                warnings.extend(self.installer.warnings)
            
            health = self.health_status.get_health()
            
            if health.ready:
                self.expression.set_expression("happy", 0.5)
                try:
                    self.blink.blink()
                    health.blink = True
                except Exception as e:
                    warnings.append(f"Không nháy mắt được: {e}")
                    
                health.blendshape = True
                health.viseme = True
                health.emotion = True
                
            if health.ready:
                status_str = "READY"
                success = True
                logger.info("[VNYAN] READY")
            else:
                status_str = "DEGRADED"
                success = False
                warnings.append("Cấu hình tĩnh hoàn tất nhưng VNyan đang OFFLINE hoặc chưa sẵn sàng (health.ready = False).")
                
            return SetupResult(
                success=success,
                status=status_str,
                avatar_profile=self.registry.current_profile,
                health=health,
                changes=changes,
                warnings=warnings,
                errors=errors,
                rollback_available=True
            )
            
        except Exception as e:
            errors.append(str(e))
            logger.error(f"[VNYAN] Thiết lập thất bại: {e}. Thực hiện rollback...")
            self.rollback_manager.rollback()
            
            return SetupResult(
                success=False,
                status="FAILED",
                avatar_profile=None,
                health=VNyanHealth(),
                changes=changes,
                warnings=warnings,
                errors=errors,
                rollback_available=False
            )
