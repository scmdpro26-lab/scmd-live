import urllib.request

url = "https://raw.githubusercontent.com/HearthSim/UnityPack/master/unitypack/assetbundle.py"
try:
    with urllib.request.urlopen(url) as response:
        content = response.read().decode('utf-8')
        lines = content.splitlines()
        print(f"Downloaded assetbundle.py. Total lines: {len(lines)}")
        print("First 20 lines:")
        for l in lines[:20]:
            print(l)
        print("\nLines 80 to 110:")
        for l in lines[80:110]:
            print(l)
except Exception as e:
    print("Error:", e)
