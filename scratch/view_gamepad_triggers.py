import json

def main():
    path = "d:/SCMD_Tech/13.autolive/vnyan/Examples/GamepadFingerTracking.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print("Trigger/CallTrigger nodes in GamepadFingerTracking.json:")
    for node in data.get("nodes", []):
        if "TriggerNode" in node.get("path", "") or "CallTriggerNode" in node.get("path", ""):
            print(f"  Path: {node.get('path')}, Values: {node.get('values')}")

if __name__ == "__main__":
    main()
