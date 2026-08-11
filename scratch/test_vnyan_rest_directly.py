import urllib.request
import json
import sys

def test_greeting():
    url = "http://127.0.0.1:8069/"
    payload = {
        "action": "AI_LIVE_GREETING",
        "payload": {
            "text1": "Testing direct REST greeting"
        }
    }
    
    req_body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    print("Sending POST request to:", url)
    print("Payload:", json.dumps(payload, indent=2))
    
    try:
        with urllib.request.urlopen(req, timeout=3.0) as response:
            print("Response Status:", response.status)
            print("Response Headers:", dict(response.headers))
            body = response.read().decode("utf-8")
            print("Response Body:", body)
    except Exception as e:
        print("Error during request:", e)

if __name__ == "__main__":
    test_greeting()
