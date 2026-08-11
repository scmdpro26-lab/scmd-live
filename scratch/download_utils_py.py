import urllib.request

url = "https://raw.githubusercontent.com/HearthSim/UnityPack/master/unitypack/utils.py"
try:
    with urllib.request.urlopen(url) as response:
        content = response.read().decode('utf-8')
        lines = content.splitlines()
        print(f"Downloaded utils.py. Total lines: {len(lines)}")
        for i, l in enumerate(lines):
            if "lz4" in l.lower() or "decompress" in l.lower():
                # Print 5 lines before and after
                start = max(0, i - 2)
                end = min(len(lines), i + 10)
                print(f"--- MATCH AT LINE {i+1} ---")
                for j in range(start, end):
                    print(f"{j+1}: {lines[j]}")
                print()
except Exception as e:
    print("Error:", e)
