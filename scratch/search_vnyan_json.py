import os

def main():
    print("Searching for files containing 'OSC' or 'VMC' in vnyan folder...")
    for root, dirs, files in os.walk("d:/SCMD_Tech/13.autolive/vnyan"):
        for file in files:
            if file.endswith(".json"):
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        if "OSC" in content or "VMC" in content:
                            print(f"FOUND: {path}")
                except Exception:
                    pass

if __name__ == "__main__":
    main()
