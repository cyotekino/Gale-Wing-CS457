import argparse
import selectors
import socket
import sys
from protocol import extract_lines, parse_message, encode_message, build_message


ROWS = "ABCDEFGHIJ"
FLEET = {"Carrier": 5, "Battleship": 4, "Cruiser": 3, "Submarine": 3, "Destroyer": 2}
TOTAL_SHIP_CELLS = 17
SHOT_LIMIT = 50
PLAYER_IDS = ("Player_1", "Player_2")


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


class GameSession:
    """All state for the current game, plus the persistent leaderboard."""

    def __init__(self):
        self.leaderboard = {}
        self.reset()

    def reset(self):
        """Clear per-game state (used at startup and in CLEANUP)."""
        self.state = "WAITING_FOR_PLAYERS"
        self.players = {}
        self.fleets = {}
        self.placed = set()
        self.shots_received = {"Player_1": set(), "Player_2": set()}
        self.active_turn = None
        self.hits = {"Player_1": 0, "Player_2": 0}
        self.shots_fired = {"Player_1": 0, "Player_2": 0}
        self.draw_offered_by = None


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


def teardown(sel, conn):
    """Unregister and close a client connection (safe to call twice)."""
    if conn.closed:
        return
    sel.unregister(conn.sock)
    conn.sock.close()
    conn.closed = True
    print(f"[SERVER] {conn.addr[0]}:{conn.addr[1]} disconnected")


def handle_read(sel, conn, session):
    """Receive data, detect EOF/errors, and process complete messages."""
    try:
        data = conn.sock.recv(4096)
    except BlockingIOError:
        return
    except OSError:
        teardown(sel, conn)
        return
    if not data:
        teardown(sel, conn)
        return
    conn.inbuf += data
    for line in extract_lines(conn.inbuf):
        msg = parse_message(line)
        if msg is None:
            send_error(sel, conn, "MALFORMED_MESSAGE", "Could not parse message", None)
        else:
            print(f"[SERVER] Received from {conn.addr[0]}:{conn.addr[1]}: {msg}")
            dispatch(sel, conn, session, msg)


def queue_message(sel, conn, msg):
    """Add a message to conn's send buffer and enable write events."""
    if conn.closed:
        return
    conn.outbuf += encode_message(msg)
    sel.modify(conn.sock, selectors.EVENT_READ | selectors.EVENT_WRITE, data=conn)


def handle_write(sel, conn):
    """Send as much of conn's buffer as the socket accepts; keep the rest."""
    try:
        sent = conn.sock.send(conn.outbuf)
    except BlockingIOError:
        return
    except OSError:
        teardown(sel, conn)
        return
    del conn.outbuf[:sent]
    if not conn.outbuf:
        sel.modify(conn.sock, selectors.EVENT_READ, data=conn)


def send_error(sel, conn, code, test, ref_msg_type):
    """Queue an ERROR message to one client."""
    payload = {"code": code, "message": test, "ref_msg_type": ref_msg_type}
    queue_message(sel, conn, build_message("ERROR", "SERVER", payload))


def dispatch(sel, conn, session, msg):
    """Validate the sender and route a message to its handler."""
    msg_type = msg["msg_type"]
    if msg_type not in HANDLERS:
        send_error(sel, conn, "INVALID_STATE", f"{msg_type} is not accepted by the server", msg_type)
        return
    if conn.player_id == "UNASSIGNED" and msg_type != "CONNECT":
        send_error(sel, conn, "NOT_CONNECTED", "Send CONNECT first", msg_type)
        return
    if conn.player_id != "UNASSIGNED" and msg["player_id"] != conn.player_id:
        send_error(sel, conn, "INVALID_PLAYER", "player_id does not match this connection", msg_type)
        return
    HANDLERS[msg_type](sel, conn, session, msg["payload"])

HANDLERS = {}


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

    session = GameSession()
    
    try:
        while True:
            events = sel.select(timeout=1.0)
            for key, mask in events:
                if key.data is None:
                    accept_client(sel, key.fileobj)
                else:
                    conn = key.data
                    if conn.closed:
                        continue
                    if mask & selectors.EVENT_READ:
                        handle_read(sel, conn, session)
                    if mask & selectors.EVENT_WRITE and not conn.closed:
                        handle_write(sel, conn)
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down")
    finally:
        sel.close()
        listen_sock.close()


if __name__ == "__main__":
    main()