import logging
from pythonosc.udp_client import SimpleUDPClient

logger = logging.getLogger("VMCTransport")

class VMCTransport:
    def __init__(self, ip: str, port: int):
        self.ip = ip
        self.port = port
        self.client = None

    def connect(self) -> bool:
        try:
            self.client = SimpleUDPClient(self.ip, self.port)
            logger.info(f"VMCTransport: Kết nối tới UDP {self.ip}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"VMCTransport: Kết nối thất bại: {e}")
            return False

    def send_blendshape(self, name: str, value: float) -> bool:
        if not self.client:
            return False
        try:
            self.client.send_message("/VMC/Ext/Blend/Val", [name, float(value)])
            self.client.send_message("/VMC/Ext/Blend/Apply", [])
            return True
        except Exception as e:
            logger.error(f"VMCTransport: Lỗi khi gửi blendshape '{name}': {e}")
            return False

    def send_blendshape_batch(self, values: dict[str, float]) -> bool:
        if not self.client:
            return False
        try:
            for name, value in values.items():
                self.client.send_message("/VMC/Ext/Blend/Val", [name, float(value)])
            self.client.send_message("/VMC/Ext/Blend/Apply", [])
            return True
        except Exception as e:
            logger.error(f"VMCTransport: Lỗi khi gửi batch blendshape: {e}")
            return False

    def send_pose(self, bone_name: str, px: float, py: float, pz: float, rx: float, ry: float, rz: float, rw: float) -> bool:
        """Gửi tọa độ xương khớp qua VMC (địa chỉ /VMC/Ext/Bone/Pos)."""
        if not self.client:
            return False
        try:
            self.client.send_message("/VMC/Ext/Bone/Pos", [bone_name, px, py, pz, rx, ry, rz, rw])
            return True
        except Exception as e:
            logger.error(f"VMCTransport: Lỗi khi gửi xương '{bone_name}': {e}")
            return False

    def send_trigger(self, action_name: str, args: list | None = None) -> bool:
        """Gửi trigger hoạt ảnh qua giao thức VMC UDP:
        1. /NyaVMC/Trigger [action_name]
        2. /VMC/Ext/Action/[action_name] [args...]
        """
        if not self.client:
            return False
        if args is None:
            args = []
        try:
            # 1. Gửi chuẩn /NyaVMC/Trigger
            self.client.send_message("/NyaVMC/Trigger", [action_name])
            
            # 2. Gửi chuẩn /VMC/Ext/Action/<ActionName>
            action_path = f"/VMC/Ext/Action/{action_name}"
            self.client.send_message(action_path, [str(a) for a in args])
            
            logger.info(f"VMCTransport: Gửi trigger VMC thành công: {action_name} (/NyaVMC/Trigger & {action_path})")
            return True
        except Exception as e:
            logger.error(f"VMCTransport: Lỗi khi gửi trigger '{action_name}': {e}")
            return False

    def close(self):
        self.client = None
