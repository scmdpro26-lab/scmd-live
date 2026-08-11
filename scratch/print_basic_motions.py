import re
from pathlib import Path

path = Path("vnyan/Items/Animations/BasicMotions.vnanim")
if path.exists():
    data = path.read_bytes()
    # Find all ascii strings
    strings = re.findall(b"[a-zA-Z0-9 _()-]{4,50}", data)
    decoded = []
    for s in strings:
        try:
            decoded.append(s.decode("ascii"))
        except Exception:
            pass
    unique_strings = sorted(list(set(decoded)))
    print("Found unique strings:")
    for s in unique_strings:
        print("  -", s)
else:
    print("File not found")
