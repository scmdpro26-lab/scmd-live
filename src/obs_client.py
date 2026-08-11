import logging
import queue
import threading
from obswebsocket import obsws, requests
from obswebsocket.exceptions import ConnectionFailure

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OBSClient")

class OBSTask:
    def __init__(self, func, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.result_event = threading.Event()
        self.result = None
        self.exception = None

class OBSClient:
    def __init__(self, host="127.0.0.1", port=4455, password=""):
        self.host = host
        self.port = port
        self.password = password
        self.client = None
        self.is_connected = False
        
        # Hàng đợi lệnh OBS chạy trên luồng đơn (Single-thread queue)
        self._queue = queue.Queue()
        self._worker_thread = threading.Thread(target=self._worker_loop, name="OBSWorkerThread", daemon=True)
        self._worker_thread.start()

    def _worker_loop(self):
        """Worker thread xử lý tuần tự từng lệnh OBS từ hàng đợi."""
        while True:
            task = self._queue.get()
            if task is None:
                self._queue.task_done()
                break
            try:
                task.result = task.func(*task.args, **task.kwargs)
            except Exception as e:
                task.exception = e
            finally:
                task.result_event.set()
                self._queue.task_done()

    def _execute_queued(self, func, *args, **kwargs):
        """Đưa lệnh vào hàng đợi và đợi kết quả trả về từ worker thread."""
        task = OBSTask(func, *args, **kwargs)
        self._queue.put(task)
        # Đợi tối đa 5.0 giây tránh treo luồng gọi nếu có lỗi hệ thống
        finished = task.result_event.wait(timeout=5.0)
        if not finished:
            logger.error(f"Lệnh OBS {func.__name__} bị timeout sau 5 giây!")
            return False
        if task.exception:
            raise task.exception
        return task.result

    def connect(self) -> bool:
        """Kết nối tới OBS Studio qua WebSocket (gửi qua hàng đợi)."""
        return self._execute_queued(self._connect_impl)

    def _connect_impl(self) -> bool:
        try:
            self.client = obsws(self.host, self.port, self.password)
            self.client.connect()
            self.is_connected = True
            logger.info("Kết nối thành công tới OBS WebSocket!")
            return True
        except ConnectionFailure as e:
            logger.error(f"Lỗi kết nối OBS: {e}")
            self.is_connected = False
            self.client = None
            return False
        except Exception as e:
            logger.error(f"Lỗi không xác định khi kết nối OBS: {e}")
            self.is_connected = False
            self.client = None
            return False

    def disconnect(self):
        """Ngắt kết nối OBS WebSocket (gửi qua hàng đợi)."""
        self._execute_queued(self._disconnect_impl)

    def _disconnect_impl(self):
        if self.client and self.is_connected:
            self.client.disconnect()
            logger.info("Đã ngắt kết nối OBS WebSocket.")
        self.is_connected = False
        self.client = None

    def change_scene(self, scene_name: str) -> bool:
        """Đổi Scene hiện tại trong OBS (gửi qua hàng đợi)."""
        return self._execute_queued(self._change_scene_impl, scene_name)

    def _change_scene_impl(self, scene_name: str) -> bool:
        if not self.is_connected or not self.client:
            logger.warning("Chưa kết nối OBS WebSocket.")
            return False
        try:
            self.client.call(requests.SetCurrentProgramScene(sceneName=scene_name))
            logger.info(f"Đã đổi sang scene: '{scene_name}'")
            return True
        except Exception as e:
            logger.error(f"Không thể đổi scene '{scene_name}': {e}")
            return False

    def get_scene_item_id(self, scene_name: str, source_name: str) -> int:
        """Lấy Scene Item ID của một Source (gửi qua hàng đợi)."""
        return self._execute_queued(self._get_scene_item_id_impl, scene_name, source_name)

    def _get_scene_item_id_impl(self, scene_name: str, source_name: str) -> int:
        if not self.is_connected or not self.client:
            return -1
        try:
            response = self.client.call(requests.GetSceneItemId(sceneName=scene_name, sourceName=source_name))
            item_id = response.getSceneItemId()
            return item_id
        except Exception as e:
            logger.error(f"Không tìm thấy item '{source_name}' trong scene '{scene_name}': {e}")
            return -1

    def set_source_visibility(self, scene_name: str, source_name: str, visible: bool) -> bool:
        """Bật hoặc tắt hiển thị một source trong một scene (gửi qua hàng đợi)."""
        return self._execute_queued(self._set_source_visibility_impl, scene_name, source_name, visible)

    def _set_source_visibility_impl(self, scene_name: str, source_name: str, visible: bool) -> bool:
        if not self.is_connected or not self.client:
            logger.warning("Chưa kết nối OBS WebSocket.")
            return False
        try:
            item_id = self._get_scene_item_id_impl(scene_name, source_name)
            if item_id == -1:
                return False
            
            self.client.call(requests.SetSceneItemEnabled(
                sceneName=scene_name,
                sceneItemId=item_id,
                sceneItemEnabled=visible
            ))
            logger.info(f"Đã đặt hiển thị source '{source_name}' trong '{scene_name}' thành: {visible}")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi đặt hiển thị source '{source_name}': {e}")
            return False

    def update_text_source(self, source_name: str, text: str) -> bool:
        """Cập nhật nội dung văn bản của một Text Source (gửi qua hàng đợi)."""
        return self._execute_queued(self._update_text_source_impl, source_name, text)

    def _update_text_source_impl(self, source_name: str, text: str) -> bool:
        if not self.is_connected or not self.client:
            logger.warning("Chưa kết nối OBS WebSocket.")
            return False
        try:
            self.client.call(requests.SetInputSettings(
                inputName=source_name,
                inputSettings={"text": text},
                overlay=True
            ))
            logger.info(f"Đã cập nhật Text Source '{source_name}' thành: '{text}'")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi cập nhật Text Source '{source_name}': {e}")
            return False

    def start_replay_buffer(self) -> bool:
        """Bật tính năng Replay Buffer (gửi qua hàng đợi)."""
        return self._execute_queued(self._start_replay_buffer_impl)

    def _start_replay_buffer_impl(self) -> bool:
        if not self.is_connected or not self.client:
            return False
        try:
            self.client.call(requests.StartReplayBuffer())
            logger.info("🎬 Đã bật Replay Buffer trong OBS.")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi bật Replay Buffer: {e}")
            return False

    def save_replay_buffer(self) -> bool:
        """Lưu video từ Replay Buffer (gửi qua hàng đợi)."""
        return self._execute_queued(self._save_replay_buffer_impl)

    def _save_replay_buffer_impl(self) -> bool:
        if not self.is_connected or not self.client:
            return False
        try:
            self.client.call(requests.SaveReplayBuffer())
            logger.info("📸 Đã lưu thành công Replay Buffer (Highlight clip) trong OBS!")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi lưu Replay Buffer: {e}")
            return False

    def stop_replay_buffer(self) -> bool:
        """Tắt tính năng Replay Buffer (gửi qua hàng đợi)."""
        return self._execute_queued(self._stop_replay_buffer_impl)

    def _stop_replay_buffer_impl(self) -> bool:
        if not self.is_connected or not self.client:
            return False
        try:
            self.client.call(requests.StopReplayBuffer())
            logger.info("🎬 Đã tắt Replay Buffer trong OBS.")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi tắt Replay Buffer: {e}")
            return False
