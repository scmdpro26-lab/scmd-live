import time
import logging
import threading
from pathlib import Path
from src.vmc_adapter import VirtualMCAdapter
from ai_live.integrations.vnyan import VnyanService, VnyanSetupManager
from ai_live.integrations.vnyan.exceptions import CapabilityUnavailable
from src.action_engine import ActionEngine, ActionSource

logger = logging.getLogger("VMCClient")

class VMCClient(VirtualMCAdapter):

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(VMCClient, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, ip=None, vmc_port=None, rest_port=None):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        from src.config import Config
        ip = ip if ip is not None else Config.VMC_IP
        vmc_port = vmc_port if vmc_port is not None else Config.VMC_PORT
        rest_port = rest_port if rest_port is not None else Config.REST_PORT

        # Liên kết trực tiếp tới bộ quản lý VNyan V2 mới của ai_live thông qua VnyanService
        self.service = VnyanService(ip, vmc_port, rest_port)
        self.manager = self.service.setup_manager
        self._vnyan_process = self.manager.process_manager
        
        # Liên kết ActionEngine tập trung
        self.action_engine = ActionEngine(self.manager.animation)
        
        self._renderer_online = False
        self._is_talking = False
        self._talk_thread = None
        
        self.auto_configure_vnyan_settings(vmc_port, rest_port)
        self.connect()

        # Tự động nạp profile avatar mặc định tại startup nếu có
        import os
        env_avatar = os.environ.get("AVATAR_VRM_PATH", os.environ.get("DEFAULT_AVATAR_PATH", ""))
        default_avatar = Path(env_avatar) if env_avatar else None

        if default_avatar and default_avatar.exists():
            self.load_avatar(default_avatar)
        else:
            # Fallback sang file .vrm đầu tiên trong thư mục Vrm
            vrm_dir = Path("Vrm")
            if vrm_dir.exists():
                vrm_files = list(vrm_dir.glob("*.vrm"))
                if vrm_files:
                    self.load_avatar(vrm_files[0])

        # Luồng kiểm tra sức khỏe tương thích ngược
        self._stop_health_check = False
        self._health_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self._health_thread.start()

    def load_avatar(self, avatar_path) -> bool:
        """Cập nhật avatar đang hoạt động trong Registry và tải profile mới."""
        if not avatar_path:
            return False
        path = Path(avatar_path)
        if path.exists():
            try:
                self.manager.registry.get_profile(path)
                logger.info(f"VMCClient: Đã tải profile avatar mới từ {path.name} (Hash: {self.manager.profile_manager._get_file_hash(path)})")
                return True
            except Exception as e:
                logger.error(f"VMCClient: Lỗi khi tải profile avatar: {e}")
                return False
        else:
            logger.error(f"VMCClient: Không tìm thấy file avatar tại {path}")
            return False

    @property
    def renderer_online(self) -> bool:
        return self._renderer_online

    @renderer_online.setter
    def renderer_online(self, value: bool):
        self._renderer_online = value

    @property
    def vmc_client(self):
        return self.manager.vmc_transport.client

    @vmc_client.setter
    def vmc_client(self, value):
        self.manager.vmc_transport.client = value

    def _health_check_loop(self):
        while not self._stop_health_check:
            self._renderer_online = self.check_vnyan_connection()
            time.sleep(5.0)

    def auto_configure_vnyan_settings(self, vmc_port: int, rest_port: int) -> bool:
        changes = self.manager.config_writer.sync_network_settings(vmc_port, rest_port, 8005)
        return len(changes) >= 0

    def launch_vnyan(self) -> bool:
        try:
            exe_path = self.manager.detector.detect_vnyan_exe()
            from src.config import Config
            avatar_path = Config.AVATAR_VRM_PATH if Config.AVATAR_VRM_PATH else os.environ.get("DEFAULT_AVATAR_PATH", "")
            result = self.service.run_setup(str(exe_path) if exe_path else "", str(avatar_path))
            return result.success
        except Exception:
            return False

    def check_vnyan_connection(self) -> bool:
        return self.service.check_connection().ready

    def connect(self) -> bool:
        return self.manager.vmc_transport.connect()

    def disconnect(self):
        self._stop_health_check = True
        self.manager.vmc_transport.close()

    def send_blendshape(self, name: str, value: float):
        try:
            name_lower = name.lower()
            if name_lower in ["a", "e", "i", "o", "u"] or name_lower.startswith("viseme_"):
                v_char = name_lower.split("_")[-1]
                self.manager.viseme.set_viseme(v_char, value)
            elif name_lower in ["mouthopen"]:
                self.manager.viseme.set_viseme("a", value)
            else:
                self.manager.expression.set_expression(name, value)
        except CapabilityUnavailable as e:
            logger.warning(f"VMCClient.send_blendshape: '{name}' không khả dụng: {e}")
        except Exception as e:
            logger.error(f"VMCClient.send_blendshape: Lỗi gửi '{name}': {e}")

    def trigger_expression(self, expression_name: str, duration: float = 3.0):
        def run_expr():
            try:
                self.manager.expression.set_expression(expression_name, 1.0)
                time.sleep(duration)
                self.manager.expression.set_expression(expression_name, 0.0)
            except CapabilityUnavailable as e:
                logger.warning(f"trigger_expression: Biểu cảm '{expression_name}' không khả dụng: {e}")
            except Exception as e:
                logger.error(f"trigger_expression: Lỗi kích hoạt '{expression_name}': {e}")

        threading.Thread(target=run_expr, daemon=True).start()

    def blink(self, duration_ms: int = 120) -> bool:
        """Kích hoạt nháy mắt thông qua BlinkController."""
        try:
            return self.manager.blink.blink(duration_ms)
        except CapabilityUnavailable as e:
            logger.warning(f"blink: Hoạt ảnh nháy mắt không khả dụng: {e}")
            return False
        except Exception as e:
            logger.error(f"blink: Lỗi khi nháy mắt: {e}")
            return False

    def start_talking(self, audio_path: str = None):
        if self._is_talking:
            return
        self._is_talking = True
        self._talk_thread = threading.Thread(target=self._lip_sync_loop, args=(audio_path,), daemon=True)
        self._talk_thread.start()
        logger.info(f"VMC: Bắt đầu nói (Lipsync ON, audio={audio_path})")

    def stop_talking(self):
        self._is_talking = False
        if self._talk_thread:
            self._talk_thread.join(timeout=0.5)
            self._talk_thread = None
        try:
            self.manager.viseme.set_viseme("a", 0.0)
        except CapabilityUnavailable as e:
            logger.warning(f"stop_talking: viseme không khả dụng: {e}")
        except Exception as e:
            logger.error(f"stop_talking: lỗi: {e}")
        logger.info("VMC: Dừng nói (Lipsync OFF)")

    def _lip_sync_loop(self, audio_path: str = None):
        import random
        
        envelope = []
        if audio_path and audio_path.endswith(".wav"):
            try:
                from src.lipsync import compute_amplitude_envelope
                envelope = compute_amplitude_envelope(audio_path)
            except Exception as e:
                logger.error(f"Lỗi khi tính toán amplitude envelope: {e}")
                
        try:
            if envelope:
                logger.info("Sử dụng real lipsync từ file âm thanh WAV...")
                for val in envelope:
                    if not self._is_talking:
                        break
                    self.manager.viseme.set_viseme("a", val)
                    time.sleep(0.05)
            else:
                logger.info("Sử dụng fallback lipsync ngẫu nhiên...")
                while self._is_talking:
                    val = random.uniform(0.2, 0.9)
                    self.manager.viseme.set_viseme("a", val)
                    time.sleep(random.uniform(0.08, 0.15))
                    self.manager.viseme.set_viseme("a", 0.05)
                    time.sleep(0.05)
        except CapabilityUnavailable as e:
            logger.warning(f"_lip_sync_loop: viseme không khả dụng: {e}")
        except Exception as e:
            logger.error(f"_lip_sync_loop: lỗi: {e}")
            
        try:
            self.manager.viseme.set_viseme("a", 0.0)
        except Exception:
            pass

    def send_action_trigger(self, path: str, arguments: list, source: int = ActionSource.AI_EVENT) -> bool:
        action_name = path.split("/")[-1]
        try:
            return self.action_engine.dispatch(action_name, source, arguments)
        except CapabilityUnavailable as e:
            logger.warning(f"send_action_trigger: động tác '{action_name}' không khả dụng: {e}")
            return False
        except Exception as e:
            logger.error(f"send_action_trigger: lỗi kích hoạt động tác '{action_name}': {e}")
            return False


    def trigger_checkout_success(self, product_name: str):
        self.send_action_trigger("/VMC/Ext/Action/CheckoutSuccess", [product_name])

    def trigger_voucher_drop(self):
        self.send_action_trigger("/VMC/Ext/Action/VoucherDrop", [])

    def trigger_minigame_start(self):
        self.send_action_trigger("/VMC/Ext/Action/MinigameStart", [])

    def trigger_apology(self, duration: float = 3.0):
        self.send_action_trigger("/VMC/Ext/Action/Apology", [float(duration)])

    def trigger_cart_pin(self, product_code: str, product_name: str):
        self.send_action_trigger("/VMC/Ext/Action/CartPin", [product_code, product_name])

    def trigger_greeting(self):
        self.send_action_trigger("/VMC/Ext/Action/Greeting", [])

    def trigger_clap(self):
        self.send_action_trigger("/VMC/Ext/Action/Clap", [])

    def trigger_heart(self):
        self.send_action_trigger("/VMC/Ext/Action/Heart", [])

    def trigger_point_up(self):
        self.send_action_trigger("/VMC/Ext/Action/PointUp", [])

    def trigger_dance(self):
        self.send_action_trigger("/VMC/Ext/Action/Dance", [])

    # --- 5 Actions E-commerce Mới ---
    def trigger_point_down(self):
        """Chỉ tay xuống giỏ hàng / khu vực mua hàng phía dưới màn hình."""
        self.send_action_trigger("/VMC/Ext/Action/PointDown", [])

    def trigger_present_left(self):
        """Giới thiệu sản phẩm/slide bên trái màn hình."""
        self.send_action_trigger("/VMC/Ext/Action/PresentLeft", [])

    def trigger_present_right(self):
        """Giới thiệu sản phẩm/slide bên phải màn hình."""
        self.send_action_trigger("/VMC/Ext/Action/PresentRight", [])

    def trigger_celebrate(self):
        """Ăn mừng lớn khi có đơn hàng VIP hoặc đạt milestone."""
        self.send_action_trigger("/VMC/Ext/Action/Celebrate", [])

    def trigger_voucher_show(self):
        """Trưng bày voucher / mã giảm giá trước camera."""
        self.send_action_trigger("/VMC/Ext/Action/VoucherShow", [])

