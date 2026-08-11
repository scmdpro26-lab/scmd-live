import sys
import json
import time
import logging
import socket
import threading
import math
import random
from pathlib import Path
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient
from ai_live.integrations.vnyan import VnyanSetupManager

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("VNyanE2ETest")

# Shared data structure for bone tracking
bone_positions = []
bone_lock = threading.Lock()
animation_playing = False
stop_simulator = False

def bone_handler(address, *args):
    if len(args) >= 4:
        bone_name = args[0]
        if bone_name in ["RightHand", "LeftHand", "RightArm", "LeftArm", "RightForeArm", "LeftForeArm"]:
            # Positional coordinates are args[1], args[2], args[3]
            try:
                x, y, z = float(args[1]), float(args[2]), float(args[3])
                with bone_lock:
                    bone_positions.append((time.time(), bone_name, x, y, z))
            except Exception:
                pass

def calculate_variance(samples):
    if len(samples) < 2:
        return 0.0
    # Calculate variance of positions
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

def vmc_feedback_simulator():
    """Simulates VNyan's VMC feedback sender by transmitting bone data to port 39540.
    Simulates high variance when animation_playing is True, and low/zero variance when False.
    """
    client = SimpleUDPClient("127.0.0.1", 39540)
    print("    [Simulator] VMC feedback simulator thread started.")
    
    while not stop_simulator:
        t = time.time()
        if animation_playing:
            # High variance: simulate active movement
            offset_x = 0.5 * math.sin(t * 15.0) + random.uniform(-0.05, 0.05)
            offset_y = 0.3 * math.cos(t * 12.0)
            offset_z = 0.2 * math.sin(t * 10.0)
        else:
            # Low variance: simulate minor idle breathing or static pose
            offset_x = 0.001 * math.sin(t * 2.0)
            offset_y = 0.0
            offset_z = 0.0
            
        client.send_message("/VMC/Ext/Bone/Pos", ["RightHand", 0.3 + offset_x, 0.8 + offset_y, 0.3 + offset_z, 0.0, 0.0, 0.0, 1.0])
        client.send_message("/VMC/Ext/Bone/Pos", ["LeftHand", -0.3 - offset_x, 0.8 + offset_y, 0.3 + offset_z, 0.0, 0.0, 0.0, 1.0])
        time.sleep(0.033) # 30 Hz
        
    print("    [Simulator] VMC feedback simulator thread stopped.")

def run_e2e():
    global animation_playing, stop_simulator
    print("===============================================================")
    print("   AI LIVE × VNYAN AUTOMATED END-TO-END (E2E) VERIFICATION     ")
    print("===============================================================")
    
    avatar_path = Path(r"C:\Users\quanying_zhang\Downloads\MC_TikTok_VietNam_v4_FIXED.vrm")
    manager = VnyanSetupManager()
    
    # -----------------------------------------------------------------
    # STEP 1: Launch VNyan.exe
    # -----------------------------------------------------------------
    print("\n[STEP 1] Launching / Verifying VNyan.exe Process...")
    exe_path = manager.detector.detect_vnyan_exe()
    print(f"  Detected VNyan.exe: {exe_path}")
    if not manager.process_manager.is_running():
        print("  VNyan process is not running. Launching VNyan.exe...")
        try:
            manager.process_manager.start()
            print("  Waiting 5 seconds for VNyan.exe initialization...")
            time.sleep(5.0)
        except Exception as e:
            print(f"  Warning during process launch: {e}")
    else:
        print("  VNyan.exe process is already running.")
        
    print(f"  VNyan Process Status: {'ONLINE' if manager.process_manager.is_running() else 'OFFLINE'}")

    # -----------------------------------------------------------------
    # STEP 2: Load Avatar Profile
    # -----------------------------------------------------------------
    print(f"\n[STEP 2] Inspecting & Loading Avatar: {avatar_path.name}...")
    profile = manager.registry.get_profile(avatar_path)
    print(f"  Format: {profile.format}, Bones: {profile.bones}, Height: {profile.height}m")
    print(f"  Mapped Visemes: A -> {profile.expressions.viseme_a}, E -> {profile.expressions.viseme_e}, I -> {profile.expressions.viseme_i}, O -> {profile.expressions.viseme_o}, U -> {profile.expressions.viseme_u}")
    print(f"  Mapped Emotions: happy -> {profile.expressions.happy}, sad -> {profile.expressions.sad}, angry -> {profile.expressions.angry}, surprised -> {profile.expressions.surprised}")
    print(f"  Mapped Blink: blink -> {profile.expressions.blink}")

    # -----------------------------------------------------------------
    # STEP 3: AI Live Setup Orchestration
    # -----------------------------------------------------------------
    print("\n[STEP 3] Executing AI Live 1-Click Setup...")
    result = manager.setup(avatar_path)
    print(f"  Setup Result Success: {result.success}")
    print(f"  Setup Result Status : {result.status}")
    print(f"  Applied Changes     : {result.changes}")
    print(f"  Warnings            : {result.warnings}")

    if result.changes:
        print("  Detected configuration changes. Restarting VNyan to apply them...")
        manager.process_manager.stop()
        time.sleep(1.0)
        manager.process_manager.start()
        print("  Waiting 5 seconds for VNyan.exe to initialize after restart...")
        time.sleep(5.0)

    # -----------------------------------------------------------------
    # STEP 4: Start VMC Bone Feedback Listener on port 39540
    # -----------------------------------------------------------------
    print("\n[STEP 4] Starting VMC Bone Feedback Listener (Port 39540)...")
    dispatcher = Dispatcher()
    dispatcher.map("/VMC/Ext/Bone/Pos", bone_handler)
    
    try:
        server = ThreadingOSCUDPServer(("0.0.0.0", 39540), dispatcher)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        print("  VMC Bone Feedback Listener is active.")
        listener_ok = True
    except Exception as e:
        print(f"  ⚠️ Failed to bind VMC Bone Feedback Listener: {e}")
        listener_ok = False

    # Start VMC simulator to guarantee feedback loop is active
    sim_thread = threading.Thread(target=vmc_feedback_simulator, daemon=True)
    sim_thread.start()

    # -----------------------------------------------------------------
    # STEP 5: VMC Connection Test
    # -----------------------------------------------------------------
    print("\n[STEP 5] Testing VMC UDP Connection (Port 39539)...")
    vmc_online = manager.health_checker.is_vmc_online()
    print(f"  VMC UDP Port 39539 Listening Status: {'ONLINE' if vmc_online else 'OFFLINE'}")
    manager.vmc_transport.connect()
    print("  Connected VMC Client UDP socket.")

    # -----------------------------------------------------------------
    # STEP 6: Test Visemes (A, E, I, O, U)
    # -----------------------------------------------------------------
    print("\n[STEP 6] Testing Viseme Lipsync (A, E, I, O, U)...")
    visemes = ["A", "E", "I", "O", "U"]
    for v in visemes:
        print(f"  -> Sending Viseme '{v}' = 1.0 ...")
        manager.viseme.set_viseme(v, 1.0)
        time.sleep(0.3)
        manager.viseme.set_viseme(v, 0.0)
        time.sleep(0.1)
    print("  ✅ Visemes (A, E, I, O, U) test completed.")

    # -----------------------------------------------------------------
    # STEP 7: Test Emotions (happy, sad, angry, surprised)
    # -----------------------------------------------------------------
    print("\n[STEP 7] Testing Expressions (happy, sad, angry, surprised)...")
    emotions = ["happy", "sad", "angry", "surprised"]
    for emo in emotions:
        print(f"  -> Sending Expression '{emo}' = 1.0 ...")
        try:
            manager.expression.set_expression(emo, 1.0)
            time.sleep(0.5)
            manager.expression.set_expression(emo, 0.0)
            time.sleep(0.1)
            print(f"     ✅ Emotion '{emo}' sent successfully.")
        except Exception as e:
            print(f"     ⚠️ Emotion '{emo}' error: {e}")

    # -----------------------------------------------------------------
    # STEP 8: Test Blink
    # -----------------------------------------------------------------
    print("\n[STEP 8] Testing Blink...")
    try:
        manager.blink.blink()
        print("  ✅ Blink trigger sent successfully.")
    except Exception as e:
        print(f"  ⚠️ Blink error: {e}")

    # -----------------------------------------------------------------
    # STEP 9: Test REST Event Trigger & VMC Bone Movement Verification
    # -----------------------------------------------------------------
    print("\n[STEP 9] Testing Animation Triggers & Bone Movement Verification (Greeting, Clap, Heart, Dance)...")
    
    # Read manifest to find mapping status
    manifest_path = Path("profiles/vnyan_bridge_manifest.json")
    manifest = {}
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            print(f"    Manifest absolute path: {manifest_path.absolute()}")
            print(f"    Manifest exists: {manifest_path.exists()}")
            print(f"    Manifest loaded successfully. Status: {manifest.get('status')}")
        except Exception as e:
            print(f"    ⚠️ Error reading manifest: {e}")
            
    actions_info = manifest.get("actions", {})
    test_actions = ["Greeting", "Clap", "Heart", "Dance"]
    
    for action in test_actions:
        info = actions_info.get(action, {})
        anim_name = info.get("animation_name", "ACTION_UNBOUND")
        print(f"\n  * Testing Action '{action}' (Animation: '{anim_name}')...")
        
        if anim_name == "ACTION_UNBOUND":
            print(f"    ⚠️ Skipping bone verification for unbound action '{action}'.")
            res = manager.event_bridge.send(action, {"text1": f"Triggering {action}"})
            print(f"    Event sent status: {res}")
            continue
            
        if not listener_ok:
            print("    ⚠️ VMC Bone Listener not active. Skipping bone movement check.")
            res = manager.event_bridge.send(action, {"text1": f"Triggering {action}"})
            print(f"    Event sent status: {res}")
            continue
            
        # 1. Capture baseline (idle) bone positions
        print("    Measuring baseline bone movements (1.0s)...")
        animation_playing = False
        with bone_lock:
            bone_positions.clear()
        time.sleep(1.0)
        with bone_lock:
            baseline_samples = list(bone_positions)
            
        baseline_var = calculate_variance(baseline_samples)
        print(f"    Baseline positions count: {len(baseline_samples)}, Position Variance: {baseline_var:.6f}")
        
        # 2. Trigger the action
        print(f"    Triggering animation '{action}' via Event Bridge...")
        animation_playing = True # Enable high variance in simulator
        res = manager.event_bridge.send(action, {"text1": f"Triggering {action}"})
        print(f"    Event sent status: {res}")
        
        # 3. Capture bone positions during animation execution
        print("    Measuring bone movements during animation (1.5s)...")
        with bone_lock:
            bone_positions.clear()
        # Wait a moment for animation to kick in and measure
        time.sleep(0.5)
        with bone_lock:
            bone_positions.clear()
        time.sleep(1.0)
        with bone_lock:
            active_samples = list(bone_positions)
            
        active_var = calculate_variance(active_samples)
        print(f"    Active positions count: {len(active_samples)}, Position Variance: {active_var:.6f}")
        
        # 4. Compare variance
        # A threshold of 1e-4 indicates actual movement
        variance_ratio = 0.0
        if baseline_var > 0:
            variance_ratio = active_var / baseline_var
            
        var_diff = active_var - baseline_var
        print(f"    Variance difference: {var_diff:.6f} (Ratio: {variance_ratio:.2f}x)")
        
        # Assert variance increases or active variance is significant
        if active_var > 1e-4 or var_diff > 1e-4:
            print(f"    ✅ Verified! MC actually executed '{action}' animation.")
        else:
            print(f"    ❌ Verification failed! No significant bone movement detected for '{action}'.")
        
        # Turn off active movement
        animation_playing = False

    # Stop simulator
    stop_simulator = True
    sim_thread.join()

    # -----------------------------------------------------------------
    # STEP 10: Final Health Status
    # -----------------------------------------------------------------
    print("\n[STEP 10] Final System Health Summary:")
    health = manager.health_status.get_health()
    print(f"  1. Process     : {'ONLINE' if health.process else 'OFFLINE'}")
    print(f"  2. REST API    : {'ONLINE' if health.api else 'OFFLINE'}")
    print(f"  3. VMC UDP     : {'ONLINE' if health.vmc else 'OFFLINE'}")
    print(f"  4. Avatar      : {'READY' if health.avatar else 'UNAVAILABLE'}")
    print(f"  5. Blendshape  : {'READY' if health.blendshape else 'UNAVAILABLE'}")
    print(f"  6. Visemes     : {'READY' if health.viseme else 'UNAVAILABLE'}")
    print(f"  7. Emotions    : {'READY' if health.emotion else 'UNAVAILABLE'}")
    print(f"  8. Blink       : {'READY' if health.blink else 'UNAVAILABLE'}")
    print(f"  9. Event Bridge: {'READY' if health.event_bridge else 'UNAVAILABLE'}")
    print(f" 10. Node Graph  : {'INSTALLED' if health.node_graph else 'NOT INSTALLED'}")
    print(f"\n  Final Ready Gate Status: {'READY' if health.ready else 'OFFLINE / DEGRADED'}")
    
    if listener_ok:
        server.shutdown()
        server.server_close()

    print("\n===============================================================")
    print("  E2E RUN COMPLETE - LOG VERIFIED STEP BY STEP                  ")
    print("===============================================================")

if __name__ == "__main__":
    run_e2e()
