import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from ai_live.integrations.vnyan.setup.manager import VnyanSetupManager
from ai_live.integrations.vnyan.models import SetupResult, VNyanHealth

class TestSetupManager(unittest.TestCase):
    def setUp(self):
        self.manager = VnyanSetupManager()

    def test_setup_success(self):
        with patch.object(self.manager.planner, "plan_changes", return_value=["Thay đổi cổng"]):
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
                            self.assertTrue(res.health.ready)

    def test_setup_failure_and_rollback(self):
        with patch.object(self.manager.executor, "execute_setup", side_effect=Exception("Lỗi ghi đĩa")):
            with patch.object(self.manager.rollback_manager, "rollback", return_value=True) as mock_rb:
                res = self.manager.setup(Path("avatar.vrm"))
                self.assertFalse(res.success)
                self.assertEqual(res.status, "FAILED")
                mock_rb.assert_called_once()

    def test_rollback_sha256_verification(self):
        # Kiểm thử mã băm SHA256 trước và sau rollback
        backup_mgr = self.manager.backup_manager
        with patch.object(backup_mgr.detector, "get_config_dir", return_value=Path("scratch/mock_config")):
            config_dir = Path("scratch/mock_config")
            config_dir.mkdir(parents=True, exist_ok=True)
            settings_file = config_dir / "settings.json"
            
            # Content trước sửa đổi
            content_before = '{"RESTPort": 8069, "VMCPort": 39539}'
            with open(settings_file, "w", encoding="utf-8") as f:
                f.write(content_before)
                
            hash_before = backup_mgr._get_file_hash(settings_file)
            
            # Tạo backup
            backup_dir = backup_mgr.create_backup()
            self.assertTrue(Path(backup_dir).exists())
            
            # Sửa đổi file
            with open(settings_file, "w", encoding="utf-8") as f:
                f.write('{"RESTPort": 9999, "VMCPort": 8888}')
                
            hash_modified = backup_mgr._get_file_hash(settings_file)
            self.assertNotEqual(hash_before, hash_modified)
            
            # Khôi phục rollback
            success = backup_mgr.restore_backup(backup_dir)
            self.assertTrue(success)
            
            # Kiểm chứng SHA256(before) == SHA256(after rollback)
            hash_after = backup_mgr._get_file_hash(settings_file)
            self.assertEqual(hash_before, hash_after)
