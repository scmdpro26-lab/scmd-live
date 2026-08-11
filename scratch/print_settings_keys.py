import json

def main():
    path = "C:/Users/quanying_zhang/AppData/LocalLow/Suvidriel/VNyan/settings.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print("All top-level keys in settings.json:")
    print(list(data.keys()))

if __name__ == "__main__":
    main()
