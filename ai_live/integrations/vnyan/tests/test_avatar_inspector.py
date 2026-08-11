import unittest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from ai_live.integrations.vnyan.avatar.inspector import VRMInspector

class TestVRMInspector(unittest.TestCase):
    def setUp(self):
        self.inspector = VRMInspector()

    def test_inspect_vrm(self):
        mock_glb_json = {
            "extensions": {
                "VRM": {
                    "exporterVersion": "UniVRM-0.66.0",
                    "meta": {
                        "title": "Avatar Test",
                        "version": "1.0",
                        "allowedUserName": "Everyone"
                    },
                    "blendShapeMaster": {
                        "blendShapeGroups": [
                            {"name": "Neutral", "presetName": "neutral"},
                            {"name": "aa", "presetName": "a"},
                            {"name": "ee", "presetName": "e"},
                            {"name": "ih", "presetName": "i"},
                            {"name": "oh", "presetName": "o"},
                            {"name": "ou", "presetName": "u"},
                            {"name": "blink", "presetName": "blink"},
                            {"name": "blinkLeft", "presetName": "blink_l"},
                            {"name": "blinkRight", "presetName": "blink_r"},
                            {"name": "happy", "presetName": "joy"},
                            {"name": "sad", "presetName": "sorrow"},
                            {"name": "angry", "presetName": "angry"},
                            {"name": "Surprised", "presetName": "unknown"}
                        ]
                    }
                }
            },
            "materials": [{}],
            "textures": [{}],
            "skins": [{"joints": [1, 2, 3]}]
        }
        
        with patch.object(VRMInspector, "_parse_glb_json", return_value=mock_glb_json):
            with patch("pathlib.Path.exists", return_value=True):
                profile = self.inspector.inspect(Path("avatar.vrm"))
                
                self.assertEqual(profile.format, "VRM")
                self.assertEqual(profile.version, "1.0")
                self.assertEqual(profile.bones, 3)
                self.assertEqual(profile.materials, 1)
                self.assertEqual(profile.textures, 1)
                
                expr = profile.expressions
                self.assertEqual(expr.viseme_a, "aa")
                self.assertEqual(expr.viseme_e, "ee")
                self.assertEqual(expr.viseme_i, "ih")
                self.assertEqual(expr.viseme_o, "oh")
                self.assertEqual(expr.viseme_u, "ou")
                self.assertEqual(expr.happy, "happy")
                self.assertEqual(expr.sad, "sad")
                self.assertEqual(expr.angry, "angry")
                self.assertEqual(expr.surprised, "Surprised")
                self.assertEqual(expr.blink, "blink")
                self.assertEqual(expr.blink_left, "blinkLeft")
                self.assertEqual(expr.blink_right, "blinkRight")
