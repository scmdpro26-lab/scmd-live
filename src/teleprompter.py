import logging
from collections import deque

logger = logging.getLogger("Teleprompter")

class TeleprompterService:
    """Hàng đợi câu AI soạn sẵn, hiển thị lên màn hình phụ (hoặc tab GUI riêng)
    để người dẫn live đọc bằng giọng thật - đáp ứng yêu cầu 'giao tiếp thời gian thực bằng người'.
    """

    def __init__(self, on_new_line_callback=None):
        self.queue = deque(maxlen=20)
        self.on_new_line_callback = on_new_line_callback

    def push_line(self, text: str):
        """Đẩy câu thoại mới từ AI soạn vào hàng đợi và kích hoạt callback cập nhật giao diện."""
        self.queue.append(text)
        logger.info(f"Teleprompter: Đã đẩy dòng nhắc mới -> '{text}'")
        if self.on_new_line_callback:
            try:
                self.on_new_line_callback(text)
            except Exception as e:
                logger.error(f"Lỗi khi thực thi callback Teleprompter: {e}")

    def pop_next(self) -> str | None:
        """Lấy câu thoại cũ nhất ra khỏi hàng đợi để đọc."""
        if self.queue:
            return self.queue.popleft()
        return None

    def get_all(self) -> list[str]:
        """Trả về toàn bộ danh sách các câu nhắc hiện tại trong hàng đợi."""
        return list(self.queue)

    def clear(self):
        """Xóa sạch hàng đợi lời nhắc."""
        self.queue.clear()
