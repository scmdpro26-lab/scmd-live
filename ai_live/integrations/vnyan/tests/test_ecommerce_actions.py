import unittest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from ai_live.integrations.vnyan.bridge.installer import NodeGraphInstaller
from ai_live.integrations.vnyan.detector import VNyanDetector
from src.vmc_client import VMCClient
from ai_live.integrations.vnyan.controllers.animation import AnimationController


class TestEcommerceActionsAndBlending(unittest.TestCase):
    def setUp(self):
        self.detector = VNyanDetector()
        self.installer = NodeGraphInstaller(self.detector)

    def test_ecommerce_action_methods_exist_in_vmc_client(self):
        """Xác minh 5 action e-commerce mới có method tương ứng trong VMCClient."""
        methods = [
            "trigger_point_down",
            "trigger_present_left",
            "trigger_present_right",
            "trigger_celebrate",
            "trigger_voucher_show"
        ]
        for m in methods:
            self.assertTrue(
                hasattr(VMCClient, m),
                f"VMCClient thiếu method: {m}"
            )

    def test_ecommerce_action_methods_exist_in_animation_controller(self):
        """Xác minh 5 action e-commerce mới có method tương ứng trong AnimationController."""
        methods = [
            "trigger_point_down",
            "trigger_present_left",
            "trigger_present_right",
            "trigger_celebrate",
            "trigger_voucher_show"
        ]
        for m in methods:
            self.assertTrue(
                hasattr(AnimationController, m),
                f"AnimationController thiếu method: {m}"
            )

    def test_blend_configuration_for_sitting_prevention(self):
        """Xác minh cấu hình blend của từng động tác để chống lỗi MC bị ngồi xuống."""
        # 1. Định nghĩa mock clips trong file BasicMotions pack
        mock_clips = {
            "basicmotions": {
                "touchgrass": "TouchGrass",
                "basicmotions@clap01": "BasicMotions@Clap01",
                "gangnam": "Gangnam",
                "sittingcrosslegged": "sittingcrosslegged"
            }
        }

        # 2. Mock _discover_animation để trả về hoạt ảnh tương ứng
        def mock_discover(action, exists):
            mapping = {
                "Greeting": "TouchGrass (BasicMotions)",
                "Clap": "BasicMotions@Clap01 (BasicMotions)",
                "Heart": "BasicMotions@Clap01 (BasicMotions)",
                "PointUp": "BasicMotions@Clap01 (BasicMotions)",
                "Dance": "Gangnam (BasicMotions)",
                "Apology": "TouchGrass (BasicMotions)",
                "PointDown": "BasicMotions@Clap01 (BasicMotions)",
                "PresentLeft": "TouchGrass (BasicMotions)",
                "PresentRight": "TouchGrass (BasicMotions)",
                "Celebrate": "Gangnam (BasicMotions)",
                "VoucherShow": "BasicMotions@Clap01 (BasicMotions)",
            }
            return mapping.get(action, "ACTION_UNBOUND")

        # 3. Tạo mock redeems.json data và chạy cài đặt node
        mock_redeems = {"nodes": [], "connections": []}
        
        # Tạo mock directory
        mock_dir = Path("scratch/mock_config")
        mock_dir.mkdir(parents=True, exist_ok=True)
        redeems_file = mock_dir / "redeems.json"
        with open(redeems_file, "w", encoding="utf-8") as f:
            json.dump(mock_redeems, f)
            
        with patch.object(self.detector, "get_config_dir", return_value=mock_dir):
            with patch.object(self.detector, "detect_vnyan_exe", return_value=mock_dir / "VNyan.exe"):
                with patch.object(self.installer, "_discover_animation", side_effect=mock_discover):
                    # Lấy danh sách actions để chạy tạo nodes
                    canonical_actions = [
                        "Greeting", "Clap", "Heart", "PointUp", "Dance", "Apology",
                        "VoucherDrop", "MinigameStart", "CartPin", "CheckoutSuccess",
                        "PointDown", "PresentLeft", "PresentRight", "Celebrate", "VoucherShow"
                    ]
                    
                    # Chạy cài đặt thực tế trên file redeems mock
                    self.installer.manifest_path = Path("scratch/mock_manifest.json")
                    self.installer.install_ai_live_bridge()
                    
                    # Đọc lại file redeems sau khi installer ghi đè
                    with open(redeems_file, "r", encoding="utf-8") as f:
                        written_data = json.load(f)
                    nodes = written_data.get("nodes", [])
                    
                    # Lọc các PlayAnimNode
                    play_nodes = [n for n in nodes if n.get("path") == "Nodes/PlayAnimNode"]
                    self.assertEqual(len(play_nodes), len(canonical_actions))


                        
                    # Kiểm tra blend settings của từng node để chống regression "all actions -> Sit"
                    for node in play_nodes:
                        # Lấy tên và các blend value
                        vals = {v["key"]: v["value"] for v in node.get("values", [])}
                        anim_name = vals.get("name")
                        
                        # Tìm action tương ứng dựa trên anim_name
                        action = None
                        for act in canonical_actions:
                            if mock_discover(act, True) == anim_name:
                                action = act
                                break
                        
                        self.assertIsNotNone(action, f"Không tìm thấy action cho anim: {anim_name}")
                        
                        # Kiểm chứng logic blend
                        if action in ["Dance", "Celebrate"]:
                            # Nhảy múa: hông = 0 (chống sụp), chân = 1 (nhảy chân)
                            self.assertEqual(vals.get("blendHipPos"), "0", f"{action} blendHipPos phải là 0")
                            self.assertEqual(vals.get("blendRoot"), "0", f"{action} blendRoot phải là 0")
                            self.assertEqual(vals.get("blendLeftLeg"), "1", f"{action} blendLeftLeg phải là 1")
                            self.assertEqual(vals.get("blendRightLeg"), "1", f"{action} blendRightLeg phải là 1")
                        else:
                            # Các cử chỉ đứng: hông/chân = 0 (chống quỳ/sụp/ngồi)
                            self.assertEqual(vals.get("blendHipPos"), "0", f"{action} blendHipPos phải là 0")
                            self.assertEqual(vals.get("blendRoot"), "0", f"{action} blendRoot phải là 0")
                            self.assertEqual(vals.get("blendLeftLeg"), "0", f"{action} blendLeftLeg phải là 0")
                            self.assertEqual(vals.get("blendRightLeg"), "0", f"{action} blendRightLeg phải là 0")
                            
                        # Thân trên luôn phải bật để múa tay/lưng
                        self.assertEqual(vals.get("blendHead"), "1")
                        self.assertEqual(vals.get("blendNeck"), "1")
                        self.assertEqual(vals.get("blendSpine"), "1")
                        self.assertEqual(vals.get("blendRightArm"), "1")
                        self.assertEqual(vals.get("blendLeftArm"), "1")


        print("-> Unit test anti-regression: PASSED!")

    def test_single_transport_priority_http_success(self):
        """Xác minh khi HTTP REST gửi thành công, VMC UDP không được kích hoạt."""
        mock_vmc = MagicMock()
        mock_bridge = MagicMock()
        mock_bridge.send.return_value = True
        
        controller = AnimationController(vmc=mock_vmc, bridge=mock_bridge)
        
        # Kích hoạt thử với Action ID đã chuẩn hóa
        success = controller.trigger_animation("AI_LIVE_DANCE", ["VIP_Product"])
        
        self.assertTrue(success)
        mock_bridge.send.assert_called_once_with("AI_LIVE_DANCE", {"text1": "VIP_Product"})
        mock_vmc.send_trigger.assert_not_called()

    def test_single_transport_priority_http_failure_fallback_udp(self):
        """Xác minh khi HTTP REST gặp lỗi/thất bại, VMC UDP được gọi làm fallback."""
        mock_vmc = MagicMock()
        mock_vmc.send_trigger.return_value = True
        mock_bridge = MagicMock()
        
        # Case A: Bridge.send trả về False
        mock_bridge.send.return_value = False
        controller = AnimationController(vmc=mock_vmc, bridge=mock_bridge)
        success = controller.trigger_animation("AI_LIVE_DANCE", ["VIP_Product"])
        
        self.assertTrue(success)
        mock_bridge.send.assert_called_once_with("AI_LIVE_DANCE", {"text1": "VIP_Product"})
        mock_vmc.send_trigger.assert_called_once_with("AI_LIVE_DANCE", ["VIP_Product"])
        
        # Case B: Bridge.send ném Exception
        mock_bridge.send.reset_mock()
        mock_vmc.send_trigger.reset_mock()
        mock_bridge.send.side_effect = Exception("Connection Timeout")
        
        success = controller.trigger_animation("AI_LIVE_DANCE", ["VIP_Product"])
        self.assertTrue(success)
        mock_bridge.send.assert_called_once_with("AI_LIVE_DANCE", {"text1": "VIP_Product"})
        mock_vmc.send_trigger.assert_called_once_with("AI_LIVE_DANCE", ["VIP_Product"])


    def test_action_engine_priority_web_interrupts_speech(self):
        """Xác minh cử chỉ WEB có ưu tiên cao hơn và ngắt cử chỉ SPEECH."""
        from src.action_engine import ActionEngine, ActionSource
        
        mock_controller = MagicMock()
        mock_controller.trigger_animation.return_value = (True, "HTTP")
        
        # Reset ActionEngine singleton state
        engine = ActionEngine()
        engine.set_controller(mock_controller)
        engine.last_action_time = 0.0
        engine.current_source = None
        engine.current_action = None
        
        # 1. Phát cử chỉ SPEECH (1)
        res1 = engine.dispatch("dance", ActionSource.SPEECH)
        self.assertTrue(res1)
        self.assertEqual(engine.current_source, ActionSource.SPEECH)
        
        # 2. Phát cử chỉ WEB (3) lập tức -> Được phép ngắt
        res2 = engine.dispatch("greeting", ActionSource.WEB)
        self.assertTrue(res2)
        self.assertEqual(engine.current_source, ActionSource.WEB)
        self.assertEqual(engine.current_action, "AI_LIVE_GREETING")

    def test_action_engine_priority_speech_ignored_during_web(self):
        """Xác minh cử chỉ SPEECH bị bỏ qua khi cử chỉ WEB đang hoạt động."""
        from src.action_engine import ActionEngine, ActionSource
        import time
        
        mock_controller = MagicMock()
        mock_controller.trigger_animation.return_value = (True, "HTTP")
        
        engine = ActionEngine()
        engine.set_controller(mock_controller)
        engine.last_action_time = time.time()
        engine.current_source = ActionSource.WEB
        engine.current_action = "AI_LIVE_GREETING"
        
        # Cử chỉ SPEECH phát lập tức sẽ bị từ chối
        res = engine.dispatch("dance", ActionSource.SPEECH)
        self.assertFalse(res)

    def test_action_engine_cooldown_speech(self):
        """Xác minh cooldown 1 giây của cử chỉ SPEECH."""
        from src.action_engine import ActionEngine, ActionSource
        import time
        
        mock_controller = MagicMock()
        mock_controller.trigger_animation.return_value = (True, "HTTP")
        
        engine = ActionEngine()
        engine.set_controller(mock_controller)
        engine.last_action_time = time.time()
        engine.current_source = ActionSource.SPEECH
        engine.current_action = "AI_LIVE_DANCE"
        
        # Gửi cử chỉ SPEECH mới lập tức -> Bị block do cooldown
        res = engine.dispatch("greeting", ActionSource.SPEECH)
        self.assertFalse(res)

    def test_action_engine_deduplication_speech(self):
        """Xác minh lọc trùng lặp liên tiếp của SPEECH trong 3 giây."""
        from src.action_engine import ActionEngine, ActionSource
        import time
        
        mock_controller = MagicMock()
        mock_controller.trigger_animation.return_value = (True, "HTTP")
        
        engine = ActionEngine()
        engine.set_controller(mock_controller)
        engine.last_action_time = time.time() - 1.5  # Hết cooldown 1s nhưng chưa hết deduplicate 3s
        engine.current_source = ActionSource.SPEECH
        engine.last_action_name = "AI_LIVE_DANCE"
        engine.current_action = "AI_LIVE_DANCE"
        
        # Gửi lại trùng "dance" -> Bị block do trùng lặp (deduplicate 3s)
        res1 = engine.dispatch("dance", ActionSource.SPEECH)
        self.assertFalse(res1)
        
        # Gửi cử chỉ khác có ưu tiên cao hơn "point_down" (P2 > P3) -> Thành công
        res2 = engine.dispatch("point_down", ActionSource.SPEECH)
        self.assertTrue(res2)



    def test_action_engine_normalization_valid(self):
        """Xác minh các dạng tên action hợp lệ đều được chuẩn hóa về AI_LIVE_ Action ID."""
        from src.action_engine import ActionEngine, ActionSource
        
        mock_controller = MagicMock()
        mock_controller.trigger_animation.return_value = (True, "HTTP")
        
        engine = ActionEngine()
        engine.set_controller(mock_controller)
        engine.last_action_time = 0.0
        engine.current_source = None
        engine.current_action = None
        
        # Test case 1: Lowercase key
        id1 = engine.normalize_to_canonical_id("point_down")
        self.assertEqual(id1, "AI_LIVE_POINT_DOWN")
        
        # Test case 2: PascalCase value
        id2 = engine.normalize_to_canonical_id("PointDown")
        self.assertEqual(id2, "AI_LIVE_POINT_DOWN")
        
        # Test case 3: Upper canonical string
        id3 = engine.normalize_to_canonical_id("AI_LIVE_POINT_DOWN")
        self.assertEqual(id3, "AI_LIVE_POINT_DOWN")

        # Test dispatch with normalization
        res = engine.dispatch("point_down", ActionSource.WEB)
        self.assertTrue(res)
        mock_controller.trigger_animation.assert_called_once_with("AI_LIVE_POINT_DOWN", [])

    def test_action_engine_normalization_invalid_rejected(self):
        """Xác minh các cử chỉ suy diễn lung tung hoặc không chính thống bị từ chối."""
        from src.action_engine import ActionEngine, ActionSource
        
        mock_controller = MagicMock()
        mock_controller.trigger_animation.return_value = (True, "HTTP")
        
        engine = ActionEngine()
        engine.set_controller(mock_controller)
        
        # Nhập các từ khóa bậy bạ / tự suy diễn
        invalid_actions = ["nhảy", "tim", "vẫy tay", "chào", "vỗ tay", "nhe răng"]
        
        for name in invalid_actions:
            self.assertIsNone(engine.normalize_to_canonical_id(name))
            res = engine.dispatch(name, ActionSource.WEB)
            self.assertFalse(res)
        
        mock_controller.trigger_animation.assert_not_called()

    def test_speech_gesture_parser_priority(self):
        """Xác minh rule có priority cao hơn thắng khi khớp đồng thời nhiều từ khóa."""
        from src.speech_gesture import SpeechGestureParser
        
        parser = SpeechGestureParser()
        parser._rules = [
            {"keywords": ["cảm ơn"], "action": "clap", "priority": 1, "confidence": 1.0},
            {"keywords": ["chốt đơn"], "action": "celebrate", "priority": 10, "confidence": 1.0}
        ]
        
        # Câu nói chứa cả "cảm ơn" và "chốt đơn"
        action = parser.find_gesture("Cảm ơn anh chị đã chốt đơn!")
        # "chốt đơn" có priority = 10 (cao hơn) nên celebrate phải thắng
        self.assertEqual(action, "celebrate")

    def test_speech_gesture_parser_context(self):
        """Xác minh cử chỉ được lọc đúng theo ngữ cảnh hoạt động (context)."""
        from src.speech_gesture import SpeechGestureParser
        
        parser = SpeechGestureParser()
        parser._rules = [
            {"keywords": ["voucher"], "action": "voucher_show", "context": ["sales"], "priority": 1},
            {"keywords": ["hello"], "action": "greeting", "context": ["default"], "priority": 1}
        ]
        
        # Ngữ cảnh mặc định: chỉ khớp "hello" -> greeting
        parser.current_context = "default"
        self.assertEqual(parser.find_gesture("hello các bạn"), "greeting")
        self.assertIsNone(parser.find_gesture("đây là voucher giảm giá"))
        
        # Đổi sang ngữ cảnh bán hàng (sales): chỉ khớp "voucher" -> voucher_show
        parser.current_context = "sales"
        self.assertEqual(parser.find_gesture("đây là voucher giảm giá"), "voucher_show")
        self.assertIsNone(parser.find_gesture("hello các bạn"))

    def test_speech_gesture_parser_low_confidence_rejected(self):
        """Xác minh cử chỉ bị từ chối nếu có điểm tin cậy (confidence) dưới 0.5."""
        from src.speech_gesture import SpeechGestureParser
        
        parser = SpeechGestureParser()
        parser._rules = [
            {"keywords": ["bên dưới"], "action": "point_down", "confidence": 0.3, "priority": 1}
        ]
        
        # Rule khớp nhưng confidence 0.3 < 0.5 nên bị bỏ qua
        action = parser.find_gesture("bên dưới giỏ hàng nhé")
        self.assertIsNone(action)

    def test_action_priority_p1_interrupts_p3(self):
        """Xác minh E-commerce event (P1) ngắt được cử chỉ Cosmetic (P3)."""
        from src.action_engine import ActionEngine, ActionSource
        
        mock_controller = MagicMock()
        mock_controller.trigger_animation.return_value = (True, "HTTP")
        
        engine = ActionEngine()
        engine.set_controller(mock_controller)
        engine.last_action_time = 0.0
        engine.current_source = None
        engine.current_action = None
        
        # 1. MC đang DANCE (P3)
        res1 = engine.dispatch("dance", ActionSource.AI_EVENT)
        self.assertTrue(res1)
        self.assertEqual(engine.current_action, "AI_LIVE_DANCE")
        
        # 2. CheckoutSuccess (P1) chen ngang lập tức (< 2.5s) -> Thành công
        res2 = engine.dispatch("checkout_success", ActionSource.AI_EVENT)
        self.assertTrue(res2)
        self.assertEqual(engine.current_action, "AI_LIVE_CHECKOUT_SUCCESS")

    def test_action_priority_p3_cannot_interrupt_p2(self):
        """Xác minh Cosmetic (P3) bị chặn khi AI speech directive (P2) đang chạy."""
        from src.action_engine import ActionEngine, ActionSource
        import time
        
        mock_controller = MagicMock()
        mock_controller.trigger_animation.return_value = (True, "HTTP")
        
        engine = ActionEngine()
        engine.set_controller(mock_controller)
        
        # Thiết lập MC đang chỉ tay xuống giỏ hàng POINT_DOWN (P2) cách đây 1.0 giây
        engine.last_action_time = time.time() - 1.0
        engine.current_source = ActionSource.AI_EVENT
        engine.current_action = "AI_LIVE_POINT_DOWN"
        
        # Gửi cử chỉ Cosmetic "Clap" (P3) -> Bị block (không thể ngắt P2)
        res = engine.dispatch("clap", ActionSource.AI_EVENT)
        self.assertFalse(res)

    def test_action_cooldown_same_action_same_source_dropped(self):
        """Xác minh same action + same source + trong cooldown window -> bị DROP."""
        from src.action_engine import ActionEngine, ActionSource
        import time
        
        mock_controller = MagicMock()
        mock_controller.trigger_animation.return_value = (True, "HTTP")
        
        engine = ActionEngine()
        engine.set_controller(mock_controller)
        engine.last_triggered = {}
        engine.last_action_time = 0.0
        engine.current_action = None
        
        # 1. Phát VoucherShow (cooldown 3.0s) từ SPEECH
        res1 = engine.dispatch("voucher_show", ActionSource.SPEECH)
        self.assertTrue(res1)
        
        # 2. Phát tiếp VoucherShow từ SPEECH sau 1.0 giây -> bị DROP
        engine.last_action_time = time.time() - 1.0  # Reset general time
        engine.last_triggered[("AI_LIVE_VOUCHER_SHOW", ActionSource.SPEECH)] = time.time() - 1.0
        
        res2 = engine.dispatch("voucher_show", ActionSource.SPEECH)
        self.assertFalse(res2)

    def test_action_cooldown_different_action_same_source_allowed(self):
        """Xác minh different action từ cùng nguồn vẫn được phát nếu không bị block priority."""
        from src.action_engine import ActionEngine, ActionSource
        import time
        
        mock_controller = MagicMock()
        mock_controller.trigger_animation.return_value = (True, "HTTP")
        
        engine = ActionEngine()
        engine.set_controller(mock_controller)
        engine.last_triggered = {}
        engine.last_action_time = time.time() - 3.0  # Đã hoàn thành visual
        engine.current_action = None
        
        # 1. Phát VoucherShow từ SPEECH
        res1 = engine.dispatch("voucher_show", ActionSource.SPEECH)
        self.assertTrue(res1)
        
        # Giả lập cử chỉ 1 chạy xong (lùi thời gian last_action_time về 3s trước)
        engine.last_action_time = time.time() - 3.0
        
        # 2. Phát Celebrate từ SPEECH ngay lập tức -> Cho phép (khác Action ID)
        res2 = engine.dispatch("celebrate", ActionSource.SPEECH)
        self.assertTrue(res2)

    def test_state_machine_transition_idle_playing_cooldown_idle(self):
        """Xác minh MC chuyển đổi từ IDLE -> PLAYING -> COOLDOWN -> IDLE dựa trên thời gian."""
        from src.action_engine import ActionEngine, ActionSource
        import time
        
        mock_controller = MagicMock()
        mock_controller.trigger_animation.return_value = (True, "HTTP")
        
        engine = ActionEngine()
        engine.set_controller(mock_controller)
        engine.last_triggered = {}
        engine.last_action_time = 0.0
        engine.current_action = None
        
        # 1. Ban đầu là IDLE
        self.assertEqual(engine.update_state(), "IDLE")
        
        # 2. Phát VoucherShow (duration: 3.0s, cooldown: 3.0s) -> PLAYING
        res = engine.dispatch("voucher_show", ActionSource.SPEECH)
        self.assertTrue(res)
        self.assertEqual(engine.state, "PLAYING")
        
        # 3. Sau 1.5 giây -> Vẫn đang PLAYING
        engine.last_action_time = time.time() - 1.5
        self.assertEqual(engine.update_state(), "PLAYING")
        
        # 4. Sau 3.5 giây (quá duration 3s) -> Chuyển sang COOLDOWN
        engine.last_action_time = time.time() - 3.5
        self.assertEqual(engine.update_state(), "COOLDOWN")
        
        # 5. Sau 6.5 giây (quá duration 3s + cooldown 3s) -> Chuyển về IDLE
        engine.last_action_time = time.time() - 6.5
        self.assertEqual(engine.update_state(), "IDLE")
        self.assertIsNone(engine.current_action)

    def test_state_machine_queueable_action(self):
        """Xác minh một action có queueable=True sẽ được hàng chờ queue tiếp nhận và tự động chạy sau."""
        from src.action_engine import ActionEngine, ActionSource
        import time
        
        mock_controller = MagicMock()
        mock_controller.trigger_animation.return_value = (True, "HTTP")
        
        engine = ActionEngine()
        engine.set_controller(mock_controller)
        engine.last_triggered = {}
        engine.last_action_time = time.time()
        engine.state = "PLAYING"
        engine.current_action = "AI_LIVE_VOUCHER_SHOW"  # VoucherShow (duration 3.0s, cooldown 3.0s)
        engine.queue = []
        
        # Tạo cấu hình custom có queueable=True cho test case này
        engine.ACTION_CONFIGS["AI_LIVE_DANCE"] = {
            "priority": 3, "interruptible": True, "queueable": True, "duration": 5.0, "cooldown": 5.0
        }
        
        # Phát Dance (P3 Cosmetic, queueable=True). Vì VoucherShow (P1) đang chạy nên Dance không thể cắt ngang.
        # Nhưng do queueable=True, nó được xếp vào hàng chờ.
        res = engine.dispatch("dance", ActionSource.SPEECH)
        self.assertFalse(res) # Trả về False vì không chạy ngay được
        self.assertEqual(len(engine.queue), 1)
        self.assertEqual(engine.queue[0][0], "AI_LIVE_DANCE")
        
        # Giả lập thời gian trôi qua 6.5 giây -> VoucherShow hoàn thành -> Chuyển về IDLE -> tự động Dequeue
        engine.last_action_time = time.time() - 6.5
        
        # Gọi update_state()
        state = engine.update_state()
        self.assertEqual(state, "PLAYING") # Trở lại PLAYING do Dance đã được tự động kích hoạt
        self.assertEqual(engine.current_action, "AI_LIVE_DANCE")
        self.assertEqual(len(engine.queue), 0) # Hàng chờ đã trống

    def test_action_engine_submit(self):
        """Xác minh phương thức submit alias hoạt động chính xác thông qua dispatch."""
        from src.action_engine import ActionEngine, ActionSource
        
        mock_controller = MagicMock()
        mock_controller.trigger_animation.return_value = (True, "HTTP")
        
        engine = ActionEngine()
        engine.set_controller(mock_controller)
        engine.last_triggered = {}
        engine.last_action_time = 0.0
        engine.current_action = None
        
        # Gọi submit cử chỉ
        res = engine.submit("point_down", ActionSource.WEB)
        self.assertTrue(res)
        self.assertEqual(engine.current_action, "AI_LIVE_POINT_DOWN")
        mock_controller.trigger_animation.assert_called_once_with("AI_LIVE_POINT_DOWN", [])

    def test_command_id_generation_and_logging(self):
        """Xác minh sinh Command ID tự tăng dạng CMD-YYYYMMDD-XXXXXX và ghi trace log."""
        from src.action_engine import ActionEngine, ActionSource
        import re
        
        mock_controller = MagicMock()
        mock_controller.trigger_animation.return_value = (True, "HTTP")
        
        engine = ActionEngine()
        engine.set_controller(mock_controller)
        engine.command_counter = 0
        engine.last_triggered = {}
        engine.last_action_time = 0.0
        engine.current_action = None
        
        # Test sinh ID trực tiếp
        cmd_id = engine.generate_command_id()
        self.assertTrue(re.match(r"^CMD-\d{8}-000001$", cmd_id))
        
        # Gọi dispatch
        res = engine.dispatch("point_down", ActionSource.WEB)
        self.assertTrue(res)
        self.assertEqual(engine.command_counter, 2)

    @patch("ai_live.integrations.vnyan.discovery.VNyanDiscovery.discover")
    def test_installer_refuses_when_vnyan_running(self, mock_discover):
        """Xác minh installer từ chối cài đặt hoặc rollback Node Graph khi VNyan đang chạy."""
        from ai_live.integrations.vnyan.bridge.installer import NodeGraphInstaller
        from ai_live.integrations.vnyan.detector import VNyanDetector
        from ai_live.integrations.vnyan.models import VNyanInstance
        
        # Giả lập VNyan đang chạy
        mock_discover.return_value = VNyanInstance(
            executable_path=Path("D:/Vnyan/VNyan.exe"),
            pid=9999,
            host="127.0.0.1",
            api_port=8069,
            vmc_port=39539,
            osc_port=None,
            running=True,
            version=None
        )
        
        detector = VNyanDetector()
        installer = NodeGraphInstaller(detector)
        
        # A. Thử chạy install -> Phải trả về False và ghi cảnh báo
        res_install = installer.install_ai_live_bridge()
        self.assertFalse(res_install)
        self.assertIn("Tiến trình VNyan.exe đang chạy", installer.warnings[0])
        
        # B. Thử chạy rollback -> Phải trả về False
        res_rollback = installer.rollback()
        self.assertFalse(res_rollback)

    def test_action_engine_thread_safety(self):
        """Xác minh ActionEngine thread-safe khi gọi dispatch từ nhiều thread đồng thời."""
        from src.action_engine import ActionEngine, ActionSource
        import threading
        
        mock_controller = MagicMock()
        mock_controller.trigger_animation.return_value = (True, "HTTP")
        
        engine = ActionEngine()
        engine.set_controller(mock_controller)
        engine.last_triggered = {}
        engine.last_action_time = 0.0
        engine.current_action = None
        
        threads = []
        results = []
        
        def run_dispatch(act, src):
            res = engine.dispatch(act, src)
            results.append(res)
            
        # Kích hoạt từ 5 thread đồng thời
        for i in range(5):
            t = threading.Thread(target=run_dispatch, args=("point_down", ActionSource.WEB))
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()
            
        # Chỉ có đúng 1 thread thành công vì cooldown và lock bảo vệ chặn phần còn lại
        self.assertEqual(results.count(True), 1)

    @patch("ai_live.integrations.vnyan.detector.VNyanDetector.get_config_dir")
    @patch("ai_live.integrations.vnyan.discovery.VNyanDiscovery.discover")
    def test_installer_creates_dual_nodes(self, mock_discover, mock_config_dir):
        """Xác minh installer sinh đồ thị chứa cả APIMessageNode và TriggerNode."""
        from ai_live.integrations.vnyan.bridge.installer import NodeGraphInstaller
        from ai_live.integrations.vnyan.detector import VNyanDetector
        from ai_live.integrations.vnyan.models import VNyanInstance
        import tempfile
        import shutil
        
        # Giả lập VNyan KHÔNG chạy
        mock_discover.return_value = VNyanInstance(
            executable_path=None, pid=None, host="127.0.0.1", api_port=8069, vmc_port=39539, osc_port=None,
            running=False, version=None
        )
        
        # Tạo thư mục tạm giả lập config VNyan
        temp_dir = tempfile.mkdtemp()
        mock_config_dir.return_value = Path(temp_dir)
        
        # Tạo file redeems.json giả lập rỗng
        redeems_file = Path(temp_dir) / "redeems.json"
        with open(redeems_file, "w", encoding="utf-8") as f:
            json.dump({"nodes": [], "connections": []}, f)
            
        detector = VNyanDetector()
        installer = NodeGraphInstaller(detector)
        installer.manifest_path = Path(temp_dir) / "manifest.json"
        
        # Thực thi install
        res = installer.install_ai_live_bridge()
        self.assertTrue(res)
        
        # Đọc lại redeems.json để kiểm tra dual nodes
        with open(redeems_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        nodes = data.get("nodes", [])
        connections = data.get("connections", [])
        
        # Phải có APIMessageNode và TriggerNode
        api_nodes = [n for n in nodes if n.get("path") == "Nodes/APIMessageNode"]
        trigger_nodes = [n for n in nodes if n.get("path") == "Nodes/TriggerNode"]
        
        self.assertTrue(len(api_nodes) > 0)
        self.assertTrue(len(trigger_nodes) > 0)
        
        # Dọn dẹp thư mục tạm
        shutil.rmtree(temp_dir)














