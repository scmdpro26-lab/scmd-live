import urllib.request
import json
import sys

def send(action_name, payload_dict=None):
    if payload_dict is None:
        payload_dict = {}
    payload = {
        "action": action_name,
        "payload": payload_dict
    }
    req_body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:8069/",
        data=req_body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=1.0) as response:
            print(f"Status: {response.status}")
            print(f"Headers: {response.headers.as_string()}")
            print(f"Body: {response.read().decode('utf-8')}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("Testing sending 'AI_LIVE_GREETING' to REST API on port 8069...")
    send("AI_LIVE_GREETING")
    
    print("\nTesting sending 'ping' to REST API on port 8069...")
    send("ping")
