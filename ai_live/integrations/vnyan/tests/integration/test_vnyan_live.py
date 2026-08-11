import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from ai_live.integrations.vnyan.setup.manager import VnyanSetupManager

class TestVNyanLiveIntegration(unittest.TestCase):
    def setUp(self):
        self.manager = VnyanSetupManager()

    def test_live_vnyan_process_detection(self):
        inst = self.manager.discovery.discover()
        self.assertIsNotNone(inst)
        print(f"[Integration] VNyan run status: {inst.running}")

    def test_setup_orchestration_mocked(self):
        with patch.object(self.manager.planner, "plan_changes", return_value=["Mock change"]):
            with patch.object(self.manager.executor, "execute_setup", return_value=True):
                with patch.object(self.manager.health_status, "get_health") as mock_h:
                    mock_h.return_value.process = True
                    mock_h.return_value.api = True
                    mock_h.return_value.vmc = True
                    mock_h.return_value.avatar = True
                    mock_h.return_value.blendshape = True
                    mock_h.return_value.viseme = True
                    mock_h.return_value.emotion = True
                    mock_h.return_value.blink = True
                    mock_h.return_value.event_bridge = True
                    mock_h.return_value.node_graph = True
                    
                    with patch.object(self.manager.expression, "set_expression", return_value=True):
                        with patch.object(self.manager.blink, "blink", return_value=True):
                            res = self.manager.setup(Path("avatar.vrm"))
                            self.assertTrue(res.success)
                            self.assertEqual(res.status, "READY")
