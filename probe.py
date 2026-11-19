"""Dev tool: connect, send CONNECT, and print every message from the server."""
import socket
import sys

from protocol import build_message, encode_message, extract_lines, parse_message

alias = sys.argv[1] if len(sys.argv) > 1 else "Tester"
sock = socket.create_connection(("localhost", 8080))
sock.settimeout(1.0)
sock.sendall(encode_message(build_message("CONNECT", "UNASSIGNED", {"alias": alias})))
buffer = bytearray()
try:
    while True:
        try:
            data = sock.recv(4096)
        except socket.timeout:
            continue
        if not data:
            print("[PROBE] Server closed the connection")
            break
        buffer += data
        for line in extract_lines(buffer):
            print("[PROBE]", parse_message(line))
except KeyboardInterrupt:
    pass
finally:
    sock.close()