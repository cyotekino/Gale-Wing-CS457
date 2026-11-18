import argparse
import selectors
import socket
import sys

class ClientConn:
    """Per-connection state for one client socket."""

    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.inbuf = bytearray()
        self.outbuf = bytearray()
        self.player_id = "UNASSIGNED"
        self.alias = None
        self.closed = False

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

def accept_client(sel, listen_sock):
    client_sock, addr = listen_sock.accept()
    client_sock.setblocking(False)
    conn = ClientConn(client_sock, addr)
    sel.register(client_sock, selectors.EVENT_READ, data=conn)
    print(f"[SERVER] Connection from {addr[0]}:{addr[1]}")

def main():
    args = parse_args()

    try:
        listen_sock = create_listener(args.port)
    except OSError as error:
        print(f"[ERROR] Could not listen on port {args.port}: {error}")
        sys.exit(1)

    sel = selectors.DefaultSelector()
    sel.register(listen_sock, selectors.EVENT_READ, data=None)
    print(f"[SERVER] Listening on 0.0.0.0:{args.port}")

    try:
        while True:
            events = sel.select(timeout=1.0)
            for key, mask in events:
                if key.data is None:
                    accept_client(sel, key.fileobj)
                else:
                    pass
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down")
    finally:
        sel.close()
        listen_sock.close()


if __name__ == "__main__":
    main()