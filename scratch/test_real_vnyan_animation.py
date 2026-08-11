import sys
import json
import time
import socket
import threading
import urllib.request
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

bone_positions = []
bone_lock = threading.Lock()
running = True

def bone_handler(address, *args):
    if not running:
        return
    if len(args) >= 4:
        bone_name = args[0]
        # Track hand or arm bones
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

def send_rest_action(action_name, payload_dict=None):
    if payload_dict is None:
        payload_dict = {}
    url = "http://127.0.0.1:8069/"
    payload = {
        "action": action_name,
        "payload": payload_dict
    }
    req_body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=2.0) as response:
            return response.status, response.read().decode("utf-8")
    except Exception as e:
        return None, str(e)

def main():
    global running, bone_positions
    print("Starting VMC feedback listener on port 39540...")
    dispatcher = Dispatcher()
    dispatcher.map("/VMC/Ext/Bone/Pos", bone_handler)
    
    try:
        server = ThreadingOSCUDPServer(("0.0.0.0", 39540), dispatcher)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        print("VMC Listener is ACTIVE. Monitoring bone positions...")
    except Exception as e:
        print(f"Error starting VMC listener: {e}")
        return

    # 1. Measure baseline
    print("Measuring baseline bone movements (2.0s)...")
    time.sleep(2.0)
    with bone_lock:
        baseline_samples = list(bone_positions)
        bone_positions.clear()
        
    baseline_var = calculate_variance(baseline_samples)
    print(f"Baseline samples: {len(baseline_samples)}, Variance: {baseline_var:.8f}")

    # 2. Trigger animation
    print("Sending AI_LIVE_GREETING trigger via REST API...")
    status, body = send_rest_action("AI_LIVE_GREETING", {"text1": "Verify animation"})
    print(f"REST API Response Status: {status}, Body: {body}")

    # 3. Measure active
    print("Measuring bone movements during animation (3.0s)...")
    time.sleep(3.0)
    with bone_lock:
        active_samples = list(bone_positions)
    
    active_var = calculate_variance(active_samples)
    print(f"Active samples: {len(active_samples)}, Variance: {active_var:.8f}")
    
    diff = active_var - baseline_var
    print(f"Variance difference: {diff:.8f}")
    
    if diff > 1e-4:
        print("SUCCESS: Animation played (significant movement detected)!")
    else:
        print("FAILED: No significant animation movement detected.")

    running = False
    server.shutdown()
    server.server_close()

if __name__ == "__main__":
    main()
