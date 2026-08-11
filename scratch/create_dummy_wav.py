import os
import wave
import struct

def main():
    resources_dir = "resources"
    os.makedirs(resources_dir, exist_ok=True)
    wav_path = os.path.join(resources_dir, "speaker.wav")
    
    print(f"Creating dummy silent WAV at: {wav_path}...")
    with wave.open(wav_path, 'wb') as wav_file:
        # Mono, 2 bytes/sample, 22050Hz sample rate (XTTS uses 22050Hz or 24000Hz)
        wav_file.setparams((1, 2, 22050, 0, 'NONE', 'not compressed'))
        # 1 second of silence
        for _ in range(22050):
            wav_file.writeframes(struct.pack('<h', 0))
    print("Dummy WAV created successfully.")

if __name__ == "__main__":
    main()
