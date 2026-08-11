import json

def main():
    path = "C:/Users/quanying_zhang/AppData/LocalLow/Suvidriel/VNyan/settings.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    print("Searching for VMC/OSC keys in settings.json:")
    for k, v in data.items():
        if "vmc" in k.lower() or "osc" in k.lower() or "port" in k.lower():
            print(f"  {k}: {v}")

if __name__ == "__main__":
    main()
