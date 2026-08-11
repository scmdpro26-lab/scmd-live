# src/vmc_service.py
_vmc_instance = None

def get_vmc_client() -> "VMCClient":
    """Trả về thực thể Singleton duy nhất của VMCClient trên toàn hệ thống.
    Tránh tình trạng khởi tạo nhiều Client gây lỗi bind cổng UDP.
    """
    global _vmc_instance
    if _vmc_instance is None:
        from src.vmc_client import VMCClient
        _vmc_instance = VMCClient()
    return _vmc_instance
