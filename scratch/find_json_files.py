import os

def main():
    print("Searching for JSON files containing VMC/Ext/Action...")
    for root, dirs, files in os.walk("d:/SCMD_Tech/13.autolive"):
        # skip venv
        if ".venv" in root or ".git" in root:
            continue
        for file in files:
            if file.endswith(".json"):
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        if "VMC/Ext/Action" in content or "CheckoutSuccess" in content or "CartPin" in content:
                            print(f"FOUND MATCH IN: {path}")
                except Exception as e:
                    pass

if __name__ == "__main__":
    main()
