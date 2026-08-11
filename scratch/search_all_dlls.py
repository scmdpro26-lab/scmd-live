import os

def main():
    print("Searching for any VMC or Jayo DLLs in the entire vnyan folder...")
    for root, dirs, files in os.walk("d:/SCMD_Tech/13.autolive/vnyan"):
        for file in files:
            if file.endswith(".dll"):
                if "jayo" in file.lower() or "vmc" in file.lower() or "nyavmc" in file.lower():
                    print(f"  FOUND: {os.path.join(root, file)}")

if __name__ == "__main__":
    main()
