import os
import json

def main():
    print("Searching for Param/Change/Listener nodes in examples...")
    for root, dirs, files in os.walk("d:/SCMD_Tech/13.autolive/vnyan/Examples"):
        for file in files:
            if file.endswith(".json"):
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for node in data.get("nodes", []):
                        nodepath = node.get("path", "")
                        if "param" in nodepath.lower() or "change" in nodepath.lower() or "list" in nodepath.lower() or "listen" in nodepath.lower():
                            print(f"  {file} -> {nodepath} -> {node.get('values')}")
                except Exception:
                    pass

if __name__ == "__main__":
    main()
