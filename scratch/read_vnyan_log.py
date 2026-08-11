import os

def main():
    path = "C:/Users/quanying_zhang/AppData/LocalLow/Suvidriel/VNyan/Player.log"
    if os.path.exists(path):
        print("Searching Player.log for network or error messages...")
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        
        # print last 50 lines first
        print("\n=== LAST 50 LINES OF Player.log ===")
        for line in lines[-50:]:
            print(line.strip())
            
        print("\n=== OSC/VMC RELATED LOGS ===")
        for line in lines:
            if "osc" in line.lower() or "vmc" in line.lower() or "port" in line.lower() or "listen" in line.lower():
                print(line.strip())
    else:
        print("Player.log not found!")

if __name__ == "__main__":
    main()
