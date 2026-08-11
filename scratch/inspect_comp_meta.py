import struct

def read_null_string(f):
    chars = []
    while True:
        c = f.read(1)
        if not c or c == b'\x00':
            break
        chars.append(c)
    return b''.join(chars).decode('ascii')

def main():
    filepath = "vnyan/Items/Animations/BasicMotions.vnanim"
    with open(filepath, 'rb') as f:
        f.read(8)
        version, = struct.unpack('>I', f.read(4))
        unity_ver = read_null_string(f)
        revision = read_null_string(f)
        
        file_size, comp_meta_size, decomp_meta_size, flags = struct.unpack(
            '>QIII', f.read(8 + 4 + 4 + 4)
        )
        
        comp_meta = f.read(comp_meta_size)
        print("Comp Meta Hex:")
        print(comp_meta.hex())
        print("Comp Meta Bytes:")
        print(comp_meta)

if __name__ == "__main__":
    main()
