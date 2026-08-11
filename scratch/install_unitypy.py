import os
import os.path
import sys

# Patch os.path to bypass Python 3.12.8 tarfile bug
if not hasattr(os.path, 'ALLOW_MISSING'):
    os.path.ALLOW_MISSING = False
    print("Patched os.path.ALLOW_MISSING = False")

import subprocess

def main():
    print("Running pip install UnityPy programmatically...")
    # Get path to current virtualenv pip or python
    python_exe = sys.executable
    cmd = [python_exe, "-m", "pip", "install", "UnityPy"]
    
    # We run it in the same process using pip module if possible, or via subprocess.
    # Wait, if we use subprocess, it will spawn a new python process which won't have the patch!
    # So we must use pip's internal main function!
    try:
        from pip._internal import main as pipmain
        print("Using pip internal main...")
        pipmain(["install", "UnityPy"])
    except Exception as e:
        print("Failed to use pip internal main, trying subprocess with custom script...")
        # If we must use subprocess, we can write a wrapper script that does the patch and then imports pip
        wrapper_path = "scratch/pip_wrapper.py"
        with open(wrapper_path, "w") as f:
            f.write("""
import os
import os.path
import sys
os.path.ALLOW_MISSING = False
from pip._internal import main as pipmain
sys.exit(pipmain(sys.argv[1:]))
""")
        subprocess.run([python_exe, wrapper_path, "install", "UnityPy"])

if __name__ == "__main__":
    main()
