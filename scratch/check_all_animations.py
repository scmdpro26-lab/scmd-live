import pathlib

def main():
    print("Searching for all animation files (*.vnanim, *.fbx, *.anim) in VNyan directory...")
    vnyan_dir = pathlib.Path("D:/SCMD_Tech/13.autolive/vnyan")
    
    files = []
    for ext in ["*.vnanim", "*.fbx", "*.anim"]:
        for p in vnyan_dir.rglob(ext):
            files.append(p)
            
    print(f"Found {len(files)} animation files:")
    for f in sorted(files):
        # Print size and relative path
        rel = f.relative_to(vnyan_dir)
        size = f.stat().st_size
        print(f" - {rel} ({size} bytes)")

if __name__ == "__main__":
    main()
