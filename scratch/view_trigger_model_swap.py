import json

def main():
    path = "d:/SCMD_Tech/13.autolive/vnyan/Examples/TriggerModelSwap.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print("Nodes in TriggerModelSwap.json:")
    for node in data.get("nodes", []):
        print(f"  Path: {node.get('path')}, Values: {node.get('values')}")

if __name__ == "__main__":
    main()
