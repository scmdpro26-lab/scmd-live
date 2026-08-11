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

def send_post(payload):
    url = "http://127.0.0.1:8069/"
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

def test_payload(name, payload):
    global bone_positions
    print(f"\n--- Testing payload: {name} ---")
    print("Payload data:", json.dumps(payload))
    
    # 1. Clear bones and measure baseline for 1.5s
    with bone_lock:
        bone_positions.clear()
    time.sleep(1.5)
    with bone_lock:
        baseline_samples = list(bone_positions)
        bone_positions.clear()
    baseline_var = calculate_variance(baseline_samples)
    print(f"Baseline samples: {len(baseline_samples)}, Var: {baseline_var:.8f}")
    
    # 2. Send payload
    status, body = send_post(payload)
    print(f"Response: Status={status}, Body={body}")
    
    # 3. Measure active for 2.5s
    time.sleep(2.5)
    with bone_lock:
        active_samples = list(bone_positions)
    active_var = calculate_variance(active_samples)
    print(f"Active samples: {len(active_samples)}, Var: {active_var:.8f}")
    
    diff = active_var - baseline_var
    print(f"Difference: {diff:.8f}")
    if diff > 1e-4:
        print("=======> SUCCESS! THIS PAYLOAD WORKED! <=======")
        return True
    return False

def main():
    global running
    dispatcher = Dispatcher()
    dispatcher.map("/VMC/Ext/Bone/Pos", bone_handler)
    
    try:
        server = ThreadingOSCUDPServer(("0.0.0.0", 39540), dispatcher)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
    except Exception as e:
        print(f"Error starting VMC listener: {e}")
        return

    # Let listener warm up
    time.sleep(1.0)
    
    payloads = {
        "A (Current - action/payload)": {
            "action": "AI_LIVE_GREETING",
            "payload": {"text1": "hello"}
        },
        "B (Only action)": {
            "action": "AI_LIVE_GREETING"
        },
        "C (action/dict)": {
            "action": "AI_LIVE_GREETING",
            "dict": {"text1": "hello"}
        },
        "D (action/data)": {
            "action": "AI_LIVE_GREETING",
            "data": {"text1": "hello"}
        },
        "E (Only event)": {
            "event": "AI_LIVE_GREETING"
        },
        "F (event/data)": {
            "event": "AI_LIVE_GREETING",
            "data": {"text1": "hello"}
        },
        "G (Only trigger)": {
            "trigger": "AI_LIVE_GREETING"
        },
        "H (trigger/data)": {
            "trigger": "AI_LIVE_GREETING",
            "data": {"text1": "hello"}
        },
        "I (Only name)": {
            "name": "AI_LIVE_GREETING"
        },
        "J (action/dictionary)": {
            "action": "AI_LIVE_GREETING",
            "dictionary": {"text1": "hello"}
        }
    }
    
    success = False
    for name, p in payloads.items():
        if test_payload(name, p):
            success = True
            break
            
    running = False
    server.shutdown()
    server.server_close()
    
    if success:
        print("\nVerification finished: A matching payload format was found!")
    else:
        print("\nVerification finished: None of the payloads triggered movement.")

if __name__ == "__main__":
    main()
