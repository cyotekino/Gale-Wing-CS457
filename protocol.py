import time
import json

VALID_TYPES = {
    "CONNECT", "DISCONNECT", "LOBBY_WAIT", "GAME_START",
    "PLACE_SHIPS", "PLACEMENT_ACK", "SHOT", "STATE_UPDATE",
    "GAME_OVER", "ERROR", "DRAW_OFFER", "DRAW_RESPONSE",
}



def build_message(msg_type, player_id, payload):
    timestamp = int(time.time())
    return {
        "msg_type": msg_type,
        "player_id": player_id,
        "payload": payload,
        "timestamp": int(time.time()),
    }

def encode_message(message):
    json_string = json.dumps(message) + "\n"
    json_bytes = json_string.encode("utf-8")
    return json_bytes

def extract_lines(buffer):
    lines = []
    while b"\n" in buffer:
        index = buffer.find(b"\n")
        line = bytes(buffer[:index])
        del buffer[:index + 1]
        lines.append(line)
    return lines

ENVELOPE_KEYS = ("msg_type", "player_id", "payload", "timestamp")

def parse_message(line):
    keys = ["msg_type", "player_id", "payload", "timestamp"]
    try:
        message = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(message, dict):
        return None
    if not all(key in message for key in ENVELOPE_KEYS):
        return None
    if message["msg_type"] not in VALID_TYPES:
        return None
    return message

