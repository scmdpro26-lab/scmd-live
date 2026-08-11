import json

def main():
    path = "C:/Users/quanying_zhang/AppData/LocalLow/Suvidriel/VNyan/settings.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    print("Top-level keys in settings.json:")
    for k in data.keys():
        if "graph" in k.lower() or "node" in k.lower():
            val = data[k]
            if isinstance(val, list):
                print(f"  {k}: list of length {len(val)}")
            elif isinstance(val, dict):
                print(f"  {k}: dict with keys {list(val.keys())}")
            else:
                print(f"  {k}: {val}")

if __name__ == "__main__":
    main()
