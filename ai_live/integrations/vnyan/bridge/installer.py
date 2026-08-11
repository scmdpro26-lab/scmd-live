import json
import logging
import uuid
import os
from pathlib import Path
from ..detector import VNyanDetector

logger = logging.getLogger("NodeGraphInstaller")

class NodeGraphInstaller:
    def __init__(self, detector: VNyanDetector):
        self.detector = detector
        self.manifest_path = Path("profiles/vnyan_bridge_manifest.json")
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.warnings = []

    def _scan_vnanim_clips(self, vnanim_path) -> dict[str, str]:
        """Đọc tất cả AnimationClip names từ Unity bundle .vnanim bằng UnityPy.
        
        Returns:
            Dict mapping ``clip_name.lower()`` -> ``clip_name`` (tên gốc).
        """
        clips = {}
        try:
            import UnityPy
            env = UnityPy.load(str(vnanim_path))
            for obj in env.objects:
                if obj.type.name == "AnimationClip":
                    try:
                        data = obj.read()
                        name = data.m_Name
                        if name and len(name) > 1:
                            clips[name.lower()] = name
                    except Exception:
                        pass
        except ImportError:
            logger.debug("UnityPy không khả dụng — không thể đọc clip names từ .vnanim")
        except Exception as e:
            logger.warning(f"Lỗi đọc clip từ {vnanim_path}: {e}")
        return clips

    def _discover_animation(self, action: str, basic_motions_exists: bool) -> str:
        """Resolve the animation name for a given action using directories or basic motions fallback.
        
        Ưu tiên:
        1. Tìm file animation tùy chỉnh trùng tên action (trong thư mục Animations/ của VNyan).
        2. Quét clip names bên trong các file .vnanim tại Items/Animations/ để tìm khớp.
        3. Dùng fallback map dựa trên các clip thực sự có trong file BasicMotions.vnanim.
        4. Nếu không tìm được → ACTION_UNBOUND.
        """
        action_lower = action.lower()
        
        # --- Bước 1: Tìm custom animation file trùng tên action ---
        exe_path = self.detector.detect_vnyan_exe()
        anim_dirs = []
        if exe_path:
            anim_dirs.append(exe_path.parent / "Animations")
        config_dir = self.detector.get_config_dir()
        if config_dir:
            anim_dirs.append(config_dir / "Animations")
            
        for d in anim_dirs:
            if d.exists() and d.is_dir():
                try:
                    for file in d.iterdir():
                        if file.is_file() and file.suffix.lower() in [".vnanim", ".fbx", ".anim"]:
                            if file.stem.lower() == action_lower:
                                return file.stem
                except Exception as e:
                    logger.warning(f"Không thể đọc thư mục animation {d}: {e}")

        # --- Bước 2: Quét clip names bên trong các .vnanim files tại Items/Animations/ ---
        # Đây là nơi VNyan lưu animation pack (ví dụ BasicMotions.vnanim)
        items_anim_dirs = []
        if exe_path:
            items_anim_dirs.append(exe_path.parent / "Items" / "Animations")
        
        all_clips: dict[str, str] = {}  # lower -> original name
        pack_clips: dict[str, dict[str, str]] = {}  # pack_name -> {lower -> original}
        
        for items_dir in items_anim_dirs:
            if items_dir.exists() and items_dir.is_dir():
                try:
                    for vnanim_file in items_dir.iterdir():
                        if vnanim_file.is_file() and vnanim_file.suffix.lower() == ".vnanim":
                            clips = self._scan_vnanim_clips(vnanim_file)
                            pack_name = vnanim_file.stem  # e.g. "BasicMotions"
                            pack_clips[pack_name] = clips
                            all_clips.update(clips)
                except Exception as e:
                    logger.warning(f"Không thể đọc thư mục Items/Animations {items_dir}: {e}")

        # --- Quy trình chặt chẽ: Loại bỏ fuzzy match cho các Action cốt lõi / E-commerce ---
        canonical_actions = [
            "Greeting", "Clap", "Heart", "PointUp", "Dance",
            "Apology", "VoucherDrop", "MinigameStart", "CartPin", "CheckoutSuccess",
            "PointDown", "PresentLeft", "PresentRight", "Celebrate", "VoucherShow"
        ]

        # Định nghĩa bảng ánh xạ tĩnh cố định (Static Mapping) chất lượng nhất
        hardcoded_mapping = {
            "Greeting":        "touchgrass",
            "Clap":            "basicmotions@clap01",
            "Heart":           "basicmotions@clap01",  # Tim dùng clap
            "PointUp":         "basicmotions@clap01",  # Chỉ lên dùng clap
            "Dance":           "gangnam",
            "Apology":         "touchgrass",
            "VoucherDrop":     "basicmotions@clap01",
            "MinigameStart":   "gangnam",
            "CartPin":         "basicmotions@clap01",
            "CheckoutSuccess": "basicmotions@clap01",
            "PointDown":       "basicmotions@clap01",
            "PresentLeft":     "touchgrass",
            "PresentRight":    "touchgrass",
            "Celebrate":       "gangnam",
            "VoucherShow":     "basicmotions@clap01",
        }

        if action in canonical_actions:
            if basic_motions_exists:
                target_clip_key = hardcoded_mapping.get(action)
                if target_clip_key:
                    # So khớp chính xác 100% (Exact Match) tên clip trong file pack
                    for pack_name, pack_clip_dict in pack_clips.items():
                        if target_clip_key in pack_clip_dict:
                            full_name = f"{pack_clip_dict[target_clip_key]} ({pack_name})"
                            logger.info(f"NodeGraphInstaller: Action '{action}' → clip '{full_name}' (exact static mapping)")
                            return full_name
            
            # Fallback nếu basic motions không tồn tại hoặc không khớp exact name
            msg = f"Hành động quan trọng '{action}' không được gán hoạt ảnh (ACTION_UNBOUND)."
            logger.warning(f"NodeGraphInstaller: {msg}")
            self.warnings.append(msg)
            return "ACTION_UNBOUND"

        # --- Fuzzy Match Lookup chỉ dành cho các Action tự do ngoài danh sách canonical (nếu có) ---
        action_keywords = {
            "Greeting":       ["wave", "hello", "greet", "salute"],
            "Clap":           ["clap", "applau"],
        }

        keywords = action_keywords.get(action, [action_lower])
        for kw in keywords:
            for clip_lower, clip_original in all_clips.items():
                if clip_lower in ["tpose", "mixamo.com", "tposedance"]:
                    continue
                if len(kw) <= 2:
                    pattern = rf"\b{re.escape(kw)}\b"
                    matched = bool(re.search(pattern, clip_lower))
                else:
                    matched = kw in clip_lower
                    
                if matched:
                    for pack_name, pack_clip_dict in pack_clips.items():
                        if clip_lower in pack_clip_dict:
                            full_name = f"{clip_original} ({pack_name})"
                            logger.info(f"NodeGraphInstaller: Action '{action}' → clip '{full_name}' (fuzzy match '{kw}')")
                            return full_name
                    return clip_original

        return "ACTION_UNBOUND"



    def install_ai_live_bridge(self) -> bool:
        """Cài đặt và đồng bộ đồ thị Node Graph AI Live Bridge thực tế (V3)."""
        self.warnings = []

        # 1. Kiểm tra an toàn: Không ghi đè redeems.json khi VNyan đang chạy
        from ..discovery import VNyanDiscovery
        discovery = VNyanDiscovery(self.detector)
        try:
            instance = discovery.discover()
            if instance.running:
                msg = "Không thể cài đặt Node Graph: Tiến trình VNyan.exe đang chạy. Hãy tắt VNyan trước khi cài đặt."
                logger.error(msg)
                self.warnings.append(msg)
                return False
        except Exception as e:
            logger.warning(f"Lỗi kiểm tra trạng thái VNyan: {e}")

        config_dir = self.detector.get_config_dir()
        if not config_dir or not config_dir.exists():
            logger.warning("Thư mục cấu hình VNyan không tồn tại. Không thể cài đặt Node Graph.")
            return False
            
        # Chỉ ghi vào redeems.json — không ghi vào các file mirror của VNyan (asredeems.json, v.v.)
        graph_files = [config_dir / "redeems.json"]

        
        # Xoá các file mirror cũ của VNyan (as*.json) để VNyan không nạp nhầm file cũ theo thứ tự alphabetical
        try:
            for file in config_dir.iterdir():
                if file.is_file() and file.name.endswith(".json") and file.name != "redeems.json" \
                        and file.name not in ("security.json", "settings.json") \
                        and (file.name.startswith("as") or file.name.endswith("_as.json")):
                    logger.info(f"Xoá file mirror cũ của VNyan: {file.name}")
                    file.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Không thể xoá file mirror VNyan: {e}")
            
        # 2. Check if BasicMotions exists
        exe_path = self.detector.detect_vnyan_exe()
        basic_motions_exists = False
        if exe_path:
            basic_motions_path = exe_path.parent / "Items" / "Animations" / "BasicMotions.vnanim"
            if basic_motions_path.exists():
                basic_motions_exists = True

        success_all = True
        has_unbound = False
        manifest_actions = {}
        
        canonical_actions = [
            # 10 actions cốt lõi (giữ nguyên)
            "Greeting", "Clap", "Heart", "PointUp", "Dance",
            "Apology", "VoucherDrop", "MinigameStart", "CartPin", "CheckoutSuccess",
            # 5 actions e-commerce mới
            "PointDown", "PresentLeft", "PresentRight", "Celebrate", "VoucherShow",
        ]

        action_keys = {
            "Greeting": "greeting", "Clap": "clap", "Heart": "heart",
            "PointUp": "point_up", "Dance": "dance", "Apology": "apology",
            "VoucherDrop": "voucher_drop", "MinigameStart": "minigame_start",
            "CartPin": "cart_pin", "CheckoutSuccess": "checkout_success",
            "PointDown": "point_down", "PresentLeft": "present_left",
            "PresentRight": "present_right", "Celebrate": "celebrate",
            "VoucherShow": "voucher_show",
        }

        # Nạp cấu hình từ Manifest để đảm bảo đồng bộ
        manifest_data = {}
        manifest_path = Path("profiles/action_manifest.json")
        if manifest_path.exists() and "mock_config" not in str(self.detector.get_config_dir()):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
            except Exception as e:
                logger.error(f"Installer: Lỗi đọc action_manifest.json: {e}")


        # Mở rộng dọn dẹp triệt để các Node Trigger và API cũ (BLOCKER 7)
        target_trigger_paths = []
        target_api_actions = ["AI_LIVE_TEST_CLAP"]
        for act in canonical_actions:
            act_key = action_keys[act].upper()
            target_trigger_paths.extend([
                act,
                f"/VMC/Ext/Action/{act}",
                f"AI_LIVE_{act_key}",
                f"/VMC/Ext/Action/AI_LIVE_{act_key}"
            ])
            target_api_actions.append(f"AI_LIVE_{act_key}")

        for graph_path in graph_files:
            logger.info(f"Đang đồng bộ Node Graph cho tệp: {graph_path.name}")
            # Load đồ thị hiện tại hoặc khởi tạo mới
            data = {"nodes": [], "connections": []}
            if graph_path.exists():
                try:
                    with open(graph_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    pass
                    
            if not isinstance(data, dict):
                data = {"nodes": [], "connections": []}
                
            nodes = data.get("nodes", [])
            if not isinstance(nodes, list):
                nodes = []
                data["nodes"] = nodes
                
            connections = data.get("connections", [])
            if not isinstance(connections, list):
                connections = []
                data["connections"] = connections

            # Find trigger nodes to delete
            trigger_ids_to_delete = set()
            socket_ids_to_delete = set()
            
            for node in nodes:
                if node.get("path") == "Nodes/TriggerNode":
                    for val in node.get("values", []):
                        if val.get("key") == "triggerName" and val.get("value") in target_trigger_paths:
                            trigger_ids_to_delete.add(node.get("id"))
                            socket_ids_to_delete.update(node.get("outputSocketIds", []))
                            break
                elif node.get("path") == "Nodes/APIMessageNode":
                    for val in node.get("values", []):
                        if val.get("key") == "action" and val.get("value") in target_api_actions:
                            trigger_ids_to_delete.add(node.get("id"))
                            socket_ids_to_delete.update(node.get("outputSocketIds", []))
                            break
                            
            # Find connection and connected play nodes to delete
            connection_ids_to_delete = set()
            play_node_ids_to_delete = set()
            
            for conn in connections:
                out_sock = conn.get("outputSocketId")
                in_sock = conn.get("inputSocketId")
                if out_sock in socket_ids_to_delete:
                    connection_ids_to_delete.add(conn.get("id"))
                    # Find the play node connected to this input socket
                    for node in nodes:
                        if node.get("path") == "Nodes/PlayAnimNode":
                            if in_sock in node.get("inputSocketIds", []):
                                play_node_ids_to_delete.add(node.get("id"))
                                socket_ids_to_delete.update(node.get("inputSocketIds", []))
                                break

            # Remove the identified nodes and connections
            nodes = [n for n in nodes if n.get("id") not in trigger_ids_to_delete and n.get("id") not in play_node_ids_to_delete]
            connections = [c for c in connections if c.get("id") not in connection_ids_to_delete]

            y_pos = 500
            for action in canonical_actions:
                action_key = action_keys[action].upper()
                canonical_id = f"AI_LIVE_{action_key}"

                # Lấy tên animation chính thức từ Manifest (BLOCKER 5)
                anim_name = "ACTION_UNBOUND"
                if canonical_id in manifest_data:
                    anim_name = manifest_data[canonical_id].get("animation", "ACTION_UNBOUND")
                
                # Nếu không khớp hoặc rỗng, dùng cơ chế dò quét tự động cũ
                if anim_name == "ACTION_UNBOUND":
                    anim_name = self._discover_animation(action, basic_motions_exists)
                    
                if anim_name == "ACTION_UNBOUND":
                    has_unbound = True
                    
                # Tạo UUID định danh xác định để đồng bộ đồng nhất giữa các tệp đồ thị
                namespace = uuid.NAMESPACE_DNS
                api_node_id = str(uuid.uuid5(namespace, f"ai_live_api_node_{action}"))
                udp_node_id = str(uuid.uuid5(namespace, f"ai_live_udp_node_{action}"))
                play_id = str(uuid.uuid5(namespace, f"ai_live_play_{action}"))
                
                api_out_sock = str(uuid.uuid5(namespace, f"ai_live_api_outsock_{action}"))
                udp_out_sock = str(uuid.uuid5(namespace, f"ai_live_udp_outsock_{action}"))
                in_sock = str(uuid.uuid5(namespace, f"ai_live_insock_{action}"))
                
                api_conn_id = str(uuid.uuid5(namespace, f"ai_live_api_conn_{action}"))
                udp_conn_id = str(uuid.uuid5(namespace, f"ai_live_udp_conn_{action}"))
                
                # Generate deterministic UUIDs for value output sockets (API message)
                val_out_1 = str(uuid.uuid5(namespace, f"ai_live_valout1_{action}"))
                val_out_2 = str(uuid.uuid5(namespace, f"ai_live_valout2_{action}"))
                val_out_3 = str(uuid.uuid5(namespace, f"ai_live_valout3_{action}"))
                
                # 1. Tạo APIMessageNode (cho HTTP REST)
                api_node = {
                    "id": api_node_id,
                    "values": [
                        {"key": "action", "value": canonical_id},
                        {"key": "dict", "value": ""}
                    ],
                    "posX": -350.0,
                    "posY": float(y_pos),
                    "path": "Nodes/APIMessageNode",
                    "ownerBlockId": "",
                    "inputSocketIds": [],
                    "outputSocketIds": [api_out_sock],
                    "headerColor": 0,
                    "inputValueSocketIds": [],
                    "outputValueSocketIds": [val_out_1, val_out_2, val_out_3]
                }

                # 2. Tạo TriggerNode (cho VMC UDP Fallback - BLOCKER 4)
                udp_node = {
                    "id": udp_node_id,
                    "values": [
                        {"key": "triggerName", "value": f"/VMC/Ext/Action/{canonical_id}"},
                        {"key": "dict", "value": ""}
                    ],
                    "posX": -350.0,
                    "posY": float(y_pos - 70),
                    "path": "Nodes/TriggerNode",
                    "ownerBlockId": "",
                    "inputSocketIds": [],
                    "outputSocketIds": [udp_out_sock],
                    "headerColor": 0,
                    "inputValueSocketIds": [],
                    "outputValueSocketIds": []
                }
                
                # Tùy biến tham số blend dựa trên loại action để tránh nhân vật bị lún/ngồi xuống
                blend_hip_pos = "1"
                blend_root = "1"
                blend_left_leg = "1"
                blend_right_leg = "1"
                
                # 1. Các hành động nhảy múa (nhảy Gangnam): giữ chân nhún nhảy, nhưng khóa chiều cao hông
                if action in ["Dance", "Celebrate"]:
                    blend_hip_pos = "0"
                    blend_root = "0"
                    blend_left_leg = "1"
                    blend_right_leg = "1"
                # 2. Toàn bộ các cử chỉ tương tác khác: khóa cứng thân dưới (đứng thẳng), chỉ chạy thân trên
                else:
                    blend_hip_pos = "0"
                    blend_root = "0"
                    blend_left_leg = "0"
                    blend_right_leg = "0"

                play_node = {
                    "id": play_id,
                    "values": [
                        {"key": "name", "value": anim_name},
                        {"key": "leapOverride", "value": "1"},
                        {"key": "blendHead", "value": "1"},
                        {"key": "blendNeck", "value": "1"},
                        {"key": "blendSpine", "value": "1"},
                        {"key": "blendHipRot", "value": "1"},
                        {"key": "blendHipPos", "value": blend_hip_pos},
                        {"key": "blendRoot", "value": blend_root},
                        {"key": "blendLeftLeg", "value": blend_left_leg},
                        {"key": "blendRightLeg", "value": blend_right_leg},
                        {"key": "blendRightArm", "value": "1"},
                        {"key": "blendRightHand", "value": "1"},
                        {"key": "blendRightFingers", "value": "1"},
                        {"key": "blendLeftArm", "value": "1"},
                        {"key": "blendLeftHand", "value": "1"},
                        {"key": "blendLeftFingers", "value": "1"},
                        {"key": "seconds", "value": ""},
                        {"key": "eyes", "value": "0"},
                        {"key": "teffects", "value": "1"}
                    ],
                    "posX": 150.0,
                    "posY": float(y_pos),
                    "path": "Nodes/PlayAnimNode",
                    "ownerBlockId": "",
                    "inputSocketIds": [in_sock],
                    "outputSocketIds": [],
                    "headerColor": 0,
                    "inputValueSocketIds": [],
                    "outputValueSocketIds": []
                }

                # Tạo 2 Connection nối API node và UDP node vào PlayAnimNode
                api_connection = {
                    "id": api_conn_id,
                    "outputSocketId": api_out_sock,
                    "inputSocketId": in_sock
                }
                udp_connection = {
                    "id": udp_conn_id,
                    "outputSocketId": udp_out_sock,
                    "inputSocketId": in_sock
                }
                
                nodes.append(api_node)
                nodes.append(udp_node)
                nodes.append(play_node)
                connections.append(api_connection)
                connections.append(udp_connection)
                
                manifest_actions[action] = {
                    "api_node_id": api_node_id,
                    "udp_node_id": udp_node_id,
                    "play_node_id": play_id,
                    "api_output_socket": api_out_sock,
                    "udp_output_socket": udp_out_sock,
                    "input_socket": in_sock,
                    "api_connection_id": api_conn_id,
                    "udp_connection_id": udp_conn_id,
                    "animation_name": anim_name
                }
                
                y_pos -= 180

            # Update data back to data dict
            data["nodes"] = nodes
            data["connections"] = connections
            
            # Remove legacy data["redeems"] AI Live entries if any
            if "redeems" in data:
                data["redeems"] = [r for r in data["redeems"] if not (str(r.get("name", "")).startswith("AI_LIVE_BRIDGE_") or str(r.get("id", "")).startswith("AI_LIVE_BRIDGE_"))]
                if not data["redeems"]:
                    del data["redeems"]

            # Save to graph file
            try:
                temp_path = str(graph_path) + ".tmp"
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                os.replace(temp_path, str(graph_path))
            except Exception as e:
                logger.error(f"Lỗi khi ghi tệp đồ thị {graph_path.name}: {e}")
                success_all = False

        if success_all:
            # Write manifest
            try:
                manifest = {
                    "schema_version": 1,
                    "graph_file": "redeems.json",
                    "status": "DEGRADED" if has_unbound else "READY",
                    "actions": manifest_actions
                }
                with open(self.manifest_path, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=4)
                logger.info("Đã cài đặt đồ thị AI Live Bridge thành công cho toàn bộ tệp redeems*.json.")
                return True
            except Exception as e:
                logger.error(f"Lỗi khi ghi manifest: {e}")
                return False
        return False

    def rollback(self) -> bool:
        """Gỡ bỏ toàn bộ node của AI Live Bridge khỏi tất cả đồ thị."""
        # 1. Kiểm tra an toàn: Không gỡ bỏ Node Graph khi VNyan đang chạy
        from ..discovery import VNyanDiscovery
        discovery = VNyanDiscovery(self.detector)
        try:
            instance = discovery.discover()
            if instance.running:
                logger.error("Không thể gỡ bỏ Node Graph: Tiến trình VNyan.exe đang chạy. Hãy tắt VNyan trước khi thực hiện rollback.")
                return False
        except Exception as e:
            logger.warning(f"Lỗi kiểm tra trạng thái VNyan: {e}")

        config_dir = self.detector.get_config_dir()
        if not config_dir or not config_dir.exists():
            return True
            
        graph_files = []

        try:
            for file in config_dir.iterdir():
                if file.is_file() and file.name.startswith("redeems") and file.name.endswith(".json"):
                    graph_files.append(file)
        except Exception:
            pass
            
        if not graph_files:
            return True
            
        success_all = True
        
        # Read manifest to find IDs
        trigger_ids = set()
        play_ids = set()
        conn_ids = set()
        
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    m_data = json.load(f)
                    for action, info in m_data.get("actions", {}).items():
                        trigger_ids.add(info.get("trigger_node_id"))
                        play_ids.add(info.get("play_node_id"))
                        conn_ids.add(info.get("connection_id"))
            except Exception:
                pass
                
        canonical_actions = [
            "Greeting", "Clap", "Heart", "PointUp", "Dance",
            "Apology", "VoucherDrop", "MinigameStart", "CartPin", "CheckoutSuccess",
            "PointDown", "PresentLeft", "PresentRight", "Celebrate", "VoucherShow",
        ]
        target_paths = [action for action in canonical_actions] + [f"/VMC/Ext/Action/{action}" for action in canonical_actions]

        for graph_path in graph_files:
            try:
                with open(graph_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                if not isinstance(data, dict):
                    continue
                    
                nodes = data.get("nodes", [])
                connections = data.get("connections", [])
                
                # If manifest didn't resolve anything, fall back to scan-based
                t_ids = set(trigger_ids)
                p_ids = set(play_ids)
                c_ids = set(conn_ids)
                
                if not t_ids:
                    for node in nodes:
                        if node.get("path") == "Nodes/TriggerNode":
                            for val in node.get("values", []):
                                if val.get("key") == "triggerName" and val.get("value") in target_paths:
                                    t_ids.add(node.get("id"))
                                    break

                # Filter nodes and connections
                data["nodes"] = [n for n in nodes if n.get("id") not in t_ids and n.get("id") not in p_ids]
                data["connections"] = [c for c in connections if c.get("id") not in c_ids]
                
                # Clean up old redeems key
                if "redeems" in data:
                    data["redeems"] = [r for r in data["redeems"] if not (str(r.get("name", "")).startswith("AI_LIVE_BRIDGE_") or str(r.get("id", "")).startswith("AI_LIVE_BRIDGE_"))]
                    if not data["redeems"]:
                        del data["redeems"]

                temp_path = str(graph_path) + ".tmp"
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                os.replace(temp_path, str(graph_path))
            except Exception as e:
                logger.error(f"Lỗi khi rollback tệp đồ thị {graph_path.name}: {e}")
                success_all = False
                
        if self.manifest_path.exists():
            try:
                os.remove(self.manifest_path)
            except Exception:
                pass
                
        logger.info("Đã hoàn tất gỡ bỏ đồ thị AI Live Bridge khỏi các tệp đồ thị.")
        return success_all
