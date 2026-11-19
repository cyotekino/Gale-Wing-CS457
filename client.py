import argparse
import socket
import sys
import threading

from protocol import build_message, encode_message, extract_lines, parse_message


ROWS = "ABCDEFGHIJ"
SHIP_SYMBOLS = {"water": ".", "ship": "S", "hit": "X", "miss": "o"}


class ClientState:
    """Everything the client knows about the game, shared by both threads."""

    def __init__(self):
        self.lock = threading.Lock()
        self.running = True
        self.phase = "LOBBY"
        self.player_id = "UNASSIGNED"
        self.alias = None
        self.opponent_alias = "Opponent"
        self.fleet = []
        self.my_cells = set()
        self.incoming = {}
        self.outgoing = {}
        self.scores = None
        self.next_turn = None

    def opponent_id(self):
        """Return the opponent's player ID."""
        return "Player_2" if self.player_id == "Player_1" else "Player_1"

    def my_turn(self):
        """Return True when it is this player's turn to fire."""
        return self.phase == "PLAYING" and self.next_turn == self.player_id


def parse_args():
    """Parse and validate command-line arguments."""
    parser = argparse.ArgumentParser(description="Battleship game client")
    parser.add_argument(
        "-i", "--host", dest="hostname", required=True,
        help="server DNS hostname or IP address (e.g. server.wing.edu)",
    )
    parser.add_argument(
        "-p", "--port", type=int, required=True,
        help="server TCP port (1024-65535)",
    )
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error(f"port {args.port} is out of range: use 1024-65535")
    return args


def resolve_host(hostname):
    """Resolve the server hostname through DNS, exiting cleanly on failure."""
    try:
        return socket.gethostbyname(hostname)
    except socket.gaierror:
        print(f"[ERROR] Unable to resolve DNS hostname '{hostname}'.")
        print("Please check your Cisco router DNS configuration "
              "('ip dns server' / 'ip host') or verify domain spelling.")
        sys.exit(1)


def connect(server_ip, port):
    """Open a TCP connection to the server, exiting cleanly on failure."""
    try:
        return socket.create_connection((server_ip, port), timeout=10)
    except OSError as error:
        print(f"[ERROR] Could not connect to {server_ip}:{port}: {error}")
        print("Make sure the server is running and the port is correct.")
        sys.exit(1)


def send(sock, state, msg_type, payload):
    """Frame and send one protocol message to the server."""
    try:
        sock.sendall(encode_message(build_message(msg_type, state.player_id, payload)))
        return True
    except OSError:
        print("[ERROR] Connection to server lost.")
        state.running = False
        return False


def ship_cells(row, col, length, orientation):
    """Return the set of cells a ship covers, or None if it leaves the board."""
    start = ROWS.index(row)
    if orientation == "H":
        if col + length - 1 > 10:
            return None
        return {(row, col + i) for i in range(length)}
    if start + length > len(ROWS):
        return None
    return {(ROWS[start + i], col) for i in range(length)}


def parse_coord(text):
    """Turn text like 'E7' into ('E', 7), or None if it is not a valid cell."""
    text = text.strip().upper()
    if len(text) < 2 or text[0] not in ROWS or not text[1:].isdigit():
        return None
    col = int(text[1:])
    if not 1 <= col <= 10:
        return None
    return text[0], col


def render_boards(state):
    """Return both boards side by side as printable text."""
    header = "   " + "".join(f"{c:>3}" for c in range(1, 11))
    lines = [f"{'YOUR FLEET':^33}      {'YOUR SHOTS':^33}", f"{header}      {header}"]
    for row in ROWS:
        left, right = [], []
        for col in range(1, 11):
            cell = (row, col)
            if cell in state.incoming:
                left.append(SHIP_SYMBOLS["miss" if state.incoming[cell] == "MISS" else "hit"])
            elif cell in state.my_cells:
                left.append(SHIP_SYMBOLS["ship"])
            else:
                left.append(SHIP_SYMBOLS["water"])
            if cell in state.outgoing:
                right.append(SHIP_SYMBOLS["miss" if state.outgoing[cell] == "MISS" else "hit"])
            else:
                right.append(SHIP_SYMBOLS["water"])
        lines.append(f" {row} " + "".join(f"{s:>3}" for s in left)
                     + f"       {row} " + "".join(f"{s:>3}" for s in right))
    lines.append("Legend: S ship   X hit   o miss   . water")
    return "\n".join(lines)


def render_status(state):
    """Return the score summary and the turn banner as printable text."""
    lines = []
    if state.scores:
        me = state.scores[state.player_id]
        them = state.scores[state.opponent_id()]
        lines.append(
            f"Score  You: {me['hits']} hits / {me['shots_fired']} shots, "
            f"{me['cells_remaining']} ship cells left  |  {state.opponent_alias}: "
            f"{them['hits']} hits / {them['shots_fired']} shots, "
            f"{them['cells_remaining']} ship cells left"
        )
    if state.my_turn():
        lines.append("=== YOUR TURN ===  Enter a target (e.g. E7), 'draw' to offer a draw, or 'quit'.")
    elif state.phase == "PLAYING":
        lines.append(f"Waiting for {state.opponent_alias} ({state.opponent_id()})...")
    return "\n".join(lines)


def show_game(state):
    """Print the boards and status."""
    print()
    print(render_boards(state))
    print(render_status(state))


def handle_message(state, msg):
    """Update local state from one server message and print what happened."""
    msg_type, payload = msg["msg_type"], msg["payload"]
    if msg_type == "LOBBY_WAIT":
        print(f"[SERVER] {payload['message']}")
    elif msg_type == "GAME_START":
        state.player_id = payload["your_player_id"]
        state.opponent_alias = payload["opponent_alias"]
        state.fleet = payload["fleet"]
        state.phase = "PLACEMENT"
        print(f"\nGame started! You are {state.player_id} vs {state.opponent_alias}.")
        print(f"{payload['first_turn']} fires first. Each player has {payload['shot_limit']} shots.")
        print("Place your fleet: type 'random' or 'manual'.")
    elif msg_type == "PLACEMENT_ACK":
        state.my_cells = set()
        for ship in payload["ships"]:
            length = next(s["length"] for s in state.fleet if s["name"] == ship["name"])
            state.my_cells |= ship_cells(ship["row"], ship["col"], length, ship["orientation"])
        state.phase = "PLACED"
        print(render_boards(state))
        if payload["waiting_for_opponent"]:
            print(f"Fleet placed. Waiting for {state.opponent_alias} to place ships...")
    elif msg_type == "STATE_UPDATE":
        shooter = payload["shooter"]
        if shooter is not None:
            cell = (payload["target"]["row"], payload["target"]["col"])
            label = f"{cell[0]}{cell[1]}"
            if shooter == state.player_id:
                state.outgoing[cell] = payload["result"]
                print(f"\nYou fired at {label}: {payload['result']}")
            else:
                state.incoming[cell] = payload["result"]
                print(f"\n{state.opponent_alias} fired at {label}: {payload['result']}")
            if payload["ship_sunk"]:
                owner = "their" if shooter == state.player_id else "your"
                print(f"*** {owner.capitalize()} {payload['ship_sunk']} was sunk! ***")
        state.scores = payload["scores"]
        state.next_turn = payload["next_turn"]
        state.phase = "PLAYING"
        show_game(state)
    elif msg_type == "DRAW_OFFER":
        state.phase = "DRAW_RESPOND"
        print(f"\n{state.opponent_alias} offers a draw. Type 'yes' to accept or 'no' to decline.")
    elif msg_type == "DRAW_RESPONSE":
        state.phase = "PLAYING"
        print(f"\n{state.opponent_alias} declined the draw.")
        show_game(state)
    elif msg_type == "GAME_OVER":
        state.phase = "OVER"
        show_game_over(state, payload)
    elif msg_type == "ERROR":
        print(f"\n[ERROR] {payload['message']}")
        if payload["code"] == "INVALID_PLACEMENT":
            state.phase = "PLACEMENT"
            print("Place your fleet: type 'random' or 'manual'.")
        elif payload["code"] in ("GAME_FULL", "SERVER_SHUTDOWN"):
            state.phase = "OVER"


def show_game_over(state, payload):
    """Print the final result and leaderboard."""
    reasons = {
        "ALL_SHIPS_SUNK": "all ships sunk",
        "SHOT_LIMIT": "shot limit reached",
        "DRAW": "draw agreed",
        "FORFEIT": "opponent left the game",
    }
    winner = payload["winner"]
    if winner is None:
        outcome = "It's a tie!"
    elif winner == state.player_id:
        outcome = "You win!"
    else:
        outcome = f"{state.opponent_alias} wins."
    hits = payload["final_hits"]
    print(f"\n=== GAME OVER ({reasons.get(payload['reason'], payload['reason'])}) === {outcome}")
    print(f"Final hits  You: {hits.get(state.player_id, 0)}  |  "
          f"{state.opponent_alias}: {hits.get(state.opponent_id(), 0)}")
    print("Leaderboard:")
    for alias, record in payload["leaderboard"].items():
        print(f"  {alias:<16} W {record['wins']}  L {record['losses']}  D {record['draws']}")


def receive_loop(sock, state):
    """Background thread: read server messages and update the game state."""
    buffer = bytearray()
    while state.running:
        try:
            data = sock.recv(4096)
        except socket.timeout:
            continue
        except OSError:
            data = b""
        if not data:
            with state.lock:
                if state.running and state.phase != "OVER":
                    print("\n[ERROR] Connection to server lost.")
                state.running = False
                print("Press Enter to exit.")
            return
        buffer += data
        for line in extract_lines(buffer):
            msg = parse_message(line)
            if msg is None:
                continue
            with state.lock:
                handle_message(state, msg)
                print("> ", end="", flush=True)


def ask_alias():
    """Prompt for a display name of 1-16 characters."""
    while True:
        alias = input("Enter your name (1-16 characters): ").strip()
        if 1 <= len(alias) <= 16:
            return alias
        print("Name must be 1-16 characters.")


def manual_placement(state):
    """Prompt for each ship's position and return the ships list, or None if cancelled."""
    print("Enter a start cell and direction for each ship, e.g. 'A1 H' "
          "(H = rightward, V = downward). Type 'cancel' to go back.")
    ships, occupied = [], set()
    for ship in state.fleet:
        while True:
            text = input(f"{ship['name']} ({ship['length']}): ").strip().upper()
            if text == "CANCEL":
                return None
            parts = text.split()
            coord = parse_coord(parts[0]) if len(parts) == 2 else None
            if coord is None or parts[1] not in ("H", "V"):
                print("Format is a cell and a direction, e.g. 'C3 V'.")
                continue
            cells = ship_cells(coord[0], coord[1], ship["length"], parts[1])
            if cells is None:
                print("That ship would go off the board.")
                continue
            if cells & occupied:
                print("That ship overlaps another ship.")
                continue
            occupied |= cells
            ships.append({"name": ship["name"], "row": coord[0], "col": coord[1],
                          "orientation": parts[1]})
            break
    return ships


def handle_command(sock, state, text):
    """Act on one line of user input based on the current game phase."""
    command = text.strip().lower()
    if command == "quit":
        send(sock, state, "DISCONNECT", {"reason": "QUIT"})
        state.running = False
        return
    with state.lock:
        phase = state.phase
        my_turn = state.my_turn()
    if phase == "PLACEMENT":
        if command == "random":
            with state.lock:
                state.phase = "PLACING"
            send(sock, state, "PLACE_SHIPS", {"mode": "RANDOM"})
        elif command == "manual":
            ships = manual_placement(state)
            if ships is None:
                print("Place your fleet: type 'random' or 'manual'.")
                return
            with state.lock:
                state.phase = "PLACING"
            send(sock, state, "PLACE_SHIPS", {"mode": "MANUAL", "ships": ships})
        else:
            print("Type 'random' or 'manual' to place your fleet.")
    elif phase == "DRAW_RESPOND":
        if command in ("yes", "no"):
            with state.lock:
                state.phase = "PLAYING"
            send(sock, state, "DRAW_RESPONSE", {"accepted": command == "yes"})
        else:
            print("Type 'yes' to accept the draw or 'no' to decline.")
    elif phase == "PLAYING" and my_turn:
        if command == "draw":
            with state.lock:
                state.phase = "DRAW_OFFERED"
            send(sock, state, "DRAW_OFFER", {})
            print(f"Draw offered. Waiting for {state.opponent_alias} to respond...")
            return
        coord = parse_coord(command)
        if coord is None:
            print("Enter a target like E7 (rows A-J, columns 1-10).")
        elif coord in state.outgoing:
            print(f"You already fired at {coord[0]}{coord[1]}.")
        else:
            send(sock, state, "SHOT", {"row": coord[0], "col": coord[1]})
    elif phase == "PLAYING":
        print(f"It's {state.opponent_alias}'s turn. Please wait.")
    elif command:
        print("Please wait...")


def main():
    """Entry point for the Battleship client."""
    args = parse_args()
    server_ip = resolve_host(args.hostname)
    print(f"[CLIENT] Resolved {args.hostname} to {server_ip}")
    sock = connect(server_ip, args.port)
    print(f"[CLIENT] Connected to {server_ip}:{args.port}")
    state = ClientState()
    try:
        state.alias = ask_alias()
        sock.settimeout(1.0)
        if not send(sock, state, "CONNECT", {"alias": state.alias}):
            return
        threading.Thread(target=receive_loop, args=(sock, state), daemon=True).start()
        while state.running:
            text = input("> ")
            if not state.running:
                break
            handle_command(sock, state, text)
    except (KeyboardInterrupt, EOFError):
        print("\n[CLIENT] Leaving the game.")
        if state.running:
            send(sock, state, "DISCONNECT", {"reason": "CLIENT_SHUTDOWN"})
    finally:
        state.running = False
        try:
            sock.shutdown(socket.SHUT_WR)
        except OSError:
            pass
        sock.close()


if __name__ == "__main__":
    main()
