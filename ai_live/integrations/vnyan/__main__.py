import sys
import argparse
import pprint
from pathlib import Path
from .service import VnyanService

def cmd_doctor(args):
    print("=== VNYAN DOCTOR: CHẨN ĐOÁN HỆ THỐNG ===")
    service = VnyanService()
    health = service.check_connection()
    print("Trạng thái VNyan:")
    print(f"  Tiến trình VNyan.exe: {'ONLINE' if health.process else 'OFFLINE'}")
    print(f"  REST API Port 8069  : {'ONLINE' if health.api else 'OFFLINE'}")
    print(f"  VMC UDP Port 39539  : {'ONLINE' if health.vmc else 'OFFLINE'}")
    print(f"  Avatar loaded       : {'YES' if health.avatar else 'NO'}")
    print(f"  Node Graph Bridge   : {'INSTALLED' if health.node_graph else 'NOT INSTALLED'}")
    print(f"  Blink capability    : {'READY' if health.blink else 'UNAVAILABLE'}")
    print(f"  Viseme capability   : {'READY' if health.viseme else 'UNAVAILABLE'}")
    print(f"  Emotion capability  : {'READY' if health.emotion else 'UNAVAILABLE'}")
    print(f"\nReady status: {'READY' if health.ready else 'NOT READY'}")
    sys.exit(0 if health.ready else 1)

def cmd_setup(args):
    print(f"=== VNYAN SETUP: BẮT ĐẦU 1-CLICK SETUP VÀO HỆ THỐNG ===")
    avatar_path = Path(args.avatar)
    if not avatar_path.exists():
        print(f"Error: Avatar file not found: {avatar_path}")
        sys.exit(1)
        
    service = VnyanService()
    vnyan_exe = service.setup_manager.detector.detect_vnyan_exe()
    
    def on_progress(step_num, step_desc, status, detail=""):
        detail_str = f" - {detail}" if detail else ""
        print(f"[{step_num}/18] {step_desc}: {status}{detail_str}")
        
    result = service.run_setup(str(vnyan_exe) if vnyan_exe else "", str(avatar_path), on_progress=on_progress)
    print("\nKết quả thiết lập:")
    print(f"  Thành công: {result.success}")
    print(f"  Trạng thái: {result.status}")
    print(f"  Số thay đổi: {len(result.changes)}")
    for change in result.changes:
        print(f"    - {change}")
    print(f"  Số cảnh báo: {len(result.warnings)}")
    for warning in result.warnings:
        print(f"    - {warning}")
    print(f"  Số lỗi     : {len(result.errors)}")
    for err in result.errors:
        print(f"    - {err}")
        
    sys.exit(0 if result.success else 1)

def cmd_test(args):
    print("=== VNYAN TEST: CHẠY THỬ NGHIỆM CHUYỂN ĐỘNG ===")
    manager = VnyanSetupManager()
    health = manager.health_status.get_health()
    if not health.ready:
        print("Error: VNyan is not running or ports are offline. Cannot run test.")
        sys.exit(1)
        
    print("1. Thử gửi Joy = 1.0 (Biểu cảm cười)...")
    manager.expression.set_expression("happy", 1.0)
    import time
    time.sleep(1.5)
    manager.expression.set_expression("happy", 0.0)
    
    print("2. Thử gửi chớp mắt...")
    try:
        manager.blink.blink()
    except Exception as e:
        print(f"Warning: {e}")
        
    print("3. Thử nhép miệng (MouthOpen A)...")
    try:
        manager.viseme.set_viseme("A", 1.0)
        time.sleep(1.0)
        manager.viseme.set_viseme("A", 0.0)
    except Exception as e:
        print(f"Warning: {e}")
        
    print("✅ Hoàn thành thử nghiệm chuyển động.")
    sys.exit(0)

def cmd_rollback(args):
    print("=== VNYAN ROLLBACK: KHÔI PHỤC CẤU HÌNH GỐC ===")
    manager = VnyanSetupManager()
    success = manager.rollback_manager.rollback()
    if success:
        print("✅ Khôi phục cấu hình gốc thành công.")
        sys.exit(0)
    else:
        print("❌ Khôi phục cấu hình gốc thất bại.")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="AI Live VNyan Auto-Setup Manager CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    subparsers.add_parser("doctor", help="Chẩn đoán trạng thái VNyan và kết nối")
    
    setup_parser = subparsers.add_parser("setup", help="Cấu hình tự động 1-Click Setup")
    setup_parser.add_argument("--avatar", required=True, help="Đường dẫn đến tệp tin avatar .vrm")
    
    subparsers.add_parser("test", help="Chạy thử chuyển động MC trên VNyan")
    
    subparsers.add_parser("rollback", help="Khôi phục cài đặt trước đó")
    
    args = parser.parse_args()
    if args.command == "doctor":
        cmd_doctor(args)
    elif args.command == "setup":
        cmd_setup(args)
    elif args.command == "test":
        cmd_test(args)
    elif args.command == "rollback":
        cmd_rollback(args)

if __name__ == "__main__":
    main()
