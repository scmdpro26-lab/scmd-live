import os
import json

def main():
    print("Searching for Trigger or Animation paths in vnyan/Examples...")
    for root, dirs, files in os.walk("d:/SCMD_Tech/13.autolive/vnyan/Examples"):
        for file in files:
            if file.endswith(".json"):
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for node in data.get("nodes", []):
                        nodepath = node.get("path", "")
                        if "trigger" in nodepath.lower() or "animation" in nodepath.lower():
                            print(f"  File: {file} -> Node Path: {nodepath}")
                except Exception as e:
                    pass

if __name__ == "__main__":
    main()
