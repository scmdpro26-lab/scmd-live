import os

def main():
    print("Searching for VRM avatar files...")
    for root, dirs, files in os.walk("d:/SCMD_Tech/13.autolive"):
        if ".venv" in root or ".git" in root:
            continue
        for file in files:
            if file.endswith(".vrm"):
                print(f"FOUND VRM: {os.path.join(root, file)}")

if __name__ == "__main__":
    main()
