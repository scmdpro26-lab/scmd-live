import os
import sys
import tarfile
import urllib.request
import json
import subprocess
import shutil

def main():
    scratch_dir = "scratch"
    os.makedirs(scratch_dir, exist_ok=True)
    
    tar_path = os.path.join(scratch_dir, "protobuf3_to_dict.tar.gz")
    extract_path = os.path.join(scratch_dir, "protobuf3_to_dict_extracted")
    
    # 1. Query PyPI JSON API to get the exact download URL of protobuf3-to-dict
    pypi_json_url = "https://pypi.org/pypi/protobuf3-to-dict/json"
    print(f"Querying PyPI JSON API: {pypi_json_url}...")
    try:
        req = urllib.request.Request(pypi_json_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            pypi_data = json.loads(response.read().decode("utf-8"))
            
        releases = pypi_data.get("releases", {})
        version = "0.1.5"
        urls = releases.get(version, [])
        download_url = None
        for u in urls:
            if u.get("url", "").endswith(".tar.gz"):
                download_url = u["url"]
                break
                
        if not download_url:
            raise ValueError(f"Could not find .tar.gz release for version {version}")
            
        print(f"Found exact download URL: {download_url}")
    except Exception as e:
        print(f"Error querying PyPI: {e}")
        # Fallback link
        download_url = "https://files.pythonhosted.org/packages/source/p/protobuf3-to-dict/protobuf3-to-dict-0.1.5.tar.gz"
        print(f"Using fallback URL: {download_url}")
        
    # 2. Download the file
    print("Downloading file...")
    try:
        req_dl = urllib.request.Request(download_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_dl) as response, open(tar_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        print("Download success.")
    except Exception as e:
        print(f"Error downloading: {e}")
        sys.exit(1)
        
    # 3. Extract locally without using pip
    print("Extracting archive...")
    if os.path.exists(extract_path):
        shutil.rmtree(extract_path)
    os.makedirs(extract_path, exist_ok=True)
    
    try:
        # Patch to prevent ALLOW_MISSING bug in Python 3.12
        import ntpath
        ntpath.ALLOW_MISSING = True
        
        with tarfile.open(tar_path, "r:gz") as tar:
            tar.extractall(path=extract_path)
        print("Extraction success.")
    except Exception as e:
        print(f"Error extracting: {e}")
        sys.exit(1)
        
    # Find setup.py folder
    inner_dir = None
    for d in os.listdir(extract_path):
        d_path = os.path.join(extract_path, d)
        if os.path.isdir(d_path) and os.path.exists(os.path.join(d_path, "setup.py")):
            inner_dir = d_path
            break
            
    if not inner_dir:
        print("Error: setup.py directory not found inside extraction folder.")
        sys.exit(1)
        
    # 4. Install protobuf3-to-dict from local folder (pip doesn't unpack anything, so it succeeds)
    pip_exe = os.path.join(".venv", "Scripts", "pip.exe")
    print(f"Installing protobuf3-to-dict from local directory: {inner_dir}...")
    try:
        # We use --no-build-isolation to avoid pip spawning an isolated process that runs into the unpack issue
        subprocess.run([pip_exe, "install", "--no-build-isolation", inner_dir], check=True)
        print("Installed protobuf3-to-dict successfully.")
    except Exception as e:
        print("Attempting standard install without build isolation flag...")
        try:
            subprocess.run([pip_exe, "install", inner_dir], check=True)
            print("Installed protobuf3-to-dict successfully.")
        except Exception as e2:
            print(f"Error installing protobuf3-to-dict: {e2}")
            sys.exit(1)
            
    # 5. Install requirements.txt
    print("Installing remaining dependencies from requirements.txt...")
    try:
        subprocess.run([pip_exe, "install", "-r", "requirements.txt"], check=True)
        print("All dependencies installed successfully!")
    except Exception as e:
        print(f"Error installing remaining requirements: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
