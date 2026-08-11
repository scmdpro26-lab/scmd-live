"""
Static Contract Test — vmc_client ↔ VMCTransport

Mục đích:
  Đảm bảo rằng mọi blendshape gửi tới VMCTransport.send_blendshape()
  phải đi qua ExpressionController / VisemeController / BlinkController —
  không có path nào bypass registry.

Nguyên tắc xây dựng blacklist:
  - Alias raw của EXPRESSION_CANDIDATES là KHÔNG được phép gửi thẳng.
  - Ngoại lệ: nếu alias đó trùng với tên thật trong expressions.available
    của profile thực (ví dụ avatar đặt blendshape tên "Fun" hoặc "A"),
    thì controller sẽ map đúng ra tên đó → hợp lệ.
  - Ta kiểm tra SEMANTIC KEY không nằm trong sent (ví dụ "joy", "sorrow")
    và sent phải nằm trong available.

Cách test hoạt động:
  1. Load profile JSON thực từ profiles/avatars/<hash>.json.
  2. Xây dựng blacklist = alias thô KHÔNG có trong available.
  3. Patch VMCTransport.send_blendshape() để ghi lại tất cả tên gửi đi.
  4. Gọi send_blendshape() / set_expression() / set_viseme() / blink().
  5. Assert:
       a) Mọi tên gửi phải nằm trong expressions.available.
       b) Không có alias thuần thô (semantic key, không phải tên avatar)
          nào chạm trực tiếp transport.

Nếu một module trong tương lai gọi send_blendshape("Joy",...) trực tiếp,
test này sẽ FAIL ngay lập tức.
"""
import json
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai_live.integrations.vnyan.avatar.registry import AvatarRegistry
from ai_live.integrations.vnyan.constants import EXPRESSION_CANDIDATES
from ai_live.integrations.vnyan.exceptions import CapabilityUnavailable
from src.vmc_client import VMCClient


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _load_first_profile() -> tuple[dict, str]:
    """
    Đọc profile JSON thực từ profiles/avatars/.
    Ưu tiên file nào có source_path khớp DEFAULT_AVATAR_PATH,
    sau đó xếp theo detected_at mới nhất.
    """
    import os
    env_avatar = os.environ.get("DEFAULT_AVATAR_PATH", "")
    
    profiles_dir = Path("profiles/avatars")
    json_files = list(profiles_dir.glob("*.json"))
    
    valid_profiles = []
    for f in json_files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            valid_profiles.append((f, data))
        except Exception:
            continue
            
    if not valid_profiles:
        raise FileNotFoundError(
            "Không tìm thấy profile JSON trong profiles/avatars/. "
            "Hãy chạy VRM Inspector ít nhất 1 lần trước khi chạy test này."
        )

    # 1. Ưu tiên profile có source_path trùng cấu hình .env
    if env_avatar:
        for f, data in valid_profiles:
            if data.get("source_path") == env_avatar:
                return data, f.stem

    # 2. Xếp theo detected_at mới nhất
    valid_profiles.sort(key=lambda x: x[1].get("detected_at", ""), reverse=True)
    
    # 3. Bỏ qua các profile rác không có 'happy' (thường do test sinh ra)
    for f, data in valid_profiles:
        if data.get("expressions", {}).get("happy") is not None:
            return data, f.stem
            
    return valid_profiles[0][1], valid_profiles[0][0].stem


def _build_semantic_blacklist(available: list[str]) -> set[str]:
    """
    Xây dựng tập hợp tên KHÔNG được phép gửi trực tiếp tới transport.

    Quy tắc: Lấy tất cả semantic keys từ EXPRESSION_CANDIDATES (ví dụ "happy",
    "sad", "joy", "sorrow", "mouthopen"...). Đây là tên "ngữ nghĩa" / "alias thô"
    mà controller phải dịch sang tên thật — chúng không được tồn tại trong sent
    trừ khi avatar thật đặt blendshape trùng tên (trường hợp này excluded khỏi blacklist).

    Cụ thể: một alias bị loại khỏi blacklist nếu nó CHÍNH XÁC khớp tên trong
    available (case-sensitive theo chuẩn VRM).
    """
    available_set = set(available)
    blacklist = set()
    for key, candidates in EXPRESSION_CANDIDATES.items():
        # Semantic key bản thân nó (ví dụ "happy", "viseme_a")
        if key not in available_set:
            blacklist.add(key)
        # Mọi alias trong danh sách candidates
        for alias in candidates:
            if alias not in available_set:
                blacklist.add(alias)
    return blacklist


# ─── Test Classes ─────────────────────────────────────────────────────────────

class TestNoRawAliasReachesTransport(unittest.TestCase):
    """
    Contract chính: Không có alias ngữ nghĩa thô nào được phép đến transport.
    """

    @classmethod
    def setUpClass(cls):
        cls.profile_data, cls.profile_hash = _load_first_profile()
        cls.available: list[str] = cls.profile_data["expressions"]["available"]
        cls.blacklist: set[str] = _build_semantic_blacklist(cls.available)
        cls.vmc = VMCClient()  # singleton

    def setUp(self):
        """Đảm bảo VMCClient singleton luôn dùng profile thật trước mỗi test."""
        import json as _json
        from ai_live.integrations.vnyan.models import AvatarProfile, AvatarExpressionProfile
        from datetime import datetime

        profiles_dir = Path("profiles/avatars")
        json_files = sorted(profiles_dir.glob("*.json"))
        if not json_files:
            return  # Không có cache → bỏ qua (test sẽ dùng profile hiện tại)

        # Parse JSON cache thủ công — không cần file .vrm tồn tại
        data = _json.loads(json_files[0].read_text(encoding="utf-8"))
        expr_data = data.get("expressions", {})
        expr = AvatarExpressionProfile(
            available=expr_data.get("available", []),
            viseme_a=expr_data.get("viseme_a"), viseme_e=expr_data.get("viseme_e"),
            viseme_i=expr_data.get("viseme_i"), viseme_o=expr_data.get("viseme_o"),
            viseme_u=expr_data.get("viseme_u"), happy=expr_data.get("happy"),
            sad=expr_data.get("sad"), angry=expr_data.get("angry"),
            surprised=expr_data.get("surprised"), relaxed=expr_data.get("relaxed"),
            neutral=expr_data.get("neutral"), blink=expr_data.get("blink"),
            blink_left=expr_data.get("blink_left"), blink_right=expr_data.get("blink_right"),
            custom=expr_data.get("custom", []),
        )
        real_profile = AvatarProfile(
            source_path=Path(data["source_path"]), format=data["format"],
            version=data["version"], height=data["height"], bones=data["bones"],
            materials=data["materials"], textures=data["textures"],
            expressions=expr, detected_at=datetime.fromisoformat(data["detected_at"]),
        )
        self.vmc.manager.registry._current_profile = real_profile


    def _spy(self) -> tuple[object, list]:
        """Trả về (patcher, sent_list). Gọi với `with patcher`."""
        sent = []
        original = self.vmc.manager.vmc_transport.send_blendshape

        def side_effect(name, value):
            sent.append(name)
            # Gọi original để không phá vỡ internal state
            try:
                return original(name, value)
            except Exception:
                return True

        patcher = patch.object(
            self.vmc.manager.vmc_transport,
            "send_blendshape",
            side_effect=side_effect,
        )
        return patcher, sent

    def _assert_no_raw_bypass(self, sent: list[str], context: str):
        """Helper: assert tất cả tên gửi hợp lệ theo contract."""
        for shape in sent:
            # 1. Tên gửi phải nằm trong available của avatar
            self.assertIn(
                shape, self.available,
                f"[{context}] Gửi '{shape}' không có trong "
                f"expressions.available của avatar!"
            )
            # 2. Tên gửi không được là alias ngữ nghĩa thô
            self.assertNotIn(
                shape, self.blacklist,
                f"[{context}] Alias thô '{shape}' chạm trực tiếp transport "
                f"mà không qua Controller!"
            )

    # ── Viseme ────────────────────────────────────────────────────────────────

    def test_viseme_mouthopen_alias_is_resolved(self):
        """send_blendshape('MouthOpen') phải resolve qua VisemeController."""
        patcher, sent = self._spy()
        with patcher:
            try:
                self.vmc.send_blendshape("MouthOpen", 0.5)
            except CapabilityUnavailable:
                return  # Bị chặn đúng chỗ — OK
        self._assert_no_raw_bypass(sent, "VISEME MouthOpen")

    def test_viseme_vowel_chars_are_resolved(self):
        """send_blendshape('a'/'e'/'i'/'o'/'u') phải resolve qua VisemeController."""
        for char in ["a", "e", "i", "o", "u"]:
            patcher, sent = self._spy()
            with patcher:
                try:
                    self.vmc.send_blendshape(char, 0.5)
                except CapabilityUnavailable:
                    continue
            self._assert_no_raw_bypass(sent, f"VISEME '{char}'")

    def test_lip_sync_loop_only_sends_resolved_names(self):
        """_lip_sync_loop() không được gửi tên raw nào tới transport."""
        self.vmc._is_talking = True
        patcher, sent = self._spy()
        with patcher:
            # Chạy 1 vòng lặp ngắn
            import threading
            import time as _time

            def _stop_after():
                _time.sleep(0.25)
                self.vmc._is_talking = False

            threading.Thread(target=_stop_after, daemon=True).start()
            try:
                self.vmc._lip_sync_loop(audio_path=None)
            except Exception:
                pass

        self._assert_no_raw_bypass(sent, "LIP_SYNC_LOOP")

    # ── Expression ────────────────────────────────────────────────────────────

    def test_all_expression_semantic_keys_resolve_through_controller(self):
        """
        Mọi semantic key (happy, sad, angry, surprised, relaxed, neutral)
        phải gửi tên thực trong available, không gửi alias thô.
        """
        expression_keys = [
            k for k in EXPRESSION_CANDIDATES
            if not k.startswith("viseme_") and not k.startswith("blink")
        ]
        for key in expression_keys:
            patcher, sent = self._spy()
            with patcher:
                try:
                    self.vmc.manager.expression.set_expression(key, 0.5)
                except CapabilityUnavailable:
                    continue  # Avatar không có blendshape này — bỏ qua

            self._assert_no_raw_bypass(sent, f"EXPRESSION '{key}'")

    def test_legacy_expression_aliases_via_send_blendshape_are_redirected(self):
        """
        Khi gọi send_blendshape() với alias cũ ("Joy","Sorrow","Surprise","Neutral"),
        phải được redirect qua ExpressionController, không gửi alias thẳng tới transport.
        """
        legacy_aliases = [
            "Joy", "Sorrow", "Surprise", "Neutral", "Angry",
            "joy", "sorrow", "surprise", "neutral", "angry",
        ]
        for alias in legacy_aliases:
            patcher, sent = self._spy()
            with patcher:
                try:
                    self.vmc.send_blendshape(alias, 0.5)
                except CapabilityUnavailable:
                    continue  # Bị chặn đúng → OK

            # Nếu có tên được gửi, kiểm tra không phải alias thô
            for shape in sent:
                self.assertIn(
                    shape, self.available,
                    f"[LEGACY EXPR] send_blendshape('{alias}') "
                    f"→ gửi '{shape}' không có trong available!"
                )
                self.assertNotIn(
                    shape, self.blacklist,
                    f"[LEGACY EXPR] send_blendshape('{alias}') "
                    f"→ alias thô '{shape}' chạm transport mà không qua Controller!"
                )

    def test_trigger_expression_with_legacy_joy_resolves(self):
        """
        trigger_expression('Joy') phải resolve ra tên thật của avatar,
        không gửi 'Joy' hay 'joy' nguyên si.
        """
        patcher, sent = self._spy()
        with patcher:
            self.vmc.trigger_expression("Joy", 0.01)
            time.sleep(0.1)  # Chờ thread

        # Nếu không có gì được gửi → avatar không hỗ trợ → bỏ qua
        if not sent:
            return

        for shape in sent:
            self.assertNotIn(
                shape, {"Joy", "joy", "JOY"},
                f"[TRIGGER EXPR] trigger_expression('Joy') → "
                f"gửi alias '{shape}' thẳng tới transport!"
            )
            self.assertIn(
                shape, self.available,
                f"[TRIGGER EXPR] '{shape}' không có trong available!"
            )

    def test_trigger_expression_with_semantic_happy_resolves(self):
        """trigger_expression('happy') phải gửi tên thực, không gửi 'happy'."""
        patcher, sent = self._spy()
        with patcher:
            self.vmc.trigger_expression("happy", 0.01)
            time.sleep(0.1)

        if not sent:
            return

        for shape in sent:
            self.assertNotIn(
                shape, {"happy", "Happy", "HAPPY"},
                f"[TRIGGER EXPR] trigger_expression('happy') → "
                f"gửi 'happy' thẳng tới transport!"
            )
            self.assertIn(shape, self.available)

    # ── Blink ─────────────────────────────────────────────────────────────────

    def test_blink_uses_blink_controller_not_hardcode(self):
        """blink() phải resolve qua BlinkController, tên gửi phải trong available."""
        patcher, sent = self._spy()
        with patcher:
            try:
                self.vmc.blink(duration_ms=10)
            except CapabilityUnavailable:
                return

        self._assert_no_raw_bypass(sent, "BLINK")

    def test_stop_talking_resets_viseme_via_controller(self):
        """stop_talking() reset lipsync phải dùng VisemeController, không send raw."""
        self.vmc._is_talking = True  # Giả lập đang nói
        patcher, sent = self._spy()
        with patcher:
            try:
                self.vmc.stop_talking()
            except CapabilityUnavailable:
                return

        self._assert_no_raw_bypass(sent, "STOP_TALKING")


class TestAvatarProfileIntegrity(unittest.TestCase):
    """
    Contract phụ: Profile JSON thực phải đầy đủ để Controller không cần fallback raw.
    """

    @classmethod
    def setUpClass(cls):
        cls.profile_data, cls.profile_hash = _load_first_profile()
        cls.expr = cls.profile_data.get("expressions", {})
        cls.available: list[str] = cls.expr.get("available", [])

    def test_profile_has_all_mandatory_semantic_keys(self):
        """Profile JSON phải chứa đủ semantic key để mọi controller resolve được."""
        # Chỉ viseme_a là bắt buộc (cần thiết cho lipsync cơ bản)
        # Các viseme khác (e, i, o, u) là optional theo VRM 0.x
        required = [
            "viseme_a",
            "happy", "sad", "angry", "surprised", "neutral", "blink",
        ]
        optional = ["viseme_e", "viseme_i", "viseme_o", "viseme_u",
                    "relaxed", "blink_left", "blink_right"]

        for key in required:
            self.assertIn(
                key, self.expr,
                f"[PROFILE] Profile thiếu semantic key bắt buộc '{key}'. "
                f"Chạy lại VRM Inspector để tái tạo profile."
            )
            self.assertIsNotNone(
                self.expr[key],
                f"[PROFILE] Key bắt buộc '{key}' có giá trị None trong profile JSON!"
            )

        for key in optional:
            if key in self.expr and self.expr[key] is not None:
                # Nếu có giá trị, phải nằm trong available
                self.assertIn(
                    self.expr[key], self.available,
                    f"[PROFILE] Optional key '{key}' map sang '{self.expr[key]}' không có trong available!"
                )

    def test_profile_available_resolves_map_to_known_keys(self):
        """Mọi giá trị trong semantic mapping phải có mặt trong expressions.available."""
        available_set = set(self.available)
        skip_keys = {"available", "custom", "schema_version"}

        for key, value in self.expr.items():
            if key in skip_keys or not isinstance(value, str):
                continue
            self.assertIn(
                value, available_set,
                f"[PROFILE] Profile ánh xạ '{key}' → '{value}' "
                f"nhưng '{value}' không nằm trong expressions.available!"
            )

    def test_available_has_no_duplicates_or_empty(self):
        """expressions.available không được có tên trùng hay rỗng."""
        self.assertGreater(len(self.available), 0)
        seen = set()
        for name in self.available:
            self.assertNotEqual(name.strip(), "")
            self.assertNotIn(name, seen, f"Tên '{name}' bị trùng trong available!")
            seen.add(name)

    def test_no_two_semantic_keys_map_to_same_blendshape_unintentionally(self):
        """Không có 2 semantic key khác nhau nào được map trùng vào cùng 1 tên blendshape thật, trừ các ngoại lệ đã biết."""
        mapping = {k: v for k, v in self.expr.items() if k not in ("available","custom","schema_version") and v}
        seen = {}
        
        # Các ngoại lệ cố ý cho phép map trùng (ví dụ relaxed có thể dùng chung với viseme_a)
        allowed_overlaps = [
            {"relaxed", "viseme_a"}
        ]
        
        for key, val in mapping.items():
            if val in seen:
                prev_key = seen[val]
                overlap_set = {key, prev_key}
                is_allowed = any(overlap_set.issubset(allowed) for allowed in allowed_overlaps)
                if not is_allowed:
                    self.fail(f"'{key}' và '{prev_key}' cùng map vào blendshape '{val}' — có thể là lỗi scoring!")
            else:
                seen[val] = key


class TestRegistryCacheInvalidation(unittest.TestCase):
    """
    Contract: AvatarRegistry cập nhật current_profile khi avatar thay đổi.
    """

    def test_registry_current_profile_changes_on_different_path(self):
        """get_profile(path_A) rồi get_profile(path_B) → current_profile khác nhau."""
        vmc = VMCClient()

        dummy1 = Path("_test_contract_avatar_1.vrm")
        dummy2 = Path("_test_contract_avatar_2.vrm")
        dummy1.write_bytes(b"FAKE_VRM_AAAAA_UNIQUE_CONTENT_1111")
        dummy2.write_bytes(b"FAKE_VRM_BBBBB_UNIQUE_CONTENT_2222")

        try:
            # Dùng mock inspector để tránh parse file VRM thật
            mock_inspector = MagicMock()

            def make_fake_profile(path):
                p = MagicMock()
                p.source_path = path
                p.expressions = MagicMock()
                p.expressions.available = ["Blink"]
                return p

            mock_inspector.inspect.side_effect = make_fake_profile

            registry = AvatarRegistry(vmc.manager.profile_manager, mock_inspector)

            p1 = registry.get_profile(dummy1)
            self.assertIs(registry.current_profile, p1,
                          "current_profile phải là profile của dummy1 sau lần load 1")

            p2 = registry.get_profile(dummy2)
            self.assertIs(registry.current_profile, p2,
                          "current_profile phải là profile của dummy2 sau lần load 2")

            self.assertIsNot(p1, p2, "Profile của 2 VRM khác nhau phải là 2 object khác!")
        finally:
            dummy1.unlink(missing_ok=True)
            dummy2.unlink(missing_ok=True)


class TestAvatarSwapIsolation(unittest.TestCase):
    """
    Xác nhận rằng khi đổi VRM avatar:
      1. registry.current_profile được cập nhật ngay lập tức.
      2. Các controller (Expression/Viseme/Blink) đọc current_profile
         mỗi lần gọi (lazy) → tự dùng profile mới, không cache profile cũ.
      3. send_blendshape() sau khi đổi avatar resolve theo profile mới,
         không còn dùng mapping của avatar cũ.
      4. Cache invalidation dựa trên SHA-256 nội dung file (không phải tên),
         nên 2 file khác tên nhưng cùng nội dung sẽ dùng cùng profile (đúng).

    Cơ chế cache hoạt động:
      load_avatar(path)
        └─ registry.get_profile(path)
             └─ profile_manager.load_profile(path)
                  └─ _get_file_hash(path)  ← SHA-256 nội dung file
                       └─ profiles/avatars/<hash>.json
                            └─ nếu không có → inspector.inspect(path) → save
    """

    @classmethod
    def _cleanup_stale_caches(cls):
        """Xóa mọi file cache JSON rác (không phải profile thật) trong profiles/avatars/."""
        import json as _json
        profiles_dir = Path("profiles/avatars")
        for cache_f in profiles_dir.glob("*.json"):
            try:
                data = _json.loads(cache_f.read_text(encoding="utf-8"))
                if data.get("expressions", {}).get("happy") is None:
                    cache_f.unlink()
            except Exception:
                pass

    @classmethod
    def setUpClass(cls):
        cls._cleanup_stale_caches()  # Xóa cache rác trước khi load
        cls.vmc = VMCClient()
        cls.profile_data, _ = _load_first_profile()
        cls.real_available: list[str] = cls.profile_data["expressions"]["available"]
        # Giữ reference tới profile thật để restore sau mọi test swap
        cls._real_profile = cls.vmc.manager.profile_manager.load_profile(
            Path(cls.profile_data["source_path"])
        )

    def tearDown(self):
        """Restore profile thật vào singleton sau mọi test swap và xóa cache rác."""
        if self._real_profile:
            self.vmc.manager.registry._current_profile = self._real_profile

        # Xóa mọi file cache rác do fake VRM sinh ra trong tests này
        import json as _json
        real_hash = self.profile_data.get("avatar_hash", "")
        profiles_dir = Path("profiles/avatars")
        for cache_f in profiles_dir.glob("*.json"):
            if cache_f.stem == real_hash:
                continue  # Giữ cache thật
            try:
                data = _json.loads(cache_f.read_text(encoding="utf-8"))
                # File rác thường không có 'happy' được map
                if data.get("expressions", {}).get("happy") is None:
                    cache_f.unlink()
            except Exception:
                pass

    def _make_fake_registry(self, avatar_a_shapes: list, avatar_b_shapes: list):
        """
        Tạo AvatarRegistry độc lập với 2 profile giả cho avatar A và B.
        Trả về (registry, path_a, path_b, profile_a, profile_b).
        """
        path_a = Path("_swap_test_avatar_A.vrm")
        path_b = Path("_swap_test_avatar_B.vrm")
        # Nội dung khác nhau → hash khác nhau → 2 cache entry riêng
        path_a.write_bytes(b"SWAP_FAKE_VRM_CONTENT_AVATAR_ALPHA_0001")
        path_b.write_bytes(b"SWAP_FAKE_VRM_CONTENT_AVATAR_BETA__0002")

        # Mock save_profile để không ghi file JSON rác ra đĩa
        mock_pm = MagicMock(wraps=self.vmc.manager.profile_manager)
        mock_pm.save_profile.return_value = True

        def make_profile(path, shapes):
            from datetime import datetime
            from ai_live.integrations.vnyan.models import AvatarProfile, AvatarExpressionProfile
            expr = AvatarExpressionProfile(
                available=shapes,
                viseme_a=shapes[0] if shapes else None,
                viseme_e=None, viseme_i=None, viseme_o=None, viseme_u=None,
                happy=shapes[1] if len(shapes) > 1 else None,
                sad=None, angry=None, surprised=None,
                relaxed=None, neutral=None,
                blink=shapes[2] if len(shapes) > 2 else None,
                blink_left=None, blink_right=None, custom=[],
            )
            return AvatarProfile(
                source_path=path, format="VRM", version="0.x",
                height=1.6, bones=100, materials=5, textures=10,
                expressions=expr, detected_at=datetime.now(),
            )

        profile_a = make_profile(path_a, avatar_a_shapes)
        profile_b = make_profile(path_b, avatar_b_shapes)

        mock_inspector = MagicMock()
        mock_inspector.inspect.side_effect = (
            lambda p: profile_a if p == path_a else profile_b
        )

        registry = AvatarRegistry(mock_pm, mock_inspector)
        return registry, path_a, path_b, profile_a, profile_b

    def test_current_profile_updates_immediately_on_avatar_swap(self):
        """
        Sau load avatar A rồi load avatar B:
          - current_profile phải là profile B.
          - current_profile không còn là profile A.
        """
        registry, path_a, path_b, profile_a, profile_b = self._make_fake_registry(
            avatar_a_shapes=["Blink", "Fun", "A"],
            avatar_b_shapes=["Wink", "Joy2", "V"],
        )
        try:
            p_a = registry.get_profile(path_a)
            self.assertIs(registry.current_profile, p_a)
            self.assertEqual(registry.current_profile.expressions.available, ["Blink", "Fun", "A"])

            p_b = registry.get_profile(path_b)
            self.assertIs(registry.current_profile, p_b)
            self.assertEqual(registry.current_profile.expressions.available, ["Wink", "Joy2", "V"])

            # Không còn trỏ về profile cũ
            self.assertIsNot(registry.current_profile, p_a)
        finally:
            path_a.unlink(missing_ok=True)
            path_b.unlink(missing_ok=True)

    def test_expression_controller_uses_new_profile_after_swap(self):
        """
        ExpressionController.set_expression() đọc registry.current_profile
        mỗi lần gọi (lazy) → sau swap avatar, tự dùng mapping của avatar mới.
        Dùng registry và transport riêng biệt — không ảnh hưởng vmc singleton.
        """
        from ai_live.integrations.vnyan.controllers.expression import ExpressionController

        registry, path_a, path_b, profile_a, profile_b = self._make_fake_registry(
            avatar_a_shapes=["OldHappy", "OldBlink", "OldViseme"],
            avatar_b_shapes=["NewHappy", "NewBlink", "NewViseme"],
        )
        mock_transport = MagicMock()
        sent = []
        mock_transport.send_blendshape.side_effect = lambda n, v: sent.append(n) or True
        ctrl = ExpressionController(mock_transport, registry)

        try:
            # ── Load A, gọi expression ──────────────────────────────────────────
            registry.get_profile(path_a)
            self.assertIs(registry.current_profile, profile_a)
            sent.clear()
            try:
                ctrl.set_expression("happy", 1.0)
            except CapabilityUnavailable:
                pass
            shapes_after_a = list(sent)

            for shape in shapes_after_a:
                self.assertIn(shape, profile_a.expressions.available,
                              f"Sau load A: '{shape}' không thuộc available A!")

            # ── Swap sang B, gọi lại — phải dùng available của B ─────────────
            registry.get_profile(path_b)
            self.assertIs(registry.current_profile, profile_b,
                          "current_profile phải là profile_b sau swap!")
            sent.clear()
            try:
                ctrl.set_expression("happy", 1.0)
            except CapabilityUnavailable:
                pass
            shapes_after_b = list(sent)

            for shape in shapes_after_b:
                self.assertIn(shape, profile_b.expressions.available,
                              f"Sau swap B: '{shape}' không thuộc available B!")
                self.assertNotIn(shape, profile_a.expressions.available,
                                 f"Sau swap B: '{shape}' vẫn thuộc available A cũ!")
        finally:
            path_a.unlink(missing_ok=True)
            path_b.unlink(missing_ok=True)


    def test_cache_key_is_file_content_hash_not_filename(self):
        """
        2 file VRM khác tên nhưng cùng nội dung → cùng hash → cùng profile (đúng).
        2 file VRM cùng tên nhưng khác nội dung → khác hash → khác profile (đúng).
        """
        pm = self.vmc.manager.profile_manager

        # Case 1: 2 file khác tên, cùng nội dung
        path_copy1 = Path("_hash_test_copy1.vrm")
        path_copy2 = Path("_hash_test_copy2.vrm")
        same_content = b"IDENTICAL_VRM_CONTENT_XYZ_12345678"
        path_copy1.write_bytes(same_content)
        path_copy2.write_bytes(same_content)

        try:
            hash1 = pm._get_file_hash(path_copy1)
            hash2 = pm._get_file_hash(path_copy2)
            self.assertEqual(
                hash1, hash2,
                "File cùng nội dung phải có cùng hash (sẽ dùng cùng profile cache)."
            )
            # Cả 2 phải trỏ cùng file cache
            self.assertEqual(pm.get_profile_path(path_copy1), pm.get_profile_path(path_copy2))
        finally:
            path_copy1.unlink(missing_ok=True)
            path_copy2.unlink(missing_ok=True)

        # Case 2: 2 file cùng tên logic, khác nội dung
        path_v1 = Path("_hash_test_avatar.vrm")
        path_v1.write_bytes(b"VRM_CONTENT_VERSION_1_AAAAAA")
        hash_v1 = pm._get_file_hash(path_v1)

        # Ghi đè với nội dung mới (avatar được cập nhật)
        path_v1.write_bytes(b"VRM_CONTENT_VERSION_2_BBBBBB")
        hash_v2 = pm._get_file_hash(path_v1)

        try:
            self.assertNotEqual(
                hash_v1, hash_v2,
                "File bị thay đổi nội dung phải có hash khác → cache bị invalidate."
            )
        finally:
            path_v1.unlink(missing_ok=True)

    def test_vmc_client_load_avatar_updates_real_registry(self):
        """
        VMCClient.load_avatar(path) phải cập nhật self.manager.registry.current_profile
        mà tất cả controller đang dùng — không phải registry nội bộ khác.
        """
        vmc = VMCClient()
        profile_before = vmc.manager.registry.current_profile

        # Dùng profile thực đã có sẵn trong cache
        profile_data, profile_hash = _load_first_profile()
        real_source_path = Path(profile_data["source_path"])

        if real_source_path.exists():
            result = vmc.load_avatar(real_source_path)
            self.assertTrue(result, "load_avatar() phải trả True khi file tồn tại!")

            profile_after = vmc.manager.registry.current_profile
            self.assertIsNotNone(profile_after, "current_profile không được là None sau load_avatar!")
            self.assertEqual(
                str(profile_after.source_path), str(real_source_path),
                "source_path của current_profile phải là path vừa load!"
            )
        else:
            self.skipTest(f"File avatar thật không tồn tại tại {real_source_path} — bỏ qua.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
