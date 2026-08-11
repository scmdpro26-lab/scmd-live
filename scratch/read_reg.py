import winreg

try:
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Suvidriel\VNyan")
    idx = 0
    while True:
        try:
            name, val, val_type = winreg.EnumValue(key, idx)
            print(f"{name}: {val}")
            idx += 1
        except OSError:
            break
except Exception as e:
    print(f"Lỗi đọc Registry: {e}")
