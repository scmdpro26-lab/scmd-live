import unittest
from unittest.mock import MagicMock, patch
from ai_live.integrations.vnyan.bridge.events import VNyanEventBridge
from ai_live.integrations.vnyan.transport.http import HTTPTransport

class TestEventBridge(unittest.TestCase):
    def test_event_bridge(self):
        mock_transport = MagicMock()
        bridge = VNyanEventBridge(mock_transport)
        
        bridge.send("Greeting", {"text1": "Chao"})
        mock_transport.send_post.assert_called_with("Greeting", {"text1": "Chao"})
