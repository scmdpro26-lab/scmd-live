from abc import ABC, abstractmethod

class VirtualMCAdapter(ABC):
    """Giao diện trừu tượng đại diện cho MC ảo (Virtual MC Renderer).
    Cho phép thay đổi backend renderer (như VNyan, VTube Studio, VSeeFace)
    mà không cần chỉnh sửa logic điều khiển của ứng dụng chính.
    """
    
    @abstractmethod
    def connect(self) -> bool:
        """Khởi tạo kết nối tới Renderer."""
        pass

    @abstractmethod
    def disconnect(self):
        """Ngắt kết nối tới Renderer."""
        pass

    @abstractmethod
    def send_blendshape(self, name: str, value: float):
        """Gửi giá trị blendshape để thay đổi nét mặt hoặc khẩu hình."""
        pass

    @abstractmethod
    def trigger_expression(self, expression_name: str, duration: float = 3.0):
        """Kích hoạt một biểu cảm khuôn mặt trong khoảng thời gian nhất định."""
        pass

    @abstractmethod
    def start_talking(self, audio_path: str = None):
        """Bắt đầu phát cử động nhép môi Lipsync (truyền file âm thanh tùy chọn)."""
        pass

    @abstractmethod
    def stop_talking(self):
        """Dừng cử động nhép môi Lipsync và đóng miệng."""
        pass

    @abstractmethod
    def trigger_checkout_success(self, product_name: str):
        """Gửi lệnh kích hoạt hiệu ứng chốt đơn thành công."""
        pass

    @abstractmethod
    def trigger_voucher_drop(self):
        """Gửi lệnh kích hoạt hiệu ứng tung voucher."""
        pass

    @abstractmethod
    def trigger_minigame_start(self):
        """Gửi lệnh kích hoạt hiệu ứng bắt đầu minigame."""
        pass

    @abstractmethod
    def trigger_apology(self, duration: float = 3.0):
        """Gửi lệnh kích hoạt cử chỉ cúi đầu xin lỗi."""
        pass

    @abstractmethod
    def trigger_greeting(self):
        """Gửi lệnh chào mừng khách hàng (cúi chào)."""
        pass

    @abstractmethod
    def trigger_clap(self):
        """Gửi lệnh vỗ tay chúc mừng."""
        pass

    @abstractmethod
    def trigger_heart(self):
        """Gửi lệnh bắn tim cảm ơn."""
        pass

    @abstractmethod
    def trigger_point_up(self):
        """Gửi lệnh chỉ tay lên trên để kêu gọi tương tác (follow/like)."""
        pass

    @abstractmethod
    def trigger_dance(self):
        """Gửi lệnh nhảy múa ăn mừng."""
        pass


    # --- 5 Actions E-commerce Mới ---
    @abstractmethod
    def trigger_point_down(self):
        """Gửi lệnh chỉ tay xuống giỏ hàng / khu vực mua hàng phía dưới màn hình."""
        pass

    @abstractmethod
    def trigger_present_left(self):
        """Gửi lệnh giới thiệu sản phẩm/slide bên trái màn hình."""
        pass

    @abstractmethod
    def trigger_present_right(self):
        """Gửi lệnh giới thiệu sản phẩm/slide bên phải màn hình."""
        pass

    @abstractmethod
    def trigger_celebrate(self):
        """Gửi lệnh ăn mừng lớn khi có đơn hàng VIP hoặc đạt milestone."""
        pass

    @abstractmethod
    def trigger_voucher_show(self):
        """Gửi lệnh trưng bày voucher / mã giảm giá trước camera."""
        pass
