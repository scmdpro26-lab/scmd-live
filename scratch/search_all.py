import os

def main():
    term = "renderer"
    print(f"Searching for '{term}' in all project files...")
    for root, dirs, files in os.walk("d:/SCMD_Tech/13.autolive"):
        if "venv" in root or "vnyan" in root or ".git" in root or ".gemini" in root:
            continue
        for file in files:
            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if term in content.lower():
                    print(f"FOUND in: {path}")
                    # print matching line numbers
                    lines = content.splitlines()
                    for idx, line in enumerate(lines):
                        if term in line.lower():
                            print(f"  Line {idx+1}: {line.strip()}")
            except Exception:
                pass

if __name__ == "__main__":
    main()
