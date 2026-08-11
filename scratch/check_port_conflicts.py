import socket
import subprocess

def test_bind(port, proto):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM if proto == "TCP" else socket.SOCK_DGRAM)
    try:
        s.bind(("127.0.0.1", port))
        s.close()
        return True # Free
    except Exception as e:
        return False # Busy

def get_pid_owner(port, proto):
    try:
        output = subprocess.check_output(f"netstat -ano", shell=True).decode("utf-8", errors="ignore")
        for line in output.splitlines():
            if f":{port} " in line or f":{port}\t" in line or line.strip().endswith(f":{port}"):
                parts = line.strip().split()
                if len(parts) >= 5:
                    return parts[-1]
    except Exception:
        pass
    return "Unknown"

def main():
    ports_to_check = [
        (3333, "UDP", "VMC Receive Port"),
        (39539, "UDP", "OSC Receive Port"),
        (39540, "UDP", "VMC Feedback Port (Python bound)"),
        (8005, "TCP", "WebSocket Port"),
        (8069, "TCP", "REST Port"),
        (8001, "TCP", "VTS Port"),
        (4455, "TCP", "OBS Port")
    ]
    
    print("Checking for port usage on local system (Bind Test):")
    for port, proto, desc in ports_to_check:
        is_free = test_bind(port, proto)
        if not is_free:
            pid = get_pid_owner(port, proto)
            print(f"  ❌ {proto} Port {port} ({desc}) is BUSY (Owner PID: {pid})")
        else:
            print(f"  ✅ {proto} Port {port} ({desc}) is FREE")

if __name__ == "__main__":
    main()
