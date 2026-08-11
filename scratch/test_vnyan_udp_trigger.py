import sys
import json
import time
import socket
import threading
from pathlib import Path
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

bone_positions = []
bone_lock = threading.Lock()
running = True

def bone_handler(address, *args):
    if not running:
        return
    if len(args) >= 4:
        bone_name = args[0]
        if bone_name in ["RightHand", "LeftHand", "RightArm", "LeftArm", "RightForeArm", "LeftForeArm"]:
            try:
                x, y, z = float(args[1]), float(args[2]), float(args[3])
                with bone_lock:
                    bone_positions.append((time.time(), bone_name, x, y, z))
            except Exception:
                pass

def calculate_variance(samples):
    if len(samples) < 2:
        return 0.0
    xs = [s[2] for s in samples]
    ys = [s[3] for s in samples]
    zs = [s[4] for s in samples]
    
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    mean_z = sum(zs) / len(zs)
    
    var_x = sum((x - mean_x) ** 2 for x in xs) / len(xs)
    var_y = sum((y - mean_y) ** 2 for y in ys) / len(ys)
    var_z = sum((z - mean_z) ** 2 for z in zs) / len(zs)
    
    return var_x + var_y + var_z

def modify_graph_for_udp():
    path = Path("C:/Users/quanying_zhang/AppData/LocalLow/Suvidriel/VNyan/redeems.json")
    if not path.exists():
        print("redeems.json not found")
        return False
        
    print("Modifying redeems.json to use TriggerNode (UDP)...")
    data = json.load(open(path, "r", encoding="utf-8"))
    nodes = data.get("nodes", [])
    
    modified = False
    for node in nodes:
        # Find the node for Greeting
        if node.get("path") == "Nodes/APIMessageNode" and any(val.get("value") == "AI_LIVE_GREETING" for val in node.get("values", [])):
            node["path"] = "Nodes/TriggerNode"
            node["values"] = [
                {"key": "triggerName", "value": "/VMC/Ext/Action/AI_LIVE_GREETING"}
            ]
            node["outputValueSocketIds"] = [] # TriggerNode has no value outputs
            modified = True
            print("Successfully converted APIMessageNode to TriggerNode for Greeting.")
            break
            
    if modified:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        return True
    else:
        print("AI_LIVE_GREETING APIMessageNode not found in redeems.json")
        return False

def main():
    global running, bone_positions
    
    # 1. Modify the graph
    if not modify_graph_for_udp():
        return
        
    # Since we modified the graph, we must restart VNyan to load the new redeems.json.
    # Let's check if VNyan is running. If so, let's kill it and start it again.
    import subprocess
    print("Restarting VNyan to apply graph changes...")
    subprocess.call("taskkill /F /IM VNyan.exe", shell=True)
    time.sleep(2.0)
    
    # Start VNyan
    vnyan_exe = r"D:\SCMD_Tech\13.autolive\vnyan\VNyan.exe"
    print(f"Starting VNyan: {vnyan_exe}")
    subprocess.Popen([vnyan_exe], cwd=str(Path(vnyan_exe).parent))
    print("Waiting 6 seconds for VNyan initialization...")
    time.sleep(6.0)

    # 2. Start VMC Feedback Listener
    print("Starting VMC feedback listener on port 39540...")
    dispatcher = Dispatcher()
    dispatcher.map("/VMC/Ext/Bone/Pos", bone_handler)
    
    try:
        server = ThreadingOSCUDPServer(("0.0.0.0", 39540), dispatcher)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
    except Exception as e:
        print(f"Error starting VMC listener: {e}")
        return

    time.sleep(1.0)
    
    # 3. Measure baseline
    print("Measuring baseline bone movements (2.0s)...")
    time.sleep(2.0)
    with bone_lock:
        baseline_samples = list(bone_positions)
        bone_positions.clear()
    baseline_var = calculate_variance(baseline_samples)
    print(f"Baseline samples: {len(baseline_samples)}, Var: {baseline_var:.8f}")

    # 4. Send UDP trigger to port 39539
    print("Sending VMC OSC trigger to port 39539...")
    client = SimpleUDPClient("127.0.0.1", 39539)
    client.send_message("/VMC/Ext/Action/AI_LIVE_GREETING", [])
    
    # 5. Measure active
    print("Measuring active bone movements (3.0s)...")
    time.sleep(3.0)
    with bone_lock:
        active_samples = list(bone_positions)
    active_var = calculate_variance(active_samples)
    print(f"Active samples: {len(active_samples)}, Var: {active_var:.8f}")
    
    diff = active_var - baseline_var
    print(f"Difference: {diff:.8f}")
    
    if diff > 1e-4:
        print("=======> SUCCESS! UDP TRIGGER WORKED! <=======")
    else:
        print("FAILED: UDP trigger did not cause bone movement.")
        
    running = False
    server.shutdown()
    server.server_close()

if __name__ == "__main__":
    main()
