class VNyanIntegrationError(Exception):
    """Lỗi cơ sở cho tích hợp VNyan."""
    pass

class CapabilityUnavailable(VNyanIntegrationError):
    """Ngoại lệ ném ra khi một khả năng của avatar (như nháy mắt, nhép miệng) không khả dụng."""
    pass

class ConfigError(VNyanIntegrationError):
    """Lỗi đọc/ghi tệp cấu hình của VNyan."""
    pass

class NodeGraphError(VNyanIntegrationError):
    """Lỗi thao tác trên đồ thị Node Graph."""
    pass

class VRMInspectError(VNyanIntegrationError):
    """Lỗi khi phân tích tệp avatar VRM."""
    pass
