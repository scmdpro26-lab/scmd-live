import json
import os

def main():
    path = "C:/Users/quanying_zhang/AppData/LocalLow/Suvidriel/VNyan/settings.json"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        print("Searching settings.json values for node keys...")
        # Since node graph might be in some nested structure, let's recursively search for dicts with key 'path'
        nodes_found = []
        
        def recurse(obj):
            if isinstance(obj, dict):
                if "path" in obj and ("Nodes/" in str(obj["path"]) or "Play" in str(obj["path"])):
                    nodes_found.append(obj)
                for k, v in obj.items():
                    recurse(v)
            elif isinstance(obj, list):
                for item in obj:
                    recurse(item)
                    
        recurse(data)
        print(f"Total nodes found: {len(nodes_found)}")
        for node in nodes_found[:20]:
            print(f"  Path: {node.get('path')}, Values: {node.get('values')}")
    else:
        print("settings.json not found!")

if __name__ == "__main__":
    main()
