import sys
import os
import urllib.request
import json
import asyncio
from unittest.mock import MagicMock, patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.vmc_client import VMCClient

async def main():
    print("=== START CLAP FLOW VERIFICATION ===")
    vmc = VMCClient()
    
    # 1. Mock VMC transport's send_trigger to check if it gets called
    # self.service.setup_manager.vmc_transport
    vmc.manager.vmc_transport.send_trigger = MagicMock(return_value=True)
    
    # 2. Mock HTTP urlopen to capture REST requests
    sent_requests = []
    def mock_urlopen(req, timeout=None):
        url = req.full_url
        data = req.data
        method = req.get_method()
        payload = json.loads(data.decode("utf-8"))
        sent_requests.append((url, method, payload))
        print(f"[Mock REST] Request: {method} {url} -> {payload}")
        
        response = MagicMock()
        response.__enter__.return_value.status = 200
        return response
        
    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        print("\nTriggering Clap...")
        vmc.trigger_clap()
        
        # Wait for async HTTP thread
        await asyncio.sleep(0.5)
        
    # Check results
    print("\n--- RESULTS ---")
    vmc_called = vmc.manager.vmc_transport.send_trigger.called
    print(f"VMC send_trigger called: {vmc_called}")
    if vmc_called:
        print(f"VMC send_trigger args: {vmc.manager.vmc_transport.send_trigger.call_args}")
    print(f"REST requests sent: {sent_requests}")
    
    assert vmc_called, "VMC trigger should be called for Clap!"
    assert len(sent_requests) == 1, "Exactly 1 REST request should be sent as fallback!"
    
    vmc_args = vmc.manager.vmc_transport.send_trigger.call_args[0]
    assert vmc_args[0] == "AI_LIVE_CLAP", f"VMC Action should be 'AI_LIVE_CLAP', got '{vmc_args[0]}'"
    
    req_payload = sent_requests[0][2]
    assert req_payload["action"] == "AI_LIVE_CLAP", f"REST Action should be 'AI_LIVE_CLAP', got '{req_payload['action']}'"
    
    print("\nSUCCESS: Clap flow operates perfectly under the new VMC UDP trigger architecture!")
    sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
