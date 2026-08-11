import json

def main():
    path = "C:/Users/quanying_zhang/AppData/LocalLow/Suvidriel/VNyan/asredeems1.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    print("=== Nodes in Graph ===")
    for node in data.get("nodes", []):
        print(f"Node ID: {node['id']}")
        print(f"  Path: {node['path']}")
        print(f"  Pos: ({node['posX']}, {node['posY']})")
        print(f"  Values: {node['values']}")
        print(f"  Inputs: {node.get('inputSocketIds', [])}")
        print(f"  Outputs: {node.get('outputSocketIds', [])}")
        
    print("\n=== Connections ===")
    for conn in data.get("connections", []):
        print(f"Connection ID: {conn['id']}")
        print(f"  Output Socket: {conn['outputSocketId']}")
        print(f"  Input Socket: {conn['inputSocketId']}")

if __name__ == "__main__":
    main()
