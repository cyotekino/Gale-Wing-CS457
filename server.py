import argparse
import selectors
import socket
import sys
import random
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
        self.close_after_send = False


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
    """Parse and validate command-line arguments."""
    parser = argparse.ArgumentParser(description="Battleship game server")
    parser.add_argument(
        "-p", "--port", type=int, required=True, help="TCP port to listen on (1024-65535)"
        )
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error(f"port {args.port} is out of range: use 1024-65535")
    return args


def create_listener(port):
    """Create a non-blocking TCP socket listening on 0.0.0.0:port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", port))
    sock.listen()
    sock.setblocking(False)
    return sock


def accept_client(sel, listen_sock):
    """Accept a new client and register it with the selector."""
    client_sock, addr = listen_sock.accept()
    client_sock.setblocking(False)
    conn = ClientConn(client_sock, addr)
    sel.register(client_sock, selectors.EVENT_READ, data=conn)
    print(f"[SERVER] Connection from {addr[0]}:{addr[1]}")


def teardown(sel, conn, session):
    """Unregister and close a client connection (safe to call twice)."""
    if conn.closed:
        return
    sel.unregister(conn.sock)
    conn.sock.close()
    conn.closed = True
    print(f"[SERVER] {conn.addr[0]}:{conn.addr[1]} disconnected")
    pid = conn.player_id
    if session.players.get(pid) is not conn:
        return
    if session.state in ("SHIP_PLACEMENT", "PLAYER_TURN", "DRAW_PENDING"):
        end_game(sel, session, "FORFEIT", opponent(pid))
    else:
        del session.players[pid]


def handle_read(sel, conn, session):
    """Receive data, detect EOF/errors, and process complete messages."""
    try:
        data = conn.sock.recv(4096)
    except BlockingIOError:
        return
    except OSError:
        teardown(sel, conn, session)
        return
    if not data:
        teardown(sel, conn, session)
        return
    conn.inbuf += data
    for line in extract_lines(conn.inbuf):
        if conn.closed:
            break
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


def handle_write(sel, conn, session):
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
        if conn.close_after_send:
            teardown(sel, conn, session)


def send_error(sel, conn, code, text, ref_msg_type):
    """Queue an ERROR message to one client."""
    payload = {"code": code, "message": text, "ref_msg_type": ref_msg_type}
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


def handle_connect(sel, conn, session, payload):
    """Seat a new player, or reject the connection if the game is full."""
    if conn.player_id != "UNASSIGNED":
        send_error(sel, conn, "INVALID_STATE", "Player is already seated", "CONNECT")
        return
    
    alias = payload.get("alias")
    if not isinstance(alias, str) or not 1 <= len(alias) <= 16:
        send_error(sel, conn, "MALFORMED_MESSAGE", "alias must be a 1-16 character string", "CONNECT")
        return
    if session.state != "WAITING_FOR_PLAYERS" or len(session.players) >= 2:
        send_error(sel, conn, "GAME_FULL", "Game can only take a maximum of two players, please wait for the next game", "CONNECT")
        conn.close_after_send = True
        return

    player_id = "Player_1" if "Player_1" not in session.players else "Player_2"
    conn.player_id = player_id
    conn.alias = alias
    session.players[player_id] = conn
    print(f"[SERVER] {alias} seated as {player_id}")

    if len(session.players) == 1:
        payload = {
            "assigned_player_id": player_id, 
            "players_connected": 1, 
            "message": "Waiting for Player 2 to join",
        }
        queue_message(sel, conn, build_message("LOBBY_WAIT", "SERVER", payload))
        return
    session.state = "GAME_START"
    fleet = [{"name": name, "length": length} for name, length in FLEET.items()]
    for pid in PLAYER_IDS:
        opponent_id = "Player_2" if pid == "Player_1" else "Player_1"
        payload = {
            "your_player_id": pid,
            "opponent_alias": session.players[opponent_id].alias,
            "first_turn": "Player_1",
            "board_size": 10,
            "shot_limit": SHOT_LIMIT,
            "fleet": fleet,
        }
        queue_message(sel, session.players[pid], build_message("GAME_START", "SERVER", payload))
    session.state = "SHIP_PLACEMENT"
    print("[SERVER] Both players seated, starting ship placement")


def opponent(pid):
    """Return the other player's ID."""

    return "Player_2" if pid == "Player_1" else "Player_1"


def broadcast(sel, session, msg_type, payload):
    """Queue the same server message to every seated player."""
    msg = build_message(msg_type, "SERVER", payload)
    for conn in session.players.values():
        queue_message(sel, conn, msg)


def score_table(session):
    """Build the per-player hits, shots fired, and cells remaining."""
    return {
        pid: {
            "hits": session.hits[pid],
            "shots_fired": session.shots_fired[pid],
            "cells_remaining": TOTAL_SHIP_CELLS - session.hits[opponent(pid)],
        }
        for pid in PLAYER_IDS
    }


def ship_cells(row, col, length, orientation):
    """Return the set of cells a ship covers, or None if it leaves the board."""
    if not isinstance(row, str) or len(row) != 1 or row not in ROWS:
        return None
    if not isinstance(col, int) or isinstance(col, bool) or not 1 <= col <= 10:
        return None
    if orientation not in ("H", "V"):
        return None
    start = ROWS.index(row)
    if orientation == "H":
        if col + length - 1 > 10:
            return None
        return {(row, col + i) for i in range(length)}
    if start + length > len(ROWS):
        return None
    return {(ROWS[start + i], col) for i in range(length)}


def validate_layout(ships):
    """Check a manual fleet layout and return {ship_name: cells}, or None if invalid."""
    if not isinstance(ships, list) or len(ships) != len(FLEET):
        return None
    fleet = {}
    occupied = set()
    for ship in ships:
        if not isinstance(ship, dict):
            return None
        name = ship.get("name")
        if not isinstance(name, str) or name not in FLEET or name in fleet:
            return None
        cells = ship_cells(ship.get("row"), ship.get("col"), FLEET[name], ship.get("orientation"))
        if cells is None or cells & occupied:
            return None
        fleet[name] = cells
        occupied |= cells
    return fleet


def random_layout():
    """Place all five ships randomly with no overlaps; return (fleet, ships)."""
    fleet = {}
    ships = []
    occupied = set()
    for name, length in FLEET.items():
        while True:
            row = random.choice(ROWS)
            col = random.randint(1, 10)
            orientation = random.choice("HV")
            cells = ship_cells(row, col, length, orientation)
            if cells and not cells & occupied:
                break
        fleet[name] = cells
        occupied |= cells
        ships.append({"name": name, "row": row, "col": col, "orientation": orientation})
    return fleet, ships


def end_game(sel, session, reason, winner):
    """Update the leaderboard, broadcast GAME_OVER, close both players, and reset."""
    session.state = "GAME_OVER"
    for pid, conn in session.players.items():
        record = session.leaderboard.setdefault(conn.alias, {"wins": 0, "losses": 0, "draws": 0})
        if winner is None:
            record["draws"] += 1
        elif pid == winner:
            record["wins"] += 1
        else:
            record["losses"] += 1
    payload = {
        "reason": reason,
        "winner": winner,
        "final_hits": dict(session.hits),
        "leaderboard": session.leaderboard,
    }
    broadcast(sel, session, "GAME_OVER", payload)
    for conn in session.players.values():
        conn.close_after_send = True
    print(f"[SERVER] Game over ({reason}), winner: {winner}")
    session.reset()


def handle_place_ships(sel, conn, session, payload):
    """Accept a manual or random fleet and start the first turn once both are placed."""
    pid = conn.player_id
    if session.state != "SHIP_PLACEMENT" or pid in session.placed:
        send_error(sel, conn, "INVALID_STATE", "Ship placement is not allowed now", "PLACE_SHIPS")
        return
    mode = payload.get("mode")
    if mode == "RANDOM":
        fleet, ships = random_layout()
    elif mode == "MANUAL":
        ships = payload.get("ships")
        fleet = validate_layout(ships)
        if fleet is None:
            send_error(sel, conn, "INVALID_PLACEMENT", "Ships overlap, leave the board, or the fleet is wrong", "PLACE_SHIPS")
            return
        ships = [
            {"name": s["name"], "row": s["row"], "col": s["col"], "orientation": s["orientation"]}
            for s in ships
        ]
    else:
        send_error(sel, conn, "MALFORMED_MESSAGE", "mode must be MANUAL or RANDOM", "PLACE_SHIPS")
        return
    session.fleets[pid] = fleet
    session.placed.add(pid)
    ack = {"ships": ships, "waiting_for_opponent": len(session.placed) < 2}
    queue_message(sel, conn, build_message("PLACEMENT_ACK", "SERVER", ack))
    print(f"[SERVER] {pid} placed ships ({mode})")
    if len(session.placed) == 2:
        session.state = "PLAYER_TURN"
        session.active_turn = "Player_1"
        broadcast(sel, session, "STATE_UPDATE", {
            "shooter": None,
            "target": None,
            "result": None,
            "ship_sunk": None,
            "scores": score_table(session),
            "next_turn": session.active_turn,
        })
        print("[SERVER] Both fleets placed, Player_1 fires first")


def handle_shot(sel, conn, session, payload):
    """Validate a shot, mark the result, check for game end, and broadcast the update."""
    pid = conn.player_id
    if session.state != "PLAYER_TURN":
        send_error(sel, conn, "INVALID_STATE", "Shots are not allowed now", "SHOT")
        return
    if pid != session.active_turn:
        send_error(sel, conn, "NOT_YOUR_TURN", f"It is {session.active_turn}'s turn", "SHOT")
        return
    row, col = payload.get("row"), payload.get("col")
    if ship_cells(row, col, 1, "H") is None:
        send_error(sel, conn, "INVALID_SHOT", "row must be A-J and col must be 1-10", "SHOT")
        return
    target = opponent(pid)
    cell = (row, col)
    if cell in session.shots_received[target]:
        send_error(sel, conn, "ALREADY_FIRED", f"{row}{col} was already targeted", "SHOT")
        return
    session.state = "EVALUATE_MOVE"
    session.shots_received[target].add(cell)
    session.shots_fired[pid] += 1
    result, sunk = "MISS", None
    for name, cells in session.fleets[target].items():
        if cell in cells:
            session.hits[pid] += 1
            result = "HIT"
            if cells <= session.shots_received[target]:
                result, sunk = "SUNK", name
            break
    print(f"[SERVER] {pid} fired at {row}{col}: {result}")
    session.state = "CHECK_WIN_DRAW"
    if session.hits[pid] == TOTAL_SHIP_CELLS:
        end_game(sel, session, "ALL_SHIPS_SUNK", pid)
        return
    if all(session.shots_fired[p] >= SHOT_LIMIT for p in PLAYER_IDS):
        p1, p2 = session.hits["Player_1"], session.hits["Player_2"]
        winner = "Player_1" if p1 > p2 else "Player_2" if p2 > p1 else None
        end_game(sel, session, "SHOT_LIMIT", winner)
        return
    session.state = "PLAYER_TURN"
    session.active_turn = target
    broadcast(sel, session, "STATE_UPDATE", {
        "shooter": pid,
        "target": {"row": row, "col": col},
        "result": result,
        "ship_sunk": sunk,
        "scores": score_table(session),
        "next_turn": session.active_turn,
    })


def handle_draw_offer(sel, conn, session, payload):
    """Relay the active player's draw offer to the opponent and pause shooting."""
    pid = conn.player_id
    if session.state != "PLAYER_TURN":
        send_error(sel, conn, "INVALID_STATE", "A draw cannot be offered now", "DRAW_OFFER")
        return
    if pid != session.active_turn:
        send_error(sel, conn, "NOT_YOUR_TURN", "You can only offer a draw on your turn", "DRAW_OFFER")
        return
    session.state = "DRAW_PENDING"
    session.draw_offered_by = pid
    other = session.players[opponent(pid)]
    queue_message(sel, other, build_message("DRAW_OFFER", "SERVER", {"offered_by": pid}))
    print(f"[SERVER] {pid} offered a draw")


def handle_draw_response(sel, conn, session, payload):
    """End the game as a draw if accepted, or resume play and notify the offerer."""
    pid = conn.player_id
    if session.state != "DRAW_PENDING" or pid == session.draw_offered_by:
        send_error(sel, conn, "INVALID_STATE", "There is no draw offer to answer", "DRAW_RESPONSE")
        return
    accepted = payload.get("accepted")
    if not isinstance(accepted, bool):
        send_error(sel, conn, "MALFORMED_MESSAGE", "accepted must be true or false", "DRAW_RESPONSE")
        return
    if accepted:
        end_game(sel, session, "DRAW", None)
        return
    offerer = session.players[session.draw_offered_by]
    session.draw_offered_by = None
    session.state = "PLAYER_TURN"
    reply = {"accepted": False, "responded_by": pid}
    queue_message(sel, offerer, build_message("DRAW_RESPONSE", "SERVER", reply))
    print(f"[SERVER] {pid} denied the draw")


def handle_disconnect(sel, conn, session, payload):
    """Close the connection on a DISCONNECT message (forfeits an active game)."""
    teardown(sel, conn, session)


HANDLERS = {
    "CONNECT": handle_connect,
    "PLACE_SHIPS": handle_place_ships,
    "SHOT": handle_shot,
    "DRAW_OFFER": handle_draw_offer,
    "DRAW_RESPONSE": handle_draw_response,
    "DISCONNECT": handle_disconnect,
}


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
                        handle_write(sel, conn, session)
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down")
    finally:
        sel.close()
        listen_sock.close()


if __name__ == "__main__":
    main()