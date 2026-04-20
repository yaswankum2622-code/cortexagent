"""Helper: print LAN URLs for accessing CortexAgent from other devices."""

import socket


def find_local_ip() -> str:
    """Find the local LAN IP address of this machine."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main() -> None:
    ip = find_local_ip()
    print("=" * 60)
    print("CortexAgent — LAN Access URLs")
    print("=" * 60)
    print()
    print("  Local laptop access:")
    print("    Streamlit UI:   http://localhost:8501")
    print("    FastAPI Swagger: http://localhost:8000/docs")
    print()
    print("  Other devices on same WiFi (phone, tablet, friend's laptop):")
    print(f"    Streamlit UI:   http://{ip}:8501")
    print(f"    FastAPI Swagger: http://{ip}:8000/docs")
    print()
    print("Tip: Open the LAN URL on your phone to demo from a mobile device.")
    print("=" * 60)


if __name__ == "__main__":
    main()
