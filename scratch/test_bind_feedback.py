import socket

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind(("0.0.0.0", 39540))
        print("SUCCESS: Port 39540 is FREE and can be bound!")
        s.close()
    except Exception as e:
        print(f"FAILED: Port 39540 is occupied or error: {e}")

if __name__ == "__main__":
    main()
