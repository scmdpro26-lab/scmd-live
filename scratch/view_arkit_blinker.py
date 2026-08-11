import json

def main():
    path = "d:/SCMD_Tech/13.autolive/vnyan/Examples/ARKitAutoBlinker.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print("Nodes in ARKitAutoBlinker.json:")
    for node in data.get("nodes", []):
        print(f"  Path: {node.get('path')}, Values: {node.get('values')}")

if __name__ == "__main__":
    main()
