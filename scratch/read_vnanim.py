import re

path = r"d:\SCMD_Tech\13.autolive\vnyan\Items\Animations\BasicMotions.vnanim"
try:
    data = open(path, "rb").read()
    # Find all ascii strings
    strings = re.findall(b"[a-zA-Z0-9 _()-]{4,50}", data)
    unique_strings = sorted(list(set([s.decode('ascii', errors='ignore') for s in strings])))
    
    print("Found unique strings:")
    for s in unique_strings:
        s_lower = s.lower()
        if "motion" in s_lower or "anim" in s_lower or "sit" in s_lower or "clap" in s_lower or "point" in s_lower or "bow" in s_lower:
            print("  -", s)
except Exception as e:
    print("Error:", e)
