import json
import os

def main():
    path = "C:/Users/quanying_zhang/AppData/LocalLow/Suvidriel/VNyan/settings.json"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            print("OSCPort (VNyan OSC Receive Port):", data.get("OSCPort"))
            print("VMCSenderPort (Feedback Port):", data.get("VMCSenderPort"))
            print("VMCSenderActive:", data.get("VMCSenderActive"))
            print("VMCPort (VMC Receive Port in VNyan):", data.get("VMCPort"))
    else:
        print("Settings file not found!")

if __name__ == "__main__":
    main()
