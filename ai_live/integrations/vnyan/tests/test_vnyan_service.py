import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from ai_live.integrations.vnyan.service import VnyanService
from ai_live.integrations.vnyan.models import SetupResult, VNyanHealth

class TestVnyanService(unittest.TestCase):
    def setUp(self):
        self.service = VnyanService()

    def test_singleton(self):
        s2 = VnyanService()
        self.assertIs(self.service, s2)

    def test_validate_invalid_paths(self):
        # 1. Invalid exe path
        res = self.service.run_setup("invalid_path.exe", "avatar.vrm")
        self.assertFalse(res.success)
        self.assertEqual(res.status, "FAILED")
        self.assertIn("VNyan.exe không hợp lệ", res.errors[0])

        # 2. Valid exe but invalid avatar path
        def mock_exists(path_self):
            path_str = str(path_self).lower()
            if "vnyan.exe" in path_str:
                return True
            return False
            
        def mock_is_file(path_self):
            return True

        with patch.object(Path, "exists", autospec=True, side_effect=mock_exists):
            with patch.object(Path, "is_file", autospec=True, side_effect=mock_is_file):
                res = self.service.run_setup("C:/VNyan/vnyan.exe", "invalid_avatar.vrm")
                self.assertFalse(res.success)
                self.assertEqual(res.status, "FAILED")
                self.assertIn("Avatar VRM không hợp lệ", res.errors[0])

    def test_get_status_details(self):
        with patch.object(self.service, "check_connection") as mock_conn:
            # 1. Mock all pass
            h = VNyanHealth()
            h.process = True
            h.api = True
            h.vmc = True
            h.avatar = True
            h.blendshape = True
            h.viseme = True
            h.emotion = True
            h.blink = True
            h.event_bridge = True
            h.node_graph = True
            mock_conn.return_value = h
            
            mock_prof = MagicMock()
            mock_prof.source_path = Path("avatar.vrm")
            self.service.setup_manager.registry._current_profile = mock_prof
            
            details = self.service.get_status_details()
            
            self.assertTrue(details["process"][0])
            self.assertTrue(details["avatar"][0])
            self.assertTrue(details["vmc"][0])
            self.assertTrue(details["node_graph"][0])
            self.assertTrue(details["animation_mapping"][0])
            self.assertTrue(details["control"][0])

            # 2. Mock some fails
            h.api = False
            h.event_bridge = False
            h.blink = False
            mock_conn.return_value = h
            
            details = self.service.get_status_details()
            
            self.assertTrue(details["process"][0])
            self.assertFalse(details["animation_mapping"][0]) # blink is false
            self.assertFalse(details["control"][0]) # api and eb are false

    def test_run_setup_success_progress_callback(self):
        # We patch exists and is_file on Path to return True for paths related to vnyan
        original_exists = Path.exists
        original_is_file = Path.is_file
        
        def mock_exists(path_self):
            path_str = str(path_self).lower()
            if "vnyan.exe" in path_str or "avatar.vrm" in path_str:
                return True
            # For the manifest check in Step 14
            if "manifest.json" in path_str:
                return False
            return original_exists(path_self)
            
        def mock_is_file(path_self):
            path_str = str(path_self).lower()
            if "vnyan.exe" in path_str or "avatar.vrm" in path_str:
                return True
            return original_is_file(path_self)

        with patch.object(Path, "exists", autospec=True, side_effect=mock_exists):
            with patch.object(Path, "is_file", autospec=True, side_effect=mock_is_file):
                with patch.object(self.service.setup_manager.process_manager.discovery, "discover") as mock_disc:
                    inst_init = MagicMock()
                    inst_init.running = False
                    inst_init.executable_path = Path("C:/VNyan/vnyan.exe")
                    
                    inst_running = MagicMock()
                    inst_running.running = True
                    inst_running.executable_path = Path("C:/VNyan/vnyan.exe")
                    inst_running.api_port = 8069
                    inst_running.vmc_port = 39539
                    
                    mock_disc.side_effect = [inst_init, inst_running, inst_running]
                    
                    with patch.object(self.service.setup_manager.process_manager, "start") as mock_start:
                        with patch.object(self.service.setup_manager.health_checker, "is_api_online", return_value=True):
                            with patch.object(self.service.setup_manager.config_writer, "sync_network_settings", return_value=[]):
                                with patch.object(self.service.setup_manager.registry, "get_profile") as mock_get_profile:
                                    profile = MagicMock()
                                    profile.expressions.available = ["A", "I", "U", "happy"]
                                    mock_get_profile.return_value = profile
                                    
                                    with patch.object(self.service.setup_manager.nodegraph_manager, "inspect") as mock_inspect:
                                        mock_inspect.return_value = {
                                            "nodes_count": 20,
                                            "schema_valid": True,
                                            "node_exists": True,
                                            "installed": True
                                        }
                                        
                                        with patch.object(self.service.setup_manager.installer, "install_ai_live_bridge", return_value=True):
                                            with patch.object(self.service.setup_manager.vmc_transport, "connect", return_value=True):
                                                with patch.object(self.service.setup_manager.vmc_transport, "send_blendshape", return_value=True):
                                                    with patch.object(self.service.setup_manager.health_status, "get_health") as mock_h:
                                                        health = VNyanHealth(
                                                            process=True, api=True, vmc=True, avatar=True,
                                                            blendshape=True, viseme=True, emotion=True, blink=True,
                                                            event_bridge=True, node_graph=True
                                                        )
                                                        mock_h.return_value = health
                                                        
                                                        progress_calls = []
                                                        def progress_cb(step, desc, status, detail=""):
                                                            progress_calls.append((step, status))
                                                            
                                                        res = self.service.run_setup("C:/VNyan/vnyan.exe", "avatar.vrm", on_progress=progress_cb)
                                                        
                                                        self.assertTrue(res.success)
                                                        self.assertEqual(res.status, "READY")
                                                        # Check that callbacks were triggered for steps 1 to 18
                                                        steps_called = [step for step, status in progress_calls if status == "PASS"]
                                                        self.assertIn(1, steps_called)
                                                        self.assertIn(18, steps_called)

    def test_run_setup_failure_and_rollback(self):
        # We patch exists and is_file on Path to return True for paths related to vnyan
        original_exists = Path.exists
        original_is_file = Path.is_file
        
        def mock_exists(path_self):
            path_str = str(path_self).lower()
            if "vnyan.exe" in path_str or "avatar.vrm" in path_str:
                return True
            return original_exists(path_self)
            
        def mock_is_file(path_self):
            path_str = str(path_self).lower()
            if "vnyan.exe" in path_str or "avatar.vrm" in path_str:
                return True
            return original_is_file(path_self)

        with patch.object(Path, "exists", autospec=True, side_effect=mock_exists):
            with patch.object(Path, "is_file", autospec=True, side_effect=mock_is_file):
                with patch.object(self.service.setup_manager.process_manager.discovery, "discover") as mock_disc:
                    inst = MagicMock()
                    inst.running = False
                    inst.executable_path = Path("C:/VNyan/vnyan.exe")
                    mock_disc.return_value = inst
                    
                    # Mock start throwing error
                    with patch.object(self.service.setup_manager.process_manager, "start", side_effect=RuntimeError("Port conflict")):
                        with patch.object(self.service.setup_manager.rollback_manager, "rollback") as mock_rollback:
                            with patch.object(self.service.setup_manager.installer, "install_ai_live_bridge", return_value=True):
                                res = self.service.run_setup("C:/VNyan/vnyan.exe", "avatar.vrm")
                                self.assertFalse(res.success)
                                self.assertEqual(res.status, "FAILED")
                                mock_rollback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
