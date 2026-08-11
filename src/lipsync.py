import wave
import numpy as np
import os
import logging

logger = logging.getLogger("Lipsync")

def compute_amplitude_envelope(wav_path: str, frame_ms: int = 50) -> list[float]:
    """Phân tích và tính toán envelope biên độ của tệp tin âm thanh WAV.
    Trả về danh sách các giá trị MouthOpen đã chuẩn hóa trong khoảng 0.0 - 1.0.
    """
    if not wav_path or not os.path.exists(wav_path):
        return []
        
    try:
        with wave.open(wav_path, 'rb') as wf:
            rate = wf.getframerate()
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            n_frames = wf.getnframes()
            
            if n_frames == 0:
                return []
                
            # Đọc toàn bộ frame bytes
            raw_data = wf.readframes(n_frames)
            
            # Chọn kiểu dữ liệu phù hợp theo sample width
            if sampwidth == 1:
                dtype = np.uint8
            elif sampwidth == 2:
                dtype = np.int16
            elif sampwidth == 4:
                dtype = np.int32
            else:
                logger.warning(f"Định dạng sample width {sampwidth} không được hỗ trợ để tính lipsync.")
                return []
                
            frames = np.frombuffer(raw_data, dtype=dtype)
            
            # Nếu có nhiều kênh, chỉ lấy kênh đầu tiên (mono-like)
            if n_channels > 1 and len(frames) > 0:
                frames = frames[0::n_channels]
                
        # Tính kích thước cửa sổ phân tích (ví dụ: 50ms)
        frame_size = int(rate * frame_ms / 1000)
        envelope = []
        
        # Chuyển đổi dữ liệu sang float32 để tính RMS tránh overflow
        frames_float = frames.astype(np.float32)
        
        for i in range(0, len(frames_float), frame_size):
            chunk = frames_float[i:i+frame_size]
            if len(chunk) == 0:
                continue
                
            # RMS = Root Mean Square (Độ lệch căn quân phương) đại diện cho biên độ
            rms = np.sqrt(np.mean(chunk ** 2))
            
            # Chuẩn hóa về khoảng 0.0 - 1.0 (8000.0 là ngưỡng biên độ thông thường của giọng đọc)
            normalized = min(rms / 8000.0, 1.0)
            
            # Khuếch đại nhẹ khẩu hình để biểu cảm chân thực hơn
            if normalized > 0.05:
                normalized = min(normalized * 1.5, 1.0)
                
            envelope.append(normalized)
            
        logger.info(f"Tính toán lipsync thành công cho file {wav_path}: {len(envelope)} frames")
        return envelope
        
    except Exception as e:
        logger.error(f"Lỗi khi tính toán amplitude envelope cho file {wav_path}: {e}")
        return []
