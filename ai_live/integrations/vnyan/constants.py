DEFAULT_IP = "127.0.0.1"
DEFAULT_VMC_PORT = 39539
DEFAULT_REST_PORT = 8069
DEFAULT_WS_PORT = 8005

# Các ứng viên cấu hình biểu cảm phục vụ scoring của VRM Inspector
EXPRESSION_CANDIDATES = {
    "viseme_a": ["aa", "a", "viseme_a", "v_aa", "mouthopen", "vrc.v_aa"],
    "viseme_e": ["ee", "e", "viseme_e", "v_ee", "vrc.v_ee"],
    "viseme_i": ["ih", "i", "viseme_i", "v_ih", "vrc.v_ih"],
    "viseme_o": ["oh", "o", "viseme_o", "v_oh", "vrc.v_oh"],
    "viseme_u": ["ou", "u", "viseme_u", "v_u", "vrc.v_u"],
    
    "happy": ["happy", "joy", "fun", "laugh"],
    "sad": ["sad", "sorrow", "depressed"],
    "angry": ["angry", "anger", "rage"],
    "surprised": ["surprised", "surprise", "shocked"],
    "relaxed": ["relaxed", "relax", "calm"],
    "neutral": ["neutral", "idle", "default"],
    
    "blink": ["blink", "closeeyes", "eyeclose"],
    "blink_left": ["blinkleft", "eyecloseleft", "blink_l", "blink_left"],
    "blink_right": ["blinkright", "eyecloseright", "blink_r", "blink_right"]
}

# Danh mục Action duy nhất đồng bộ giữa AI Live và VNyan
CANONICAL_ACTIONS = {
    # --- 10 actions cốt lõi (giữ nguyên) ---
    "greeting": "Greeting",
    "clap": "Clap",
    "heart": "Heart",
    "point_up": "PointUp",
    "dance": "Dance",
    "apology": "Apology",
    "voucher_drop": "VoucherDrop",
    "minigame_start": "MinigameStart",
    "cart_pin": "CartPin",
    "checkout_success": "CheckoutSuccess",
    # --- 5 actions e-commerce mới (thêm mới, không thay thế cũ) ---
    "point_down": "PointDown",
    "present_left": "PresentLeft",
    "present_right": "PresentRight",
    "celebrate": "Celebrate",
    "voucher_show": "VoucherShow",
}

