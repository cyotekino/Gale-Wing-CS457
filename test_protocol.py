from protocol import (
    build_message,
    encode_message,
    extract_lines,
    parse_message,
)


def test_round_trip():
    """A message survives build -> encode -> extract -> parse unchanged."""
    original = build_message("SHOT", "Player_1", {"row": "E", "col": 7})
    buffer = bytearray(encode_message(original))
    lines = extract_lines(buffer)
    assert len(lines) == 1, "expected exactly one line"
    assert parse_message(lines[0]) == original, "round trip changed the message"
    assert buffer == bytearray(), "buffer should be empty afterward"


def test_encode_format():
    """Encoded messages are bytes ending in exactly one newline."""
    data = encode_message(build_message("CONNECT", "UNASSIGNED", {"alias": "Edgar"}))
    assert isinstance(data, bytes), "encode should return bytes"
    assert data.endswith(b"\n"), "encoded message must end with a newline"
    assert data.count(b"\n") == 1, "only the framing newline should appear"


def test_newline_inside_payload():
    """A newline inside a string is escaped, so framing doesn't break."""
    msg = build_message("CONNECT", "UNASSIGNED", {"alias": "Ed\ngar"})
    buffer = bytearray(encode_message(msg))
    lines = extract_lines(buffer)
    assert len(lines) == 1, "escaped newline should not split the message"
    assert parse_message(lines[0])["payload"]["alias"] == "Ed\ngar"


def test_two_messages_in_one_recv():
    """Two messages glued together come out as two separate messages."""
    first = build_message("SHOT", "Player_1", {"row": "A", "col": 1})
    second = build_message("DRAW_OFFER", "Player_1", {})
    buffer = bytearray(encode_message(first) + encode_message(second))
    lines = extract_lines(buffer)
    assert len(lines) == 2, "expected two lines"
    assert parse_message(lines[0]) == first
    assert parse_message(lines[1]) == second


def test_message_split_across_recvs():
    """Half a message waits in the buffer until the rest arrives."""
    data = encode_message(build_message("SHOT", "Player_2", {"row": "J", "col": 10}))
    half = len(data) // 2
    buffer = bytearray()

    buffer += data[:half]
    assert extract_lines(buffer) == [], "incomplete message should not be returned"
    assert len(buffer) == half, "partial bytes should stay in the buffer"

    buffer += data[half:]
    lines = extract_lines(buffer)
    assert len(lines) == 1, "message should be complete now"
    assert parse_message(lines[0])["msg_type"] == "SHOT"


def test_one_and_a_half_messages():
    """A complete message plus a partial one: return one, keep the rest."""
    complete = encode_message(build_message("SHOT", "Player_1", {"row": "B", "col": 4}))
    partial = b'{"msg_type": "STATE_'
    buffer = bytearray(complete + partial)
    lines = extract_lines(buffer)
    assert len(lines) == 1, "only the complete message should come out"
    assert bytes(buffer) == partial, "partial message should stay in the buffer"


def test_invalid_messages_return_none():
    """Every kind of bad input returns None instead of crashing."""
    cases = {
        "not JSON": b"hello there",
        "invalid UTF-8": b"\xff\xfe\xfd",
        "JSON list, not dict": b"[1, 2, 3]",
        "missing keys": b'{"msg_type": "SHOT"}',
        "unknown msg_type": (
            b'{"msg_type": "FAKE", "player_id": "Player_1", '
            b'"payload": {}, "timestamp": 1}'
        ),
        "empty line": b"",
    }
    for name, line in cases.items():
        assert parse_message(line) is None, f"{name} should return None"


def main():
    """Run every test and report results."""
    tests = [
        test_round_trip,
        test_encode_format,
        test_newline_inside_payload,
        test_two_messages_in_one_recv,
        test_message_split_across_recvs,
        test_one_and_a_half_messages,
        test_invalid_messages_return_none,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except AssertionError as error:
            failed += 1
            print(f"FAIL  {test.__name__}: {error}")
        except Exception as error:
            failed += 1
            print(f"ERROR {test.__name__}: {type(error).__name__}: {error}")
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")


if __name__ == "__main__":
    main()
