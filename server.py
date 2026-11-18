import argparse
import selectors
import socket
import sys

def parse_args():
    parser = argparse.ArgumentParser(description="Battleship game server")
    parser.add_argument(
        "-p", "--port", type=int, required=True, help="TCP port to listen on (1024-65535)"
        )
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error(f"port {args.port} is out of range: use 1024-65535")
    return args

def create_listener(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", port))
    sock.listen()
    sock.setblocking(False)
    return sock


def main():
    """Entry point for the Battleship server."""
    args = parse_args()
    try:
        listen_sock = create_listener(args.port)
    except OSError as error:
        print(f"[ERROR] Could not listen on port {args.port}: {error}")
        sys.exit(1)

    sel = selectors.DefaultSelector()
    sel.register(listen_sock, selectors.EVENT_READ, data=None)
    print(f"[SERVER] Listening on 0.0.0.0:{args.port}")


if __name__ == "__main__":
    main()