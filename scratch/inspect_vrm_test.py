import struct
import json
import os

def parse_glb_json(filepath):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return None
        
    with open(filepath, "rb") as f:
        # Read header
        magic = f.read(4)
        if magic != b"glTF":
            print(f"Not a valid glTF file: {magic}")
            return None
            
        version, length = struct.unpack("<II", f.read(8))
        print(f"glTF Version: {version}, Total Length: {length} bytes")
        
        # Read chunk 0 (must be JSON)
        chunk_length, chunk_type = struct.unpack("<II", f.read(8))
        if chunk_type != 0x4E4F534A:  # b'JSON'
            print(f"Chunk 0 is not JSON: {chunk_type}")
            return None
            
        json_bytes = f.read(chunk_length)
        # Decode JSON
        json_str = json_bytes.decode("utf-8", errors="ignore")
        return json.loads(json_str)

vrm_path = r"C:\Users\quanying_zhang\Downloads\MC_TikTok_VietNam_v4_FIXED.vrm"
data = parse_glb_json(vrm_path)
if data:
    print("Successfully parsed GLB JSON!")
    # Check for VRM extension
    extensions = data.get("extensions", {})
    vrm_ext = extensions.get("VRM", {})
    if vrm_ext:
        print("VRM Extension Version:", vrm_ext.get("exporterVersion"))
        meta = vrm_ext.get("meta", {})
        print("VRM Meta:")
        for k, v in meta.items():
            if k not in ["thumbnail"]:
                print(f"  {k}: {v}")
                
        # Let's check the expressions (blendShapeGroups in VRM 0.x)
        blend_shape_master = vrm_ext.get("blendShapeMaster", {})
        groups = blend_shape_master.get("blendShapeGroups", [])
        print(f"\nFound {len(groups)} BlendShape groups:")
        for g in groups:
            print(f"  Name: {g.get('name')}, Preset: {g.get('presetName')}")
    else:
        print("VRM extension not found in glTF.")
