import json

path = r"C:\Users\quanying_zhang\AppData\LocalLow\Suvidriel\VNyan\settings.json"
try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print("Keys in settings.json:", list(data.keys()))
    
    # Check if there is any key like "nodes" or "graphs" or "redeems" or similar
    for key, val in data.items():
        if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict) and "nodes" in val[0]:
            print(f"Found graphs list in key: {key}")
        if "asredeems" in key or "graph" in key.lower() or "redeem" in key.lower():
            print(f"Found key containing graph/redeem/asredeem: {key}")
            
    # Search for greeting and see what keys it appears in
    import re
    raw = json.dumps(data)
    matches = [m.start() for m in re.finditer("Greeting", raw)]
    print(f"Greeting matches count: {len(matches)}")
    for idx in matches[:5]:
        start = max(0, idx - 50)
        end = min(len(raw), idx + 100)
        print("MATCH CONTEXT:", raw[start:end])
except Exception as e:
    print("Error:", e)
