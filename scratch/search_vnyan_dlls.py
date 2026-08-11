import os

def main():
    print("Searching for Jayo or VMC assemblies in VNyan Managed directory...")
    path = "d:/SCMD_Tech/13.autolive/vnyan/VNyan_Data/Managed"
    if os.path.exists(path):
        for file in os.listdir(path):
            if "jayo" in file.lower() or "vmc" in file.lower() or "osc" in file.lower():
                print(f"  FOUND DLL: {file}")
    else:
        print("Managed folder not found!")

if __name__ == "__main__":
    main()
