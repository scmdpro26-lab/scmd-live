import json
import os
import uuid

def patch_graph(path):
    print(f"Patching VNyan graph file: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    nodes = data.get("nodes", [])
    connections = data.get("connections", [])
    
    # 6 actions we want to ensure
    actions = [
        {"name": "Greeting", "path": "/VMC/Ext/Action/Greeting", "default_anim": "Sit on Ground (BasicMotions)", "y": 200},
        {"name": "Clap", "path": "/VMC/Ext/Action/Clap", "default_anim": "", "y": 50},
        {"name": "Heart", "path": "/VMC/Ext/Action/Heart", "default_anim": "", "y": -100},
        {"name": "PointUp", "path": "/VMC/Ext/Action/PointUp", "default_anim": "", "y": -250},
        {"name": "Dance", "path": "/VMC/Ext/Action/Dance", "default_anim": "", "y": -400},
        {"name": "Apology", "path": "/VMC/Ext/Action/Apology", "default_anim": "", "y": -550}
    ]
    
    updated = False
    
    for action in actions:
        # Check if TriggerNode for this path already exists
        exists = False
        for node in nodes:
            if node.get("path") == "Nodes/TriggerNode":
                for val in node.get("values", []):
                    if val.get("key") == "triggerName" and val.get("value") == action["path"]:
                        exists = True
                        break
            if exists:
                break
                
        if exists:
            print(f"  Action '{action['name']}' already exists in graph.")
            continue
            
        print(f"  Adding action '{action['name']}' to graph...")
        # Create TriggerNode
        trigger_id = str(uuid.uuid4())
        output_socket_id = str(uuid.uuid4())
        
        trigger_node = {
            "id": trigger_id,
            "values": [
                {"key": "triggerName", "value": action["path"]}
            ],
            "posX": -300.0,
            "posY": action["y"],
            "path": "Nodes/TriggerNode",
            "ownerBlockId": "",
            "inputSocketIds": [],
            "outputSocketIds": [output_socket_id],
            "headerColor": 0,
            "inputValueSocketIds": [],
            "outputValueSocketIds": []
        }
        
        # Create PlayAnimNode
        play_id = str(uuid.uuid4())
        input_socket_id = str(uuid.uuid4())
        
        play_node = {
            "id": play_id,
            "values": [
                {"key": "name", "value": action["default_anim"]},
                {"key": "leapOverride", "value": "1"},
                {"key": "blendHead", "value": "1"},
                {"key": "blendNeck", "value": "1"},
                {"key": "blendSpine", "value": "1"},
                {"key": "blendHipRot", "value": "1"},
                {"key": "blendHipPos", "value": "1"},
                {"key": "blendRoot", "value": "1"},
                {"key": "blendLeftLeg", "value": "1"},
                {"key": "blendRightLeg", "value": "1"},
                {"key": "blendRightArm", "value": "1"},
                {"key": "blendRightHand", "value": "1"},
                {"key": "blendRightFingers", "value": "1"},
                {"key": "blendLeftArm", "value": "1"},
                {"key": "blendLeftHand", "value": "1"},
                {"key": "blendLeftFingers", "value": "1"},
                {"key": "seconds", "value": ""},
                {"key": "eyes", "value": "0"},
                {"key": "teffects", "value": "1"}
            ],
            "posX": 100.0,
            "posY": action["y"],
            "path": "Nodes/PlayAnimNode",
            "ownerBlockId": "",
            "inputSocketIds": [input_socket_id],
            "outputSocketIds": [],
            "headerColor": 0,
            "inputValueSocketIds": [],
            "outputValueSocketIds": []
        }
        
        # Create Connection
        conn_id = str(uuid.uuid4())
        connection = {
            "id": conn_id,
            "outputSocketId": output_socket_id,
            "inputSocketId": input_socket_id
        }
        
        nodes.append(trigger_node)
        nodes.append(play_node)
        connections.append(connection)
        updated = True
        
    if updated:
        data["nodes"] = nodes
        data["connections"] = connections
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        print("  Successfully saved graph updates!")
    else:
        print("  No updates needed for this graph.")

def main():
    dir_path = "C:/Users/quanying_zhang/AppData/LocalLow/Suvidriel/VNyan"
    for file in os.listdir(dir_path):
        if file.startswith("asredeems") and file.endswith(".json"):
            path = os.path.join(dir_path, file)
            # Only patch active or non-empty graphs
            try:
                patch_graph(path)
            except Exception as e:
                print(f"Error patching {file}: {e}")

if __name__ == "__main__":
    main()
