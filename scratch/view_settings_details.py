import json

def main():
    path = "C:/Users/quanying_zhang/AppData/LocalLow/Suvidriel/VNyan/settings.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    print("Largest keys in settings.json:")
    sizes = []
    for k, v in data.items():
        size = len(json.dumps(v))
        sizes.append((k, size))
    
    sizes.sort(key=lambda x: x[1], reverse=True)
    for k, size in sizes[:15]:
        print(f"  {k}: {size} bytes")

if __name__ == "__main__":
    main()
