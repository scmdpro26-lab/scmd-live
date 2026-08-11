import os

def main():
    term = "Renderer 3D"
    print(f"Searching for '{term}' in the entire project...")
    for root, dirs, files in os.walk("d:/SCMD_Tech/13.autolive"):
        # skip virtualenv and vnyan folders
        if "venv" in root or "vnyan" in root or ".git" in root or ".gemini" in root:
            continue
        for file in files:
            if file.endswith((".py", ".js", ".html", ".json", ".md", ".txt")):
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
