import unittest
from ai_live.integrations.vnyan.avatar.expression_mapper import ExpressionMapper

class TestExpressionMapper(unittest.TestCase):
    def setUp(self):
        self.mapper = ExpressionMapper()

    def test_map_visemes(self):
        names = ["aa", "ee", "ih", "oh", "ou"]
        groups = [
            {"name": "aa", "presetName": "a"},
            {"name": "ee", "presetName": "e"},
            {"name": "ih", "presetName": "i"},
            {"name": "oh", "presetName": "o"},
            {"name": "ou", "presetName": "u"}
        ]
        profile = self.mapper.map_expressions(names, groups)
        self.assertEqual(profile.viseme_a, "aa")
        self.assertEqual(profile.viseme_e, "ee")

    def test_map_emotions(self):
        names = ["happy", "sad", "angry", "Surprised", "relaxed", "neutral"]
        groups = [
            {"name": "happy", "presetName": "joy"},
            {"name": "sad", "presetName": "sorrow"},
            {"name": "angry", "presetName": "angry"},
            {"name": "Surprised", "presetName": "unknown"},
            {"name": "relaxed", "presetName": "fun"},
            {"name": "neutral", "presetName": "neutral"}
        ]
        profile = self.mapper.map_expressions(names, groups)
        self.assertEqual(profile.happy, "happy")
        self.assertEqual(profile.sad, "sad")
        self.assertEqual(profile.angry, "angry")
        self.assertEqual(profile.surprised, "Surprised")
        self.assertEqual(profile.relaxed, "relaxed")
        self.assertEqual(profile.neutral, "neutral")

    def test_map_blink(self):
        names = ["blinkLeft", "blinkRight"]
        groups = [
            {"name": "blinkLeft", "presetName": "blink_l"},
            {"name": "blinkRight", "presetName": "blink_r"}
        ]
        profile = self.mapper.map_expressions(names, groups)
        self.assertIsNone(profile.blink)
        self.assertEqual(profile.blink_left, "blinkLeft")
        self.assertEqual(profile.blink_right, "blinkRight")

    def test_reject_low_confidence_mapping(self):
        # Tên blendshape hoàn toàn không liên quan, không khớp bất kỳ candidate nào
        names = ["xyz_unrelated_123", "abc_test_shape"]
        profile = self.mapper.map_expressions(names, [])
        # Tất cả core mappings phải là None do score < 0.65
        self.assertIsNone(profile.viseme_a)
        self.assertIsNone(profile.happy)
        self.assertIsNone(profile.blink)
