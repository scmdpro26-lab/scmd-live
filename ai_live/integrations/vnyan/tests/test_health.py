import unittest
from unittest.mock import MagicMock, patch
from ai_live.integrations.vnyan.health.status import VNyanStatus
from ai_live.integrations.vnyan.models import VNyanHealth

class TestVNyanHealth(unittest.TestCase):
    def test_health_process(self):
        mock_proc = MagicMock()
        mock_proc.is_running.return_value = True
        
        mock_check = MagicMock()
        mock_check.is_api_online.return_value = True
        mock_check.is_vmc_online.return_value = True
        
        mock_caps = MagicMock()
        mock_caps.registry.current_profile = MagicMock()
        mock_caps.check_capabilities.return_value = {"viseme": True, "emotion": True, "blink": True}
        
        mock_graph = MagicMock()
        mock_graph.inspect.return_value = {
            "node_exists": True,
            "schema_valid": True,
            "bridge_loaded": True,
            "event_accepted": True,
            "installed": True
        }
        
        status = VNyanStatus(mock_proc, mock_check, mock_caps, mock_graph)
        h = status.get_health()
        
        self.assertTrue(h.process)
        self.assertTrue(h.api)
        self.assertTrue(h.vmc)
        self.assertTrue(h.avatar)
        self.assertTrue(h.node_graph)
        self.assertTrue(h.ready)
