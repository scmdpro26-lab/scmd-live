import urllib.request

url = "https://raw.githubusercontent.com/HearthSim/UnityPack/master/unitypack/assetbundle.py"
try:
    with urllib.request.urlopen(url) as response:
        content = response.read().decode('utf-8')
        lines = content.splitlines()
        
        # Find def load_unityfs
        start_line = -1
        for i, l in enumerate(lines):
            if "def load_unityfs" in l:
                start_line = i
                break
                
        if start_line != -1:
            print(f"Found load_unityfs at line {start_line+1}:")
            for j in range(start_line, min(len(lines), start_line + 60)):
                print(f"{j+1}: {lines[j]}")
        else:
            print("load_unityfs not found")
except Exception as e:
    print("Error:", e)
