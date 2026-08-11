import json
from pathlib import Path

settings_path = Path("C:/Users/quanying_zhang/AppData/LocalLow/Suvidriel/VNyan/settings.json")
if not settings_path.exists():
    print("settings.json không tồn tại")
    exit(1)

with open(settings_path, "r", encoding="utf-8") as f:
    data = json.load(f)

def search(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            search(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            search(item, f"{path}[{idx}]")
    elif isinstance(obj, str):
        if ".vrm" in obj.lower() or "/" in obj or "\\" in obj:
            print(f"{path}: {obj}")

search(data)
print("Hoàn tất tìm kiếm.")
