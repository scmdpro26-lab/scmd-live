from pathlib import Path

path = Path("vnyan/Items/Animations/BasicMotions.vnanim")
if path.exists():
    data = path.read_bytes()
    for word in [b"Wave", b"Clap", b"Point", b"Bow", b"Ground", b"Sit", b"BasicMotions"]:
        idx = data.find(word)
        if idx != -1:
            # Print surrounding context
            start = max(0, idx - 20)
            end = min(len(data), idx + len(word) + 20)
            print(f"Found {word} at index {idx}. Context: {data[start:end]}")
        else:
            print(f"Word {word} not found")
else:
    print("File not found")
