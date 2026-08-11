import os
import json
import logging
from pathlib import Path
from ..detector import VNyanDetector

logger = logging.getLogger("NodeGraphManager")

class NodeGraphManager:
    def __init__(self, detector: VNyanDetector):
        self.detector = detector
        self.manifest_path = Path("profiles/vnyan_bridge_manifest.json")

    def validate_graph(self, graph_data: dict, manifest_data: dict, log_warnings: bool = False) -> tuple[bool, bool]:
        """Validate the installed graph nodes, sockets, connections, and animation bindings.
        Returns: (schema_valid, has_unbound)
        """
        if not isinstance(graph_data, dict) or not isinstance(manifest_data, dict):
            return False, False
            
        nodes = graph_data.get("nodes", [])
        connections = graph_data.get("connections", [])
        actions = manifest_data.get("actions", {})
        
        if not isinstance(nodes, list) or not isinstance(connections, list) or not isinstance(actions, dict):
            return False, False

        # Create maps for fast lookup
        nodes_by_id = {n.get("id"): n for n in nodes if isinstance(n, dict)}
        connections_by_out = {c.get("outputSocketId"): c for c in connections if isinstance(c, dict)}
        
        canonical_actions = [
            # 10 actions cốt lõi (giữ nguyên)
            "Greeting", "Clap", "Heart", "PointUp", "Dance",
            "Apology", "VoucherDrop", "MinigameStart", "CartPin", "CheckoutSuccess",
            # 5 actions e-commerce mới
            "PointDown", "PresentLeft", "PresentRight", "Celebrate", "VoucherShow",
        ]
        
        # Verify that all 10 canonical actions exist in the manifest and the graph
        has_unbound = (manifest_data.get("status") == "DEGRADED")
        
        for action in canonical_actions:
            if action not in actions:
                if log_warnings:
                    logger.warning(f"Action {action} thiếu trong manifest.")
                return False, has_unbound
                
            info = actions[action]
            trigger_id = info.get("trigger_node_id")
            play_id = info.get("play_node_id")
            out_sock = info.get("output_socket")
            in_sock = info.get("input_socket")
            anim_name = info.get("animation_name")
            
            if anim_name == "ACTION_UNBOUND":
                has_unbound = True
                
            # 1. Verify APIMessageNode
            if trigger_id not in nodes_by_id:
                if log_warnings:
                    logger.warning(f"APIMessageNode {trigger_id} cho {action} không tồn tại trong đồ thị.")
                return False, has_unbound
            trigger_node = nodes_by_id[trigger_id]
            if trigger_node.get("path") != "Nodes/APIMessageNode":
                if log_warnings:
                    logger.warning(f"APIMessageNode {trigger_id} có path sai: {trigger_node.get('path')}")
                return False, has_unbound
            if out_sock not in trigger_node.get("outputSocketIds", []):
                if log_warnings:
                    logger.warning(f"APIMessageNode {trigger_id} thiếu output socket {out_sock}")
                return False, has_unbound
            action_val = None
            for val in trigger_node.get("values", []):
                if val.get("key") == "action":
                    action_val = val.get("value")
                    break
            action_keys = {
                # 10 actions cốt lõi
                "Greeting": "greeting", "Clap": "clap", "Heart": "heart",
                "PointUp": "point_up", "Dance": "dance", "Apology": "apology",
                "VoucherDrop": "voucher_drop", "MinigameStart": "minigame_start",
                "CartPin": "cart_pin", "CheckoutSuccess": "checkout_success",
                # 5 actions e-commerce mới
                "PointDown": "point_down", "PresentLeft": "present_left",
                "PresentRight": "present_right", "Celebrate": "celebrate",
                "VoucherShow": "voucher_show",
            }
            expected_action_val = f"AI_LIVE_{action_keys[action].upper()}"
            if action_val != expected_action_val:
                if log_warnings:
                    logger.warning(f"APIMessageNode {trigger_id} có action sai: {action_val}, kì vọng {expected_action_val}")
                return False, has_unbound
                
            # 2. Verify PlayAnimNode
            if play_id not in nodes_by_id:
                if log_warnings:
                    logger.warning(f"PlayAnimNode {play_id} cho {action} không tồn tại trong đồ thị.")
                return False, has_unbound
            play_node = nodes_by_id[play_id]
            if play_node.get("path") != "Nodes/PlayAnimNode":
                if log_warnings:
                    logger.warning(f"PlayAnimNode {play_id} có path sai: {play_node.get('path')}")
                return False, has_unbound
            if in_sock not in play_node.get("inputSocketIds", []):
                if log_warnings:
                    logger.warning(f"PlayAnimNode {play_id} thiếu input socket {in_sock}")
                return False, has_unbound
                
            name_val = None
            for val in play_node.get("values", []):
                if val.get("key") == "name":
                    name_val = val.get("value")
                    break
            if not name_val: # Empty name is invalid
                if log_warnings:
                    logger.warning(f"PlayAnimNode {play_id} có tên animation rỗng.")
                return False, has_unbound
            if name_val != anim_name:
                if log_warnings:
                    logger.warning(f"PlayAnimNode {play_id} name: '{name_val}' không khớp manifest '{anim_name}'")
                return False, has_unbound
                
            # 3. Verify Connection
            if out_sock not in connections_by_out:
                if log_warnings:
                    logger.warning(f"Thiếu kết nối từ output socket {out_sock} cho {action}")
                return False, has_unbound
            conn = connections_by_out[out_sock]
            if conn.get("inputSocketId") != in_sock:
                if log_warnings:
                    logger.warning(f"Kết nối cho {action} trỏ sai input socket: {conn.get('inputSocketId')}, kì vọng {in_sock}")
                return False, has_unbound

        return True, has_unbound

    def inspect(self, log_warnings: bool = False) -> dict:
        """Kiểm tra toàn diện Node Graph thực tế theo chuẩn V3."""
        config_dir = self.detector.get_config_dir()
        result = {
            "node_exists": False,
            "schema_valid": False,
            "bridge_loaded": False,
            "event_accepted": False,
            "installed": False,
            "graphs_found": [],
            "nodes_count": 0
        }

        # 1. Kiểm tra bridge_loaded (Kiểm tra tệp manifest bridge)
        manifest_data = {}
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
                    if manifest_data.get("graph_file") == "redeems.json" and "actions" in manifest_data:
                        result["bridge_loaded"] = True
            except Exception as e:
                if log_warnings:
                    logger.warning(f"Không thể đọc tệp manifest {self.manifest_path}: {e}")

        if not config_dir or not config_dir.exists():
            return result

        # 2. Kiểm tra node_exists & schema_valid trong tệp redeems.json
        graph_path = config_dir / "redeems.json"
        if graph_path.exists():
            result["graphs_found"].append("redeems.json")
            try:
                with open(graph_path, "r", encoding="utf-8") as f:
                    graph_data = json.load(f)
                
                # Check nodes count
                nodes = graph_data.get("nodes", [])
                result["nodes_count"] = len(nodes)
                
                if result["bridge_loaded"]:
                    schema_valid, has_unbound = self.validate_graph(graph_data, manifest_data, log_warnings=log_warnings)
                    result["schema_valid"] = schema_valid
                    result["node_exists"] = schema_valid # If schema is valid, nodes must exist
                    
                    # 3. event_accepted
                    if result["node_exists"] and result["schema_valid"] and result["bridge_loaded"]:
                        result["event_accepted"] = True
                        
                    # 4. installed: Installed status is ONLY True if all are ready AND no unbound actions
                    result["installed"] = result["event_accepted"] and not has_unbound
                else:
                    # Fallback node detection (at least some TriggerNodes exist)
                    has_bridge_trigger = False
                    for node in nodes:
                        if node.get("path") == "Nodes/TriggerNode":
                            for val in node.get("values", []):
                                if str(val.get("value", "")).startswith("/VMC/Ext/Action/") or val.get("value") in ["Greeting", "Clap", "Heart", "PointUp", "Dance", "Apology", "VoucherDrop", "MinigameStart", "CartPin", "CheckoutSuccess"]:
                                    has_bridge_trigger = True
                                    break
                    result["node_exists"] = has_bridge_trigger
            except Exception as e:
                if log_warnings:
                    logger.warning(f"Lỗi khi đọc tệp đồ thị redeems.json: {e}")

        return result
