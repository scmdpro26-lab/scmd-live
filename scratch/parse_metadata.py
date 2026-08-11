import struct

def parse_metadata(meta_bytes):
    print("Metadata bytes length:", len(meta_bytes))
    
    # UnityFS metadata format (big-endian)
    # 16 bytes: GUID
    guid = meta_bytes[:16]
    print(f"GUID: {guid.hex()}")
    
    # 4 bytes: number of blocks
    num_blocks, = struct.unpack('>I', meta_bytes[16:20])
    print(f"Number of blocks: {num_blocks}")
    
    offset = 20
    blocks = []
    for i in range(num_blocks):
        # Each block:
        # 8 bytes: decompressed size
        # 8 bytes: compressed size
        # 2 bytes: flags
        decomp_size, comp_size, flags = struct.unpack('>QQH', meta_bytes[offset:offset+18])
        blocks.append((decomp_size, comp_size, flags))
        print(f"Block {i}: Decomp={decomp_size}, Comp={comp_size}, Flags={flags:04x}")
        offset += 18
        
    # 4 bytes: number of nodes (files)
    num_nodes, = struct.unpack('>I', meta_bytes[offset:offset+4])
    print(f"Number of nodes: {num_nodes}")
    offset += 4
    
    for i in range(num_nodes):
        # Each node:
        # 8 bytes: offset in decompressed data
        # 8 bytes: size
        # 4 bytes: status/flags
        # string: path/name (null-terminated)
        node_offset, node_size, node_flags = struct.unpack('>QQI', meta_bytes[offset:offset+20])
        offset += 20
        
        # Read name
        name_chars = []
        while offset < len(meta_bytes):
            c = meta_bytes[offset]
            offset += 1
            if c == 0:
                break
            name_chars.append(chr(c))
        name = ''.join(name_chars)
        print(f"Node {i}: Name={name}, Offset={node_offset}, Size={node_size}, Flags={node_flags:08x}")

if __name__ == "__main__":
    # Bytes read from the start of the file after header:
    meta = bytes.fromhex('00000000000000000000000000001e000100b101000da82c000a2b3900410e00080100001a00f0190000044341422d38346164616637313863373030333536303332')
    try:
        parse_metadata(meta)
    except Exception as e:
        print("Error parsing:", e)
