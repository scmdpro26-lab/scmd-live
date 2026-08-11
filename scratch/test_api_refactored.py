import sys
import os
import time
import urllib.request
import json
import subprocess

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_live.integrations.vnyan import VnyanSetupManager
from src.config import Config

def send_payload(action, payload_dict):
    url = f"http://127.0.0.1:{Config.REST_PORT}/"
    payload = {
        "action": action,
        "payload": payload_dict
    }
    req_body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=1.0) as response:
            print(f"Sent {action}. Response status: {response.status}, Body: {response.read().decode('utf-8')}")
            return True
    except Exception as e:
        print(f"Error sending {action}: {e}")
        return False

def main():
    print("=== START API REFACTORED TEST ===")
    
    # 1. Initialize Setup Manager to write redeems.json with APIMessageNode
    print("1. Running setup to ensure graph uses APIMessageNode...")
    manager = VnyanSetupManager()
    
    # Kill running VNyan process first to write config cleanly
    manager.process_manager.stop()
    time.sleep(2.0)
    
    # Run setup
    from pathlib import Path
    result = manager.setup(Path(Config.AVATAR_VRM_PATH))
    print(f"Setup result: success={result.success}, status={result.status}, warnings={result.warnings}")
    
    # Start VNyan
    print("2. Starting VNyan.exe...")
    manager.process_manager.start()
    
    print("3. Waiting 10 seconds for VNyan to initialize and load the avatar...")
    time.sleep(10.0)
    
    # Send string-only payload
    print("\n4. Sending 'AI_LIVE_GREETING' with flat string-only payload...")
    # NOTE: "text1" is a string, and we DO NOT include "args": [] which was a list!
    send_payload("AI_LIVE_GREETING", {"text1": "Hello"})
    
    print("\n5. Waiting 3 seconds...")
    time.sleep(3.0)
    
    print("\n6. Sending 'AI_LIVE_CLAP' with flat string-only payload...")
    send_payload("AI_LIVE_CLAP", {"text1": "Clap"})
    
    print("\nDone. Please check if the avatar waved and clapped on the screen!")

if __name__ == "__main__":
    main()
