import lz4.block

def main():
    # Compressed metadata block from the end of the file (66 bytes)
    comp = bytes.fromhex('f18a23bef70c4e8117db2f9150ee987b03727cfaae4affda8814cbaf798034053e66d6746a3bad5fbc22ff5180c592eecf6279f20d25feda0f329821ffff4ad8dc00')
    
    # Try different uncompressed sizes around 91
    for sz in range(80, 120):
        try:
            res = lz4.block.decompress(comp, uncompressed_size=sz)
            print(f"Success with size {sz}!")
            print(res.hex())
            return
        except Exception:
            pass
            
    # Try prepending or removing headers?
    # Some Unity LZ4 implementations write the uncompressed size as a 4-byte header.
    # But here the uncompressed size is 91.
    print("Failed all direct lz4 block decompressions.")

if __name__ == "__main__":
    main()
