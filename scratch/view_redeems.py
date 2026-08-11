import json
import os

def main():
    dir_path = "C:/Users/quanying_zhang/AppData/LocalLow/Suvidriel/VNyan"
    for name in ["asredeems.json", "asredeems1.json", "redeems.json", "redeems1.json"]:
        path = os.path.join(dir_path, name)
        if os.path.exists(path):
            print(f"\n--- {name} ({os.path.getsize(path)} bytes) ---")
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    print("Keys:", list(data.keys()))
                    # print snippet
                    print(json.dumps(data, indent=2)[:500])
                else:
                    print("Type:", type(data))
                    print(str(data)[:500])
            except Exception as e:
                print(f"Error reading {name}: {e}")

if __name__ == "__main__":
    main()
