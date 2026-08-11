import json
import os

def main():
    path = "C:/Users/quanying_zhang/AppData/LocalLow/Suvidriel/VNyan/settings.json.bak_autolive"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print("Type in backup settings.json:")
        for k in ["VMCPort", "OSCPort", "WebSocketPort"]:
            if k in data:
                print(f"  {k}: {data[k]} (type: {type(data[k])})")
    else:
        print("Backup settings.json not found!")

if __name__ == "__main__":
    main()
