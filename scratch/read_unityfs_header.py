import struct

def read_null_string(f):
    chars = []
    while True:
        c = f.read(1)
        if not c or c == b'\x00':
            break
        chars.append(c)
    return b''.join(chars).decode('ascii')

def read_header(filepath):
    with open(filepath, 'rb') as f:
        signature = f.read(8)
        if signature != b'UnityFS\x00':
            print(f"Not a UnityFS bundle: {signature}")
            return
            
        version, = struct.unpack('>I', f.read(4))
        unity_ver = read_null_string(f)
        revision = read_null_string(f)
        
        file_size, comp_meta_size, decomp_meta_size, flags = struct.unpack(
            '>QIII', f.read(8 + 4 + 4 + 4)
        )
        
        print("UnityFS Header:")
        print(f"  Version: {version}")
        print(f"  Unity Version: {unity_ver}")
        print(f"  Revision: {revision}")
        print(f"  File Size: {file_size}")
        print(f"  Comp Meta Size: {comp_meta_size}")
        print(f"  Decomp Meta Size: {decomp_meta_size}")
        print(f"  Flags: {flags:08x}")
        
if __name__ == "__main__":
    read_header("vnyan/Items/Animations/BasicMotions.vnanim")
