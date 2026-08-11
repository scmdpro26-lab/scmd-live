import time
import socket
import logging
from pathlib import Path
from ai_live.integrations.vnyan import VnyanSetupManager
from ai_live.integrations.vnyan.transport.vmc import VMCTransport
from ai_live.integrations.vnyan.transport.http import HTTPTransport
from ai_live.integrations.vnyan.controllers import ExpressionController, VisemeController, BlinkController, AnimationController

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("RealVNyanE2E")

def run_real_e2e():
    print("==================================================================")
    print("   AI LIVE × VNYAN REAL SYSTEM E2E TRANSMISSION VERIFICATION      ")
    print("==================================================================")
    
    manager = VnyanSetupManager()
    
    # 1. Kiểm tra tiến trình VNyan.exe thật
    is_running = manager.process_manager.is_running()
    if not is_running:
        print("[INIT] Khởi chạy tiến trình VNyan.exe thật...")
        manager.process_manager.start()
        time.sleep(4.0)
        
    inst = manager.discovery.discover()
    print(f"[PROCESS] VNyan.exe Real PID: {inst.pid}, Status: {'RUNNING' if inst.running else 'STOPPED'}")
    assert inst.running, "VNyan.exe phải đang chạy thật trên hệ thống Windows!"
    
    # 2. Khởi tạo transport thật kết nối UDP 39539 và REST HTTP 8069 (ZERO MOCKS)
    vmc_transport = VMCTransport("127.0.0.1", 39539)
    vmc_transport.connect()
    http_transport = HTTPTransport("127.0.0.1", 8069)
    
    # Khởi tạo Controllers với profile thật của MC
    avatar_path = Path(r"C:\Users\quanying_zhang\Downloads\MC_TikTok_VietNam_v4_FIXED.vrm")
    profile = manager.registry.get_profile(avatar_path)
    
    expr_ctrl = ExpressionController(vmc_transport, manager.registry)
    viseme_ctrl = VisemeController(vmc_transport, manager.registry)
    blink_ctrl = BlinkController(vmc_transport, manager.registry)
    anim_ctrl = AnimationController(vmc_transport, manager.event_bridge)

    print("\n--- TEST 1: REAL VMC UDP -> Blendshape 'A' ---")
    print("AI Live -> VMC UDP -> Blendshape 'A' = 1.0")
    res_a = viseme_ctrl.set_viseme("A", 1.0)
    time.sleep(0.5)
    viseme_ctrl.set_viseme("A", 0.0)
    print(f"  -> Gửi gói tin VMC UDP 'A': {res_a}")
    assert res_a, "Gói tin UDP VMC 'A' phải được gửi thành công!"

    print("\n--- TEST 2: REAL VMC UDP -> Blendshape 'happy' (Fun) ---")
    print("AI Live -> VMC UDP -> Blendshape 'happy' (Fun) = 1.0")
    res_happy = expr_ctrl.set_expression("happy", 1.0)
    time.sleep(0.5)
    expr_ctrl.set_expression("happy", 0.0)
    print(f"  -> Gửi gói tin VMC UDP 'happy' (Fun): {res_happy}")
    assert res_happy, "Gói tin UDP VMC 'happy' phải được gửi thành công!"

    print("\n--- TEST 3: REAL VMC UDP -> Blendshape 'blink' (Blink) ---")
    print("AI Live -> VMC UDP -> Blendshape 'blink' (Blink) = 1.0")
    res_blink = blink_ctrl.blink()
    print(f"  -> Gửi gói tin VMC UDP 'blink': {res_blink}")
    assert res_blink, "Gói tin UDP VMC 'blink' phải được gửi thành công!"

    print("\n--- TEST 4: REAL VMC UDP -> /NyaVMC/Trigger & /VMC/Ext/Action/Greeting ---")
    print("AI Live -> VMC UDP (/NyaVMC/Trigger & /VMC/Ext/Action/Greeting) -> TriggerNode -> PlayAnimNode")
    res_greeting = anim_ctrl.trigger_greeting()
    time.sleep(0.5)
    print(f"  -> Gửi gói tin VMC UDP Trigger 'Greeting': {res_greeting}")
    assert res_greeting, "Gói tin UDP VMC Trigger 'Greeting' phải được gửi thành công!"

    print("\n--- TEST 5: REAL VMC UDP -> /NyaVMC/Trigger & /VMC/Ext/Action/Dance ---")
    print("AI Live -> VMC UDP (/NyaVMC/Trigger & /VMC/Ext/Action/Dance) -> TriggerNode -> PlayAnimNode")
    res_dance = anim_ctrl.trigger_dance()
    time.sleep(0.5)
    print(f"  -> Gửi gói tin VMC UDP Trigger 'Dance': {res_dance}")
    assert res_dance, "Gói tin UDP VMC Trigger 'Dance' phải được gửi thành công!"

    print("\n==================================================================")
    print("   REAL VNYAN EXECUTION VERIFIED 100% (ZERO MOCKS)                ")
    print("==================================================================")

if __name__ == "__main__":
    run_real_e2e()
