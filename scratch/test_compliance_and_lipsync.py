import os
import sys
import wave
import numpy as np
import asyncio
import sqlite3

# Thêm đường dẫn gốc của project vào sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.compliance_engine import get_policy, VoiceMode, COMPLIANCE_MATRIX
from src.teleprompter import TeleprompterService
import src.database as db
from src.lipsync import compute_amplitude_envelope
from src.vmc_service import get_vmc_client
from src.priority_queue import PriorityQueueProcessor

# Mock Objects for Testing
class MockOBS:
    def __init__(self):
        self.is_connected = True
        self.visible_sources = {}
        
    def set_source_visibility(self, scene, source, visible):
        self.visible_sources[source] = visible

class MockTTS:
    def __init__(self):
        self.last_spoken = None
        self.on_start_cb = None
        self.on_finished_cb = None
        
    def speak(self, text, on_start=None, on_finished=None, rate="+0%", pitch="+0Hz"):
        self.last_spoken = text
        self.on_start_cb = on_start
        self.on_finished_cb = on_finished
        # Thực thi callback giả lập
        if on_start:
            on_start()
        if on_finished:
            on_finished()

def generate_mock_wav(path, duration_sec=1, sample_rate=16000):
    """Tạo file wav giả lập với tín hiệu hình sin để test lipsync."""
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
    # Tín hiệu hình sin có tần số 440Hz (nốt La)
    data = np.sin(2 * np.pi * 440 * t) * 10000  # Amplitude
    data = data.astype(np.int16)
    
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(data.tobytes())

async def run_tests():
    print("=== BẮT ĐẦU CHẠY THỬ NGHIỆM COMPLIANCE & LIPSYNC ===")
    
    # 1. Test Policy Resolution
    print("\n--- 1. Kiểm tra phân loại chính sách tuân thủ ---")
    tiktok_policy = get_policy("TikTok")
    assert tiktok_policy.voice_mode == VoiceMode.AI_TTS_AVATAR
    assert tiktok_policy.max_avatar_screen_ratio == 1.0
    print("✅ Xác thực chính sách TikTok (Việt Nam) thành công!")
    
    tiktok_us_policy = get_policy("TikTok_US")
    assert tiktok_us_policy.voice_mode == VoiceMode.AI_COPILOT_HUMAN
    assert tiktok_us_policy.max_avatar_screen_ratio == 0.45
    print("✅ Xác thực chính sách TikTok (Mỹ) thành công!")
    
    facebook_policy = get_policy("Facebook")
    assert facebook_policy.voice_mode == VoiceMode.AI_TTS_AVATAR
    assert facebook_policy.require_ai_disclosure_label is True
    print("✅ Xác thực chính sách Facebook thành công!")
    
    # Fail-safe check
    unknown_policy = get_policy("UnknownPlatform")
    assert unknown_policy.platform == "TikTok"  # Fallback to strictest
    print("✅ Cơ chế fail-safe (fallback sang TikTok Shop) hoạt động chính xác!")
    
    # 2. Test Teleprompter
    print("\n--- 2. Kiểm tra dịch vụ nhắc chữ Teleprompter ---")
    lines_received = []
    def prompter_callback(text):
        lines_received.append(text)
        
    prompter = TeleprompterService(on_new_line_callback=prompter_callback)
    prompter.push_line("Xin chào cả nhà đang xem live")
    prompter.push_line("Hôm nay shop có rất nhiều deal hot")
    
    assert len(prompter.get_all()) == 2
    assert lines_received == ["Xin chào cả nhà đang xem live", "Hôm nay shop có rất nhiều deal hot"]
    assert prompter.pop_next() == "Xin chào cả nhà đang xem live"
    assert len(prompter.get_all()) == 1
    print("✅ Teleprompter hoạt động đúng thiết kế hàng đợi và kích hoạt callback thành công!")
    
    # 3. Test Gating trong Priority Queue Processor
    print("\n--- 3. Kiểm tra cơ chế Gating điều phối phát ngôn theo chính sách ---")
    mock_obs = MockOBS()
    mock_tts = MockTTS()
    
    # Khởi tạo db và tạo bảng tạm
    db.init_db()
    
    processor = PriorityQueueProcessor(
        ai_brain=None,
        tts_engine=mock_tts,
        obs_client=mock_obs
    )
    
    # Test TikTok_US: AI_COPILOT_HUMAN
    processor._dispatch_speech("TikTok_US", "Khách mua hàng vui lòng nhấn nút giỏ hàng", "+0%", "+0Hz", "Joy")
    assert mock_tts.last_spoken is None  # TikTok_US không được phát TTS
    assert processor.teleprompter.pop_next() == "Khách mua hàng vui lòng nhấn nút giỏ hàng"
    print("✅ TikTok_US gating: Lời thoại chuyển vào Teleprompter thay vì phát TTS!")
    
    # Test Facebook: AI_TTS_AVATAR
    processor._dispatch_speech("Facebook", "Chào bạn Nguyễn Văn A nhé!", "+0%", "+0Hz", "Joy")
    assert mock_tts.last_spoken == "Chào bạn Nguyễn Văn A nhé!"
    print("✅ Facebook gating: Phát trực tiếp qua TTS và cử chỉ MC ảo!")
    
    # 4. Test Amplitude Envelope Lipsync
    print("\n--- 4. Kiểm tra phân tích Lipsync envelope từ audio thực tế ---")
    wav_path = "scratch/temp_test_speech.wav"
    generate_mock_wav(wav_path, duration_sec=0.5)
    
    envelope = compute_amplitude_envelope(wav_path, frame_ms=50)
    assert len(envelope) > 0
    assert all(0.0 <= val <= 1.0 for val in envelope)
    # File mock sinh hình sin liên tục nên RMS sẽ đều
    print(f"✅ Đã tính toán envelope từ file wav. Số frame: {len(envelope)}. Trị số mẫu đầu tiên: {envelope[0]:.4f}")
    
    # Cleanup temp wav
    if os.path.exists(wav_path):
        os.remove(wav_path)
        
    # VMC singleton check
    vmc_1 = get_vmc_client()
    vmc_2 = get_vmc_client()
    assert vmc_1 is vmc_2
    print("✅ VMC Client tuân thủ mô hình Singleton duy nhất!")
    
    # 5. Test Stream Session Database
    print("\n--- 5. Kiểm tra phiên lưu trữ định danh người chịu trách nhiệm (Luật 1/7/2026) ---")
    session_id = db.start_stream_session("TikTok", "Nguyễn Văn A", "CCCD-123456", "ai_copilot_human")
    assert session_id > 0
    
    # Truy vấn lại database xem đã lưu đúng chưa
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stream_sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    assert row is not None
    assert row["responsible_person_name"] == "Nguyễn Văn A"
    assert row["platform"] == "TikTok"
    assert row["voice_mode"] == "ai_copilot_human"
    conn.close()
    
    db.end_stream_session(session_id)
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ended_at FROM stream_sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    assert row["ended_at"] is not None
    conn.close()
    print("✅ Khai báo danh tính phiên live và audit log lưu trữ trong DB thành công!")
    
    print("\n🎉 TẤT CẢ CÁC BÀI KIỂM THỬ ĐÃ ĐẠT ĐẦU RA MONG MUỐN! KHÔNG CÓ LỖI CRASH.")
    sys.exit(0)

if __name__ == "__main__":
    asyncio.run(run_tests())
