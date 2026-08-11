import os
import asyncio
import logging
import threading
import time
import tempfile
import edge_tts
import pygame
from typing import Callable, Optional
from src.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TTSEngine")

class TTSEngine:
    def __init__(self):
        self.voice = Config.TTS_VOICE
        self.temp_dir = os.path.join(tempfile.gettempdir(), "autolive_tts")
        os.makedirs(self.temp_dir, exist_ok=True)
        self._init_pygame()
        self.current_thread: Optional[threading.Thread] = None
        self.is_playing = False
        self._cleanup_temp_files()
        
        # Cấu hình Voice Cloning cục bộ (XTTS v2)
        self.use_local_xtts = os.getenv("USE_LOCAL_XTTS", "False").lower() == "true"
        self.xtts_speaker_wav = os.getenv("XTTS_SPEAKER_WAV", "resources/speaker.wav")
        self.xtts_language = os.getenv("XTTS_LANGUAGE", "vi")
        self.xtts_model = None
        
        if self.use_local_xtts:
            self._init_xtts()

    def _init_xtts(self):
        """Khởi tạo mô hình XTTS v2 local sử dụng PyTorch và thư viện TTS."""
        try:
            import torch
            from TTS.api import TTS
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Đang tải mô hình Voice Cloning XTTS v2 cục bộ trên thiết bị: {device}...")
            
            # Tự động tải và nạp mô hình XTTS v2
            self.xtts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
            self.xtts_model.to(device)
            logger.info("Tải mô hình XTTS v2 cục bộ thành công!")
        except Exception as e:
            logger.warning(f"Không thể khởi tạo XTTS v2 cục bộ ({e}). Hệ thống tự động chuyển sang fallback edge-tts (Cloud).")
            self.use_local_xtts = False
            self.xtts_model = None

    def _init_pygame(self):
        """Khởi tạo thư viện pygame.mixer để phát âm thanh."""
        try:
            pygame.mixer.init()
            logger.info("Khởi tạo Pygame Mixer thành công!")
        except Exception as e:
            logger.error(f"Lỗi khởi tạo Pygame Mixer: {e}")

    def _cleanup_temp_files(self):
        """Xóa các file âm thanh tạm thời từ lần chạy trước."""
        for file in os.listdir(self.temp_dir):
            if file.endswith(".mp3") or file.endswith(".wav"):
                try:
                    os.remove(os.path.join(self.temp_dir, file))
                except Exception:
                    pass

    async def _generate_audio(self, text: str, output_path: str, rate: str = "+0%", pitch: str = "+0Hz") -> bool:
        """Sinh file âm thanh dựa trên cấu hình (XTTS v2 Local hoặc edge-tts Cloud)."""
        # Thử sinh âm thanh bằng XTTS v2 cục bộ nếu được kích hoạt
        if self.use_local_xtts and self.xtts_model:
            try:
                if not os.path.exists(self.xtts_speaker_wav):
                    logger.warning(f"Không tìm thấy mẫu giọng tham chiếu: {self.xtts_speaker_wav}. Fallback sang edge-tts.")
                    raise FileNotFoundError(f"Speaker WAV missing: {self.xtts_speaker_wav}")
                
                logger.info(f"Đang sinh giọng đọc bằng XTTS v2 cục bộ (Giọng mẫu: {self.xtts_speaker_wav})...")
                
                # Chạy inference đồng bộ của XTTS trong thread executor của loop để tránh chặn async loop
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None,
                    self.xtts_model.tts_to_file,
                    text,
                    None,
                    self.xtts_language,
                    self.xtts_speaker_wav,
                    output_path
                )
                logger.info("Sinh giọng nói bằng XTTS v2 thành công!")
                return True
            except Exception as e:
                logger.error(f"Lỗi sinh audio bằng XTTS v2: {e}. Hệ thống tự động chuyển sang fallback edge-tts (Cloud).")
                # Chuyển sang đuôi .mp3 cho edge-tts nếu file ra là .wav
                if output_path.endswith(".wav"):
                    output_path = output_path[:-4] + ".mp3"
                
        # Trình fallback sử dụng Microsoft edge-tts (Cloud)
        try:
            communicate = edge_tts.Communicate(text, self.voice, rate=rate, pitch=pitch)
            await communicate.save(output_path)
            return True
        except Exception as e:
            logger.error(f"Lỗi sinh audio từ edge-tts: {e}")
            return False

    def _play_audio_thread(self, text: str, on_start: Optional[Callable], on_finished: Optional[Callable], rate: str = "+0%", pitch: str = "+0Hz"):
        """Hàm chạy trong thread riêng để sinh và phát âm thanh."""
        if not self.is_playing:
            if on_finished:
                on_finished()
            return
            
        # Chọn đuôi file tạm phù hợp (.wav cho XTTS, .mp3 cho edge-tts)
        is_using_xtts = self.use_local_xtts and self.xtts_model is not None
        ext = ".wav" if is_using_xtts else ".mp3"
        temp_file = os.path.join(self.temp_dir, f"tts_{int(time.time() * 1000)}{ext}")
        
        # Chạy tác vụ bất đồng bộ sinh audio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(self._generate_audio(text, temp_file, rate=rate, pitch=pitch))
        loop.close()

        if not self.is_playing:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception:
                pass
            if on_finished:
                on_finished()
            return

        # Nếu sinh thất bại, hãy thử tìm file tạm dự phòng (có thể đuôi bị đổi sang .mp3 do fallback trong _generate_audio)
        if not success or not os.path.exists(temp_file):
            fallback_mp3 = temp_file.replace(".wav", ".mp3")
            if os.path.exists(fallback_mp3):
                temp_file = fallback_mp3
                success = True
            else:
                self.is_playing = False
                if on_finished:
                    on_finished()
                return

        if not self.is_playing:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception:
                pass
            if on_finished:
                on_finished()
            return

        if on_start:
            try:
                # Thử truyền đường dẫn file âm thanh vừa sinh (để hỗ trợ lipsync thật)
                on_start(temp_file)
            except TypeError:
                on_start()

        try:
            # Dừng nhạc đang phát (nếu có)
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()

            # Tải và phát file mới
            pygame.mixer.music.load(temp_file)
            pygame.mixer.music.play()
            
            logger.info(f"Đang phát giọng đọc: '{text}'")
            
            # Đợi cho tới khi phát xong
            while pygame.mixer.music.get_busy() and self.is_playing:
                time.sleep(0.1)
                
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            
        except Exception as e:
            logger.error(f"Lỗi khi phát âm thanh: {e}")
        finally:
            self.is_playing = False
            # Cố gắng xóa file tạm
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception:
                pass
            
            if on_finished:
                on_finished()

    def speak(self, text: str, on_start: Optional[Callable] = None, on_finished: Optional[Callable] = None, rate: str = "+0%", pitch: str = "+0Hz"):
        """Phát giọng đọc của đoạn text (không chặn luồng chính)."""
        if not text:
            return

        # Dừng luồng phát hiện tại nếu có
        self.stop()
        self.is_playing = True

        # Tạo thread mới
        self.current_thread = threading.Thread(
            target=self._play_audio_thread,
            args=(text, on_start, on_finished, rate, pitch),
            daemon=True
        )
        self.current_thread.start()

    def stop(self):
        """Dừng phát âm thanh ngay lập tức."""
        self.is_playing = False
        try:
            if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
        except Exception as e:
            logger.error(f"Lỗi khi dừng phát âm thanh: {e}")
        
        if self.current_thread and self.current_thread.is_alive():
            self.current_thread.join(timeout=0.5)
            self.current_thread = None
