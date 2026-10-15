# CS 457 Project Statement of Work (SOW) & Protocol Specification Template

**Student Name:** Gale Wing  
**Date:** 2026-10-14
**Course:** CS 457 - Computer Networks  
**Target Server Domain:** `server.wing.edu`  

---

## 1. Game Selection & Scope (Sprint 0)

> Planning is going to be an iterative process through the sprints so you don't have to have all the details now. Focus on big overview concepts. You will be updating the SOW as we plan.
> You have a lot of freedom to choose a game. There are a couple caveats.  

> - It must run in the console. The lab nodes won't be able to handle extensive graphics.
> - It has to be self-contained. You can use a internet-connector to download you code, but because the architecture must run 5 nodes you won't be able to run 
> - You are encouraged to use python, but I'm not going to make it a strict requirement. The instructor and TA's ability to help with C or Rust, etc will be diminished in other languages.

### 1.1 Game Overview
- **Chosen Game:** Battleship
- **Player Capacity:** 2 Players (Simulated via 2 CML Client nodes)
- **Game Summary:** Each player has a 10x10 board that only they can see. Each player has 5 ships that they place on their board either vertically or horizontally, and they cannot overlap. The rows of the board are A-J and columns 1-10, with a Carrier ship taking 5 slots, a Battleship takes 4, a Cruiser takes 3, a submarine takes 3, and a Destroyer ship takes 2 slots. Players alternate taking turns firing a single shot at a coordinate attempting to hit a slot on a ship, either getting a hit or miss in response. Once all slots on a ship have been hit, the ship sinks, if all 17 slots are eventually hit, that player loses. 

### 1.2 Core Game Rules & Win/Draw Conditions
- **Turn Mechanics:** The first client who connects will be player one, while the second becomes player 2. Each will be assigned them when the game starts, each player will receive their layout and their five ships, with the option to place their ships or have them randomly assigned. Player 1 will fire first, with one shot per turn, after the shot is launched, it will switch to the next player. Additional actions taken by a player outside of their turn will be rejected. 
- **Victory Condition:** [Define how a player wins the game] Once all 17 ship slots are hit, the server will send a game over alert with the winner displayed to both clients, if a player disconnects then the other player will with by forfeit. 
- **Draw/Tie Condition:** A 50 shot limit will be implemented, if all shots are exhausted and both players still have standing ships, the person with the most hits landed on ships wins, otherwise if it is even a tie will be called. For a draw, players can submit a draw request that the other player will receive, with an accept or deny option. 

---

## 2. Application-Layer Messaging Protocol Blueprint (Sprint 1 Deliverable)

### 2.1 Message Transport & Serialization Format
- **Transport Protocol:** TCP
- **Serialization Format:** Structured JSON
- **Framing Rule Requirement:** Every JSON object is UTF-8 encoded and terminated by a newline character \n (0x0A). The receiver accumulates incoming bytes into a stream buffer until a \n is encountered, extracts the complete line, and deserializes the JSON object. Any bytes after the last \n remain in buffer until the rest of the message is received. 
- *Wire Stream Example:* `{"msg_type":"CONNECT","player_id":"UNASSIGNED","payload":{"alias":"Edgar"},"timestamp":1920000000}\n{"msg_type":"SHOT","player_id":"Player_1","payload":{"row":"E","col":7},"timestamp":1920000005}\n`
- *JSON Schema Definition (SHOT):*
```json
  {
    "msg_type": "SHOT",
    "player_id": "Player_1",
    "payload": {
      "row": "E",
      "col": 7
    },
    "timestamp": 1920000005
  }
```
- `msg_type`: a string naming the message type.
- `player_id`: an identifier or the player, if they are assigned player 1 or 2, or unassigned if they have not started a game yet. 
- `row`: string, Letter A-J.
- `col`: Integer, 1-10.
- `timestamp`: an integer Unix time.
- `payload`: object whose field depends on msg_type.

### 2.2 Message Schema Definitions

#### Message Types:
1. `CONNECT` (Client -> Server): Request to join the game room.
2. `DISCONNECT` (Client -> Server): Notice of leaving the game room.
3. `LOBBY_WAIT` (Server -> Client): Notification that server is waiting for Player 2.
4. `GAME_START` (Server -> Clients): Game initiated, assigns roles Player 1 or Player 2.
5. `SHOT` (Client -> Server): Player action, provide target coordinates to shoot at.
6. `STATE_UPDATE` (Server -> Clients): Alerts if there is a HIT, MISS, or SUNK SHIP after the shot, and remaining target cells count left, then whose turn is next.
7. `GAME_OVER` (Server -> Clients): Victory, declaration of winner, announcement of shot limit tie, draw, forfeit, with final hit counts.
8. `ERROR` (Server -> Client): Invalid shot or malformed packet error, an unaccepted placement, actions taken outside of turn.
9. `DRAW_OFFER` (Client -> Server, relays to opponent): Player asks for a draw.
10. `DRAW_RESPONSE` (Client -> Server, relayed to offering player): Accept or deny the draw.
11. `PLACE_SHIPS` (Client -> Server): Player places ships, or selects a random placement.
12. `PLACEMENT_ACK` (Server -> Client): Confirms layout for players, displays ship placements for selected ships and random placement.

---

### 2.3 Game State Machine (FSM) Design (Sprint 1 Deliverable)
- **State Transitions:** Detail state flow: `INIT` -> `WAITING_FOR_PLAYERS` -> `GAME_START` -> `SHIP_PLACEMENT` -> `PLAYER_TURN` -> `EVALUATE_MOVE` -> `CHECK_WIN_DRAW` -> `DRAW_PENDING` -> `GAME_OVER` -> `CLEANUP`.
<img width="2767" height="4130" alt="Game Session Lifecycle Flow-2026-10-15-051522" src="https://github.com/user-attachments/assets/28783916-860a-405a-9857-6133bd63ebb0" />

---

## 3. Game Behavior & Server Concurrency Architecture (Sprint 2 Deliverable)

### 3.1 Server Concurrency Strategy
- **Architecture Choice:** [Multi-Threading (`threading.Thread`) OR Non-blocking I/O multiplexing (`select.select` / `selectors`)]
- **Synchronization Logic:** Explain how shared game state and client list are thread-safe (e.g. `threading.Lock`) to prevent race conditions during turn processing.

### 3.2 State & Score Synchronization Across Clients
- **Turn Enforcement:** Detail how the server validates active player ID before processing moves and broadcasts updated turn notifications to all clients.
- **Score & Board Synchronization:** Describe how state broadcasts keep client screens synchronized in real time.
- **Mermaid Sequence Diagram:** Embed a sequence diagram authored strictly in **Mermaid (`sequenceDiagram`) syntax** illustrating client move submission, server authority validation, board mutation, and synchronized state broadcast to all clients.

---

## 4. Coding & AI Implementation Plan (Sprint 3)

- **Permitted AI Tools:** [e.g., GitHub Copilot, ChatGPT, Claude]
- **AI Prompting & Constraint Strategy:** Explain how you will constrain AI models to generate code (in Python or your chosen language) that adheres strictly to the protocol blueprint and FSM designed in Sprints 1 & 2.
- **Implementation Risk Management:** Detail your plan to leverage past programming experience and manage time to ensure code completion on schedule.

---

## 5. CML Multi-Subnet Topology & Wireshark Deployment Plan (Sprint 4 & 5 Deliverable)

> For now you can use the topology below. We may update this when we get to defining subnets.

### 5.1 Subnet & Router Design
- **Subnet A (Client 1):** `192.168.10.0/24` (Interface `Gi0/1` on Router R1)
- **Subnet B (Client 2):** `192.168.11.0/24` (Interface `Gi0/2` on Router R1)
- **Subnet C (Game Server):** `192.168.20.0/24` (Interface `Gi0/1` on Router R2)
- **Router Backbone:** `10.0.0.0/30` (Interface `Gi0/0` on R1 <-> `Gi0/0` on R2)

### 5.2 DHCP Pools & DNS Configuration Plan
- **Router R1 DHCP Pool 1 (`CLIENT1_POOL`):** Leases `192.168.10.10` - `192.168.10.50`, gateway `192.168.10.1`, DNS `10.0.0.2`.
- **Router R1 DHCP Pool 2 (`CLIENT2_POOL`):** Leases `192.168.11.10` - `192.168.11.50`, gateway `192.168.11.1`, DNS `10.0.0.2`.
- **Router R2 Authoritative DNS:** Configured with `ip dns server` and static host mapping `server.[yourlastname].edu` -> `192.168.20.100`.

### 5.3 Deployment Strategy & Wireshark Trace Capture
- **CML Deployment Strategy:** Deploy `server.py` onto Subnet C node (`192.168.20.100`) behind Router R2, and `client.py` onto Subnet A and Subnet B nodes behind Router R1.
- **Cisco Infrastructure Configuration:** Router R1 DHCP pools (`CLIENT1_POOL`, `CLIENT2_POOL`) and Router R2 authoritative DNS (`ip host server.[lastname].edu 192.168.20.100`).
- **Wireshark Trace Capture Plan:** Capture DHCP DORA exchange (`dhcp_negotiation.pcap`) and DNS query/response resolution (`dns_lookup.pcap`).
