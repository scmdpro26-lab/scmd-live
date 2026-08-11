import os
import os.path
import sys

# Patch
os.path.ALLOW_MISSING = False

try:
    import UnityPy
    print("SUCCESS: Imported UnityPy!")
    print("UnityPy path:", UnityPy.__file__)
except Exception as e:
    print("Failed to import UnityPy:", e)
    
    print("\nsys.path folders:")
    for p in sys.path:
        if p and os.path.exists(p):
            try:
                contents = os.listdir(p)
                matching = [c for c in contents if 'unity' in c.lower() or 'tpk' in c.lower()]
                if matching:
                    print(f"Path '{p}' contains: {matching}")
            except Exception as ex:
                print(f"Error reading '{p}': {ex}")
