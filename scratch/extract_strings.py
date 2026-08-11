import string

def extract_strings(filepath, min_len=4):
    with open(filepath, 'rb') as f:
        data = f.read()
        
    current = bytearray()
    found_strings = []
    
    # Try ASCII
    for b in data:
        if chr(b) in string.printable and b >= 32 and b <= 126:
            current.append(b)
        else:
            if len(current) >= min_len:
                found_strings.append(current.decode('ascii', errors='ignore'))
            current = bytearray()
            
    if len(current) >= min_len:
        found_strings.append(current.decode('ascii', errors='ignore'))
        
    return found_strings

if __name__ == "__main__":
    print("Extracting strings from BasicMotions.vnanim...")
    all_strings = extract_strings("vnyan/Items/Animations/BasicMotions.vnanim", 4)
    print(f"Extracted {len(all_strings)} strings.")
    
    # Print strings that might be animation names
    keywords = ["motion", "anim", "wave", "clap", "point", "bow", "sit", "dance", "stand", "idle"]
    matching = [s for s in all_strings if any(k in s.lower() for k in keywords)]
    print("\nMatching strings:")
    for m in set(matching[:100]): # Print unique matching strings
        print(f" - {m}")
