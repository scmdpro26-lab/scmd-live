import os

def main():
    term = "vmc_client"
    print(f"Searching for '{term}'...")
    for root, dirs, files in os.walk("d:/SCMD_Tech/13.autolive/src"):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    for idx, line in enumerate(lines):
                        if term in line:
                            print(f"  {file}:{idx+1} -> {line.strip()}")
                except Exception:
                    pass

if __name__ == "__main__":
    main()
