import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from ai_live.integrations.vnyan.detector import VNyanDetector
from ai_live.integrations.vnyan.discovery import VNyanDiscovery
from ai_live.integrations.vnyan.process import VNyanProcessManager

class TestVNyanDetectorAndProcess(unittest.TestCase):
    def setUp(self):
        self.detector = VNyanDetector()
        self.discovery = VNyanDiscovery(self.detector)
        self.process = VNyanProcessManager(self.discovery)

    def test_detect_vnyan(self):
        with patch.object(VNyanDetector, "detect_vnyan_exe", return_value=Path("C:/Program Files/VNyan/VNyan.exe")):
            exe = self.detector.detect_vnyan_exe()
            self.assertIsNotNone(exe)
            self.assertEqual(exe.name, "VNyan.exe")

    def test_start_vnyan(self):
        with patch.object(VNyanDiscovery, "discover") as mock_disc:
            mock_disc.return_value.running = True
            mock_disc.return_value.executable_path = Path("C:/Program Files/VNyan/VNyan.exe")
            instance = self.process.start()
            self.assertTrue(instance.running)
