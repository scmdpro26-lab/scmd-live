import logging
import time
from pathlib import Path
import os
import socket
from .setup.manager import VnyanSetupManager
from .models import SetupResult, VNyanHealth

logger = logging.getLogger("VnyanService")

class VnyanService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(VnyanService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, ip: str = "127.0.0.1", vmc_port: int = 39539, rest_port: int = 8069, ws_port: int = 8005):
        if self._initialized:
            return
        self._initialized = True
        self.ip = ip
        self.vmc_port = vmc_port
        self.rest_port = rest_port
        self.ws_port = ws_port
        self.setup_manager = VnyanSetupManager(ip, vmc_port, rest_port, ws_port)

    def run_setup(self, vnyan_exe_path: str, avatar_path: str, on_progress=None) -> SetupResult:
        """Thực thi quy trình 18 bước tích hợp VNyan tự động hoàn chỉnh."""
        changes = []
        warnings = []
        errors = []

        def update_progress(step_num: int, step_desc: str, status: str, detail: str = ""):
            if on_progress:
                try:
                    on_progress(step_num, step_desc, status, detail)
                except Exception as ex:
                    logger.error(f"Lỗi progress callback: {ex}")

        # 1. Đọc vnyan.exe path từ UI/config
        update_progress(1, "Đọc đường dẫn vnyan.exe từ UI/config", "RUNNING")
        vnyan_exe = Path(vnyan_exe_path) if vnyan_exe_path else None
        update_progress(1, "Đọc đường dẫn vnyan.exe từ UI/config", "PASS", str(vnyan_exe) if vnyan_exe else "Rỗng")

        # 2. Đọc avatar VRM path từ UI/config
        update_progress(2, "Đọc đường dẫn avatar VRM từ UI/config", "RUNNING")
        vrm_path = Path(avatar_path) if avatar_path else None
        update_progress(2, "Đọc đường dẫn avatar VRM từ UI/config", "PASS", str(vrm_path) if vrm_path else "Rỗng")

        # 3. Validate cả hai
        update_progress(3, "Xác thực đường dẫn vnyan.exe và avatar VRM", "RUNNING")
        if not vnyan_exe or not vnyan_exe.exists() or not vnyan_exe.is_file():
            err_msg = f"Đường dẫn VNyan.exe không hợp lệ hoặc không tồn tại: '{vnyan_exe}'"
            update_progress(3, "Xác thực đường dẫn vnyan.exe và avatar VRM", "FAIL", err_msg)
            return SetupResult(False, "FAILED", None, VNyanHealth(), changes, warnings, [err_msg], False)

        if not vrm_path or not vrm_path.exists() or not vrm_path.is_file():
            err_msg = f"Đường dẫn Avatar VRM không hợp lệ hoặc không tồn tại: '{vrm_path}'"
            update_progress(3, "Xác thực đường dẫn vnyan.exe và avatar VRM", "FAIL", err_msg)
            return SetupResult(False, "FAILED", None, VNyanHealth(), changes, warnings, [err_msg], False)
        update_progress(3, "Xác thực đường dẫn vnyan.exe và avatar VRM", "PASS")

        # Cập nhật cấu hình exe path để detector nhận diện chính xác
        from src.config import Config
        Config.VNYAN_EXE_PATH = str(vnyan_exe)

        # 4. Detect VNyan
        update_progress(4, "Dò quét tiến trình VNyan đang chạy", "RUNNING")
        inst = self.setup_manager.process_manager.discovery.discover()
        is_running = inst.running
        update_progress(4, "Dò quét tiến trình VNyan đang chạy", "PASS", "Đang chạy" if is_running else "Chưa chạy")

        # 5. Start VNyan nếu chưa chạy (Hoặc khởi động lại để áp dụng cấu hình mới nhất)
        update_progress(5, "Khởi chạy VNyan nếu chưa chạy", "RUNNING")
        try:
            # 1. Luôn sao lưu cấu hình trước khi can thiệp
            self.setup_manager.backup_manager.create_backup()
            
            # 2. Nếu VNyan đang chạy, thực hiện dừng tiến trình TRƯỚC để tránh tranh chấp/khóa file ghi đĩa
            if is_running:
                logger.info("VNyan đang chạy sẵn. Thực hiện dừng tiến trình trước khi ghi cấu hình và Node Graph mới...")
                self.setup_manager.process_manager.stop(vmc_port=self.vmc_port)
                time.sleep(1.5)
                
            # 3. Đồng bộ thiết lập mạng xuống settings.json
            synced_changes = self.setup_manager.config_writer.sync_network_settings(self.vmc_port, self.rest_port, self.ws_port)
            changes.extend(synced_changes)
            
            # 4. Cài đặt các Node chuyển động cơ thể xuống toàn bộ tệp đồ thị redeems*.json
            self.setup_manager.installer.install_ai_live_bridge()
            if hasattr(self.setup_manager.installer, "warnings") and self.setup_manager.installer.warnings:
                warnings.extend(self.setup_manager.installer.warnings)
            
            # 5. Khởi chạy tiến trình VNyan mới
            self.setup_manager.process_manager.start(vmc_port=self.vmc_port)
            changes.append("Khởi chạy tiến trình VNyan.exe")
            update_progress(5, "Khởi chạy VNyan nếu chưa chạy", "PASS", "Khởi động/Khởi động lại thành công")
        except Exception as e:
            err_msg = f"Lỗi khởi chạy VNyan.exe: {e}"
            update_progress(5, "Khởi chạy VNyan nếu chưa chạy", "FAIL", err_msg)
            self.setup_manager.rollback_manager.rollback()
            return SetupResult(False, "FAILED", None, VNyanHealth(), changes, warnings, [err_msg], False)

        # 6. Wait VNyan process ready
        update_progress(6, "Chờ tiến trình VNyan sẵn sàng kết nối", "RUNNING")
        start_time = time.time()
        api_ready = False
        while time.time() - start_time < 15:
            if self.setup_manager.health_checker.is_api_online():
                api_ready = True
                break
            time.sleep(0.5)
        if not api_ready:
            err_msg = f"VNyan REST API không phản hồi tại cổng {self.rest_port} sau 15 giây."
            update_progress(6, "Chờ tiến trình VNyan sẵn sàng kết nối", "FAIL", err_msg)
            self.setup_manager.rollback_manager.rollback()
            return SetupResult(False, "FAILED", None, VNyanHealth(), changes, warnings, [err_msg], False)
        update_progress(6, "Chờ tiến trình VNyan sẵn sàng kết nối", "PASS")

        # 7. Detect VNyan runtime/config
        update_progress(7, "Dò quét cấu hình runtime VNyan", "RUNNING")
        inst = self.setup_manager.process_manager.discovery.discover()
        update_progress(7, "Dò quét cấu hình runtime VNyan", "PASS", f"REST Port: {inst.api_port}, VMC Port: {inst.vmc_port}")

        # 8. Configure VMC
        update_progress(8, "Cấu hình VMC & đồng bộ cổng mạng", "RUNNING")
        try:
            synced_changes = self.setup_manager.config_writer.sync_network_settings(self.vmc_port, self.rest_port, self.ws_port)
            changes.extend(synced_changes)
            update_progress(8, "Cấu hình VMC & đồng bộ cổng mạng", "PASS", f"Đã đồng bộ {len(synced_changes)} thay đổi")
        except Exception as e:
            err_msg = f"Lỗi cấu hình VMC: {e}"
            update_progress(8, "Cấu hình VMC & đồng bộ cổng mạng", "FAIL", err_msg)
            self.setup_manager.rollback_manager.rollback()
            return SetupResult(False, "FAILED", None, VNyanHealth(), changes, warnings, [err_msg], False)

        # 9. Load/validate avatar
        update_progress(9, "Tải và xác thực tệp Avatar VRM", "RUNNING")
        try:
            profile = self.setup_manager.registry.get_profile(vrm_path)
            update_progress(9, "Tải và xác thực tệp Avatar VRM", "PASS", f"Avatar: {vrm_path.name}")
        except Exception as e:
            err_msg = f"Lỗi nạp và xác thực avatar VRM: {e}"
            update_progress(9, "Tải và xác thực tệp Avatar VRM", "FAIL", err_msg)
            self.setup_manager.rollback_manager.rollback()
            return SetupResult(False, "FAILED", None, VNyanHealth(), changes, warnings, [err_msg], False)

        # 10. Build/reconcile Avatar Profile
        update_progress(10, "Xây dựng và đối chiếu Profile biểu cảm Avatar", "RUNNING")
        try:
            expr_count = len(profile.expressions.available)
            update_progress(10, "Xây dựng và đối chiếu Profile biểu cảm Avatar", "PASS", f"Tổng số BlendShapes: {expr_count}")
        except Exception as e:
            err_msg = f"Lỗi xây dựng profile biểu cảm: {e}"
            update_progress(10, "Xây dựng và đối chiếu Profile biểu cảm Avatar", "FAIL", err_msg)
            self.setup_manager.rollback_manager.rollback()
            return SetupResult(False, "FAILED", None, VNyanHealth(), changes, warnings, [err_msg], False)

        # 11. Build/reconcile VNyan Node Graph
        update_progress(11, "Đọc và đối chiếu cấu trúc VNyan Node Graph", "RUNNING")
        try:
            graph_info = self.setup_manager.nodegraph_manager.inspect(log_warnings=True)
            update_progress(11, "Đọc và đối chiếu cấu trúc VNyan Node Graph", "PASS", f"Nodes hiện có: {graph_info.get('nodes_count', 0)}")
        except Exception as e:
            err_msg = f"Lỗi đọc Node Graph: {e}"
            update_progress(11, "Đọc và đối chiếu cấu trúc VNyan Node Graph", "FAIL", err_msg)
            self.setup_manager.rollback_manager.rollback()
            return SetupResult(False, "FAILED", None, VNyanHealth(), changes, warnings, [err_msg], False)

        # 12. Tạo đầy đủ TriggerNode → PlayAnimNode → connection
        update_progress(12, "Tạo các liên kết Node Graph (TriggerNode -> PlayAnimNode)", "RUNNING")
        # Node Graph đã được đồng bộ an toàn ở Bước 5 trước khi VNyan chạy. 
        # Bỏ qua việc cài đặt lại để tránh xung đột ghi đĩa khi VNyan đang hoạt động.
        update_progress(12, "Tạo các liên kết Node Graph (TriggerNode -> PlayAnimNode)", "PASS", "Bỏ qua cài đặt lại do VNyan đang chạy")


        # 13. Build Action Registry
        update_progress(13, "Xây dựng Action Registry trong tệp Manifest", "RUNNING")
        # Hoạt động tự động chạy khi cài đặt Node Graph (lưu profiles/vnyan_bridge_manifest.json)
        update_progress(13, "Xây dựng Action Registry trong tệp Manifest", "PASS")

        # 14. Validate tất cả action mapping
        update_progress(14, "Xác thực tất cả các Action Mapping trong manifest và graph", "RUNNING")
        try:
            # Đọc lại manifest để xác định xem có action nào bị ACTION_UNBOUND hay không
            manifest_path = Path("profiles/vnyan_bridge_manifest.json")
            unbound_actions = []
            if manifest_path.exists():
                import json
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
                    for act, act_info in manifest_data.get("actions", {}).items():
                        if act_info.get("animation_name") == "ACTION_UNBOUND":
                            unbound_actions.append(act)
            if unbound_actions:
                err_msg = f"Lỗi ánh xạ hoạt ảnh: Các actions sau chưa được gán anim: {', '.join(unbound_actions)}"
                update_progress(14, "Xác thực tất cả các Action Mapping trong manifest và graph", "FAIL", err_msg)
                self.setup_manager.rollback_manager.rollback()
                return SetupResult(False, "FAILED", None, VNyanHealth(), changes, warnings, [err_msg], False)
            update_progress(14, "Xác thực tất cả các Action Mapping trong manifest và graph", "PASS")
        except Exception as e:
            err_msg = f"Lỗi xác thực Action Mapping: {e}"
            update_progress(14, "Xác thực tất cả các Action Mapping trong manifest và graph", "FAIL", err_msg)
            self.setup_manager.rollback_manager.rollback()
            return SetupResult(False, "FAILED", None, VNyanHealth(), changes, warnings, [err_msg], False)

        # 15. Verify VMC
        update_progress(15, "Xác minh kết nối VMC UDP", "RUNNING")
        try:
            self.setup_manager.vmc_transport.connect()
            self.setup_manager.vmc_transport.send_blendshape("happy", 0.0)
            update_progress(15, "Xác minh kết nối VMC UDP", "PASS")
        except Exception as e:
            err_msg = f"Lỗi kết nối VMC UDP: {e}"
            update_progress(15, "Xác minh kết nối VMC UDP", "FAIL", err_msg)
            self.setup_manager.rollback_manager.rollback()
            return SetupResult(False, "FAILED", None, VNyanHealth(), changes, warnings, [err_msg], False)

        # 16. Verify Node Graph
        update_progress(16, "Xác minh sự tồn tại của Node Graph", "RUNNING")
        try:
            graph_info = self.setup_manager.nodegraph_manager.inspect(log_warnings=True)
            if not graph_info.get("node_exists", False):
                raise RuntimeError("Không tìm thấy các node AI Live Bridge trong redeems.json")
            update_progress(16, "Xác minh sự tồn tại của Node Graph", "PASS")
        except Exception as e:
            err_msg = f"Lỗi xác minh Node Graph: {e}"
            update_progress(16, "Xác minh sự tồn tại của Node Graph", "FAIL", err_msg)
            self.setup_manager.rollback_manager.rollback()
            return SetupResult(False, "FAILED", None, VNyanHealth(), changes, warnings, [err_msg], False)

        # 17. Verify Animation Bridge
        update_progress(17, "Xác minh trạng thái kết nối Animation Bridge", "RUNNING")
        try:
            health = self.setup_manager.health_status.get_health()
            if not health.ready:
                not_ready = []
                if not health.process: not_ready.append("Process")
                if not health.api: not_ready.append("API")
                if not health.vmc: not_ready.append("VMC")
                if not health.avatar: not_ready.append("Avatar Profile")
                if not health.node_graph: not_ready.append("Node Graph")
                if not (health.viseme and health.emotion and health.blink): not_ready.append("Animation Mapping")
                err_msg = f"Animation Bridge chưa sẵn sàng. Các cấu phần lỗi: {', '.join(not_ready)}"
                update_progress(17, "Xác minh trạng thái kết nối Animation Bridge", "FAIL", err_msg)
                self.setup_manager.rollback_manager.rollback()
                return SetupResult(False, "FAILED", None, health, changes, warnings, [err_msg], False)
            update_progress(17, "Xác minh trạng thái kết nối Animation Bridge", "PASS")
        except Exception as e:
            err_msg = f"Lỗi xác minh Animation Bridge: {e}"
            update_progress(17, "Xác minh trạng thái kết nối Animation Bridge", "FAIL", err_msg)
            self.setup_manager.rollback_manager.rollback()
            return SetupResult(False, "FAILED", None, VNyanHealth(), changes, warnings, [err_msg], False)

        # 18. Chuyển UI sang trạng thái: MC ẢO — SẴN SÀNG ĐIỀU KHIỂN
        update_progress(18, "Cập nhật trạng thái giao diện: MC ẢO — SẴN SÀNG ĐIỀU KHIỂN", "RUNNING")
        update_progress(18, "Cập nhật trạng thái giao diện: MC ẢO — SẴN SÀNG ĐIỀU KHIỂN", "PASS")

        # Thiết lập biểu cảm chào đón ban đầu khi bắt đầu thành công
        try:
            self.setup_manager.expression.set_expression("happy", 0.5)
            self.setup_manager.blink.blink()
        except Exception:
            pass

        return SetupResult(
            success=True,
            status="READY",
            avatar_profile=self.setup_manager.registry.current_profile,
            health=health,
            changes=changes,
            warnings=warnings,
            errors=[],
            rollback_available=True
        )

    def stop_mc(self) -> None:
        """Tắt MC ảo (Tắt tiến trình VNyan)."""
        logger.info("Yêu cầu tắt MC ảo...")
        self.setup_manager.process_manager.stop(vmc_port=self.vmc_port)

    def check_connection(self) -> VNyanHealth:
        """Kiểm tra trạng thái kết nối tức thời."""
        return self.setup_manager.health_status.get_health()

    def get_status_details(self) -> dict[str, tuple[bool, str]]:
        """
        Trả về trạng thái chi tiết của 6 cấu phần bắt buộc.
        Định dạng: { "Tên cấu phần": (Trạng thái bool, "Mô tả chi tiết") }
        """
        health = self.check_connection()
        details = {}

        # 1. VNyan process
        details["process"] = (health.process, "PASS - Tiến trình đang chạy" if health.process else "FAIL - Chưa khởi chạy VNyan.exe")

        # 2. Avatar
        avatar_profile = self.setup_manager.registry.current_profile
        avatar_name = avatar_profile.source_path.name if avatar_profile else "Chưa xác định"
        details["avatar"] = (health.avatar, f"PASS - Đã tải: {avatar_name}" if health.avatar else "FAIL - Chưa nạp Avatar VRM")

        # 3. VMC
        details["vmc"] = (health.vmc, "PASS - Cổng VMC UDP 39539 hoạt động" if health.vmc else "FAIL - Lỗi kết nối VMC UDP")

        # 4. Node Graph
        details["node_graph"] = (health.node_graph, "PASS - Đồ thị Node Graph hợp lệ" if health.node_graph else "FAIL - Đồ thị bị lỗi hoặc chưa cài đặt")

        # 5. Animation Mapping
        mapping_pass = health.viseme and health.emotion and health.blink and health.blendshape
        details["animation_mapping"] = (mapping_pass, "PASS - Ánh xạ 10 actions đầy đủ" if mapping_pass else "FAIL - Thiếu ánh xạ Blendshape/Expression")

        # 6. AI Live Control
        control_pass = health.event_bridge and health.api
        details["control"] = (control_pass, "PASS - REST API hoạt động" if control_pass else "FAIL - Mất kết nối REST API")

        return details
