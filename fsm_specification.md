  stateDiagram-v2
  direction TB
  [*] --> INIT
  INIT --> WAITING_FOR_PLAYERS : server listening
  WAITING_FOR_PLAYERS --> WAITING_FOR_PLAYERS : CONNECT
  WAITING_FOR_PLAYERS --> WAITING_FOR_PLAYERS : LOBBY_WAIT
  WAITING_FOR_PLAYERS --> GAME_START : Two players joined
  GAME_START --> SHIP_PLACEMENT : Two valid players for a game
  SHIP_PLACEMENT --> PLAYER_TURN : Valid placement
  SHIP_PLACEMENT --> SHIP_PLACEMENT : Invalid placement, ERROR
  SHIP_PLACEMENT --> GAME_OVER : Disconnect
  PLAYER_TURN --> EVALUATE_MOVE : SHOT FIRED
  PLAYER_TURN --> GAME_OVER : Disconnect
  PLAYER_TURN --> PLAYER_TURN : Out of turn shot, ERROR
  EVALUATE_MOVE --> CHECK_WIN_DRAW : Accepted attack, evlauate if attack sinks, ends, game, etc
  CHECK_WIN_DRAW --> GAME_OVER : All ships sunk or all shots fired
  CHECK_WIN_DRAW -->  PLAYER_TURN : No winner, switch turn
  EVALUATE_MOVE --> PLAYER_TURN : Invalid attack, ERROR
  DRAW_PENDING --> GAME_OVER : Draw accepted
  DRAW_PENDING --> PLAYER_TURN : Draw Denied
  DRAW_PENDING --> GAME_OVER : Disconnect
  GAME_OVER --> CLEANUP
  PLAYER_TURN --> DRAW_PENDING
  CLEANUP --> WAITING_FOR_PLAYERS : New game
  CLEANUP --> [*] 
