import time

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

def encode:



def linePuller:
