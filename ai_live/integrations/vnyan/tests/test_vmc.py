import unittest
from unittest.mock import MagicMock, patch
from ai_live.integrations.vnyan.transport.vmc import VMCTransport

class TestVMCTransport(unittest.TestCase):
    def test_vmc_send_blendshape(self):
        transport = VMCTransport("127.0.0.1", 39539)
        mock_client = MagicMock()
        transport.client = mock_client
        
        transport.send_blendshape("Joy", 1.0)
        mock_client.send_message.assert_any_call("/VMC/Ext/Blend/Val", ["Joy", 1.0])
        mock_client.send_message.assert_any_call("/VMC/Ext/Blend/Apply", [])

    def test_vmc_batch(self):
        transport = VMCTransport("127.0.0.1", 39539)
        mock_client = MagicMock()
        transport.client = mock_client
        
        transport.send_blendshape_batch({"Joy": 1.0, "Blink": 0.5})
        mock_client.send_message.assert_any_call("/VMC/Ext/Blend/Val", ["Joy", 1.0])
        mock_client.send_message.assert_any_call("/VMC/Ext/Blend/Val", ["Blink", 0.5])
        mock_client.send_message.assert_any_call("/VMC/Ext/Blend/Apply", [])
