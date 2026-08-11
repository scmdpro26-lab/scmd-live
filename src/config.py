import os
from dotenv import load_dotenv

# Load environmental variables from .env file
load_dotenv()

class Config:
    # Gemini Configuration
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

    # OBS Configuration
    OBS_HOST = os.getenv("OBS_HOST", "127.0.0.1")
    OBS_PORT = int(os.getenv("OBS_PORT", "4455"))
    OBS_PASSWORD = os.getenv("OBS_PASSWORD", "")

    # TTS Configuration
    TTS_VOICE = os.getenv("TTS_VOICE", "vi-VN-HoaiMyNeural")

    # DB Path
    DB_PATH = "autolive.db"

    # VNyan Path
    VNYAN_EXE_PATH = os.getenv("VNYAN_EXE_PATH", "")
    AVATAR_VRM_PATH = os.getenv("AVATAR_VRM_PATH", "")

    # VMC / VNyan / VTube Studio Configuration
    VMC_IP = os.getenv("VMC_IP", "127.0.0.1")
    VMC_PORT = int(os.getenv("VMC_PORT", "39539"))
    REST_PORT = int(os.getenv("REST_PORT", "8069"))
    OSC_PORT = int(os.getenv("OSC_PORT", "39539"))
    VMC_FEEDBACK_PORT = int(os.getenv("VMC_FEEDBACK_PORT", "39540"))


    @classmethod
    def is_gemini_configured(cls) -> bool:

        return bool(cls.GEMINI_API_KEY) and cls.GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE"
