import logging
from ..models import VNyanHealth
from ..process import VNyanProcessManager
from .checks import VNyanHealthChecker
from .capabilities import VNyanCapabilities
from ..bridge.nodegraph import NodeGraphManager

logger = logging.getLogger("VNyanStatus")

class VNyanStatus:
    def __init__(
        self,
        process_manager: VNyanProcessManager,
        health_checker: VNyanHealthChecker,
        capabilities: VNyanCapabilities,
        nodegraph_manager: NodeGraphManager
    ):
        self.process_manager = process_manager
        self.health_checker = health_checker
        self.capabilities = capabilities
        self.nodegraph_manager = nodegraph_manager

    def get_health(self) -> VNyanHealth:
        """Kiểm định chi tiết và trả về đối tượng VNyanHealth đa chiều."""
        health = VNyanHealth()
        
        health.process = self.process_manager.is_running()
        
        if health.process:
            health.api = self.health_checker.is_api_online()
            health.vmc = self.health_checker.is_vmc_online()
            
        profile = self.capabilities.registry.current_profile
        if profile:
            health.avatar = True
            
            caps = self.capabilities.check_capabilities()
            health.viseme = caps.get("viseme", False)
            health.emotion = caps.get("emotion", False)
            health.blink = caps.get("blink", False)
            health.blendshape = True
            
        graph_info = self.nodegraph_manager.inspect()
        health.node_graph = graph_info.get("installed", False)
        health.event_bridge = health.api and health.node_graph
        
        return health
