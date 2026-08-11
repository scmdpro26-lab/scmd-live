import sys
sys.stdout.reconfigure(encoding='utf-8')
with open("d:/SCMD_Tech/13.autolive/src/web/server.py", "r", encoding="utf-8") as f:
    for idx, line in enumerate(f, 1):
        if "vmc" in line.lower() or "osc" in line.lower():
            print(f"{idx}: {line.strip()}")
