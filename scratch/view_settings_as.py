import json
import os

def main():
    path = "C:/Users/quanying_zhang/AppData/LocalLow/Suvidriel/VNyan/settings.json_as.json"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print("Keys in settings.json_as.json:")
        print(list(data.keys()))
        if "graphs" in data:
            print("FOUND 'graphs' key!")
            print(f"Graphs type: {type(data['graphs'])}")
            if isinstance(data['graphs'], list):
                print(f"Number of graphs: {len(data['graphs'])}")
                for i, g in enumerate(data['graphs']):
                    print(f"  Graph {i}: name='{g.get('name')}', nodes count={len(g.get('nodes', []))}, connections count={len(g.get('connections', []))}")
    else:
        print("settings.json_as.json not found!")

if __name__ == "__main__":
    main()
