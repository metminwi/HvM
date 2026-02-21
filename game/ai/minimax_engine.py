
import math
import random
import time
from typing import List, Optional, Tuple, Dict

# ==================== Constants & Configuration ====================

BOARD_SIZE = 15
WIN_LEN = 5

# Directions: vertical, horizontal, two diagonals
DIRS = [(1, 0), (0, 1), (1, 1), (1, -1)]

# Pattern type constants for clearer code
WIN = 7
OPEN_FOUR = 6
HALF_OPEN_FOUR = 5
OPEN_THREE = 4
HALF_OPEN_THREE = 3
OPEN_TWO = 2
HALF_OPEN_TWO = 1

# Pattern scores (hierarchical to prioritize threats)
PATTERN_SCORES = {
    WIN: 1_000_000,
    OPEN_FOUR: 100_000,
    HALF_OPEN_FOUR: 10_000,
    OPEN_THREE: 5_000,
    HALF_OPEN_THREE: 500,
    OPEN_TWO: 50,
    HALF_OPEN_TWO: 5,
}

# Difficulty parameters: depth, move generation radius, max candidates, eval noise
DIFFICULTY_PARAMS = {
    "easy": {"max_depth": 2, "radius": 2, "max_candidates": 15, "noise": 40},
    "standard": {"max_depth": 4, "radius": 2, "max_candidates": 25, "noise": 0},
    "challenge": {"max_depth": 6, "radius": 1, "max_candidates": 30, "noise": 0},
}

# ==================== Module-Level State ====================

# Zobrist keys for hashing board positions (lazy initialization)
_zobrist_keys: Optional[List[List[List[int]]]] = None

# Transposition table: hash -> (depth, score, flag, best_move)
_transposition_table: Dict[int, Tuple[int, int, int, Optional[Tuple[int, int]]]] = {}

# History heuristic table: move frequency for ordering
_history_table: Optional[List[List[int]]] = None

# Killer moves: depth -> [move1, move2]
_killer_moves: Dict[int, List[Optional[Tuple[int, int]]]] = {}


def _init_zobrist():
    """One-time initialization of Zobrist keys and history table."""
    global _zobrist_keys, _history_table
    if _zobrist_keys is None:
        _zobrist_keys = [
            [[random.getrandbits(64) for _ in range(2)] for _ in range(BOARD_SIZE)]
            for _ in range(BOARD_SIZE)
        ]
        _history_table = [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)]


# ==================== Board Utilities ====================


def _in_bounds(r: int, c: int) -> bool:
    return 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE


def _check_winner(board: List[List[str]]) -> Optional[str]:
    """Fast winner check - returns 'X', 'O', or None."""
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            player = board[r][c]
            if not player:
                continue
            for dr, dc in DIRS:
                nr, nc = r + dr * (WIN_LEN - 1), c + dc * (WIN_LEN - 1)
                if not _in_bounds(nr, nc):
                    continue
                for i in range(WIN_LEN):
                    if board[r + dr * i][c + dc * i] != player:
                        break
                else:
                    return player
    return None


def _zobrist_hash(board: List[List[str]]) -> int:
    """Compute hash for current board position."""
    h = 0
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            cell = board[r][c]
            if cell == "X":
                h ^= _zobrist_keys[r][c][0]
            elif cell == "O":
                h ^= _zobrist_keys[r][c][1]
    return h


def _get_game_stage(board: List[List[str]]) -> int:
    """Estimate game stage by counting stones (affects search radius)."""
    stone_count = sum(1 for row in board for cell in row if cell)
    return min(stone_count // 10, 2)  # 0: early, 1: mid, 2: late


def _find_immediate_win(board: List[List[str]], player: str) -> Optional[Tuple[int, int]]:
    """If player has a winning move, return it; else None."""
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board[r][c]:
                continue
            board[r][c] = player
            if _check_winner(board) == player:
                board[r][c] = ""
                return (r, c)
            board[r][c] = ""
    return None


# ==================== Pattern Detection ====================


def _scan_direction(
    board: List[List[str]], player: str, r: int, c: int, dr: int, dc: int
) -> Tuple[int, int]:
    """
    Scan a line from (r,c) in direction (dr,dc) to identify patterns.
    Returns (pattern_type, length) for the sequence starting at (r,c).
    """
    if not _in_bounds(r, c) or board[r][c] != player:
        return (0, 0)

    # Find start of sequence (avoid double-counting)
    pr, pc = r - dr, c - dc
    if _in_bounds(pr, pc) and board[pr][pc] == player:
        return (0, 0)

    # Count length
    length = 1
    nr, nc = r + dr, c + dc
    while _in_bounds(nr, nc) and board[nr][nc] == player:
        length += 1
        nr += dr
        nc += dc

    # Check openness of ends
    left_open = _in_bounds(pr, pc) and board[pr][pc] == ""
    right_open = _in_bounds(nr, nc) and board[nr][nc] == ""

    # Classify pattern
    if length >= 5:
        return (WIN, length)
    elif length == 4:
        if left_open and right_open:
            return (OPEN_FOUR, length)
        elif left_open or right_open:
            return (HALF_OPEN_FOUR, length)
    elif length == 3:
        if left_open and right_open:
            return (OPEN_THREE, length)
        elif left_open or right_open:
            return (HALF_OPEN_THREE, length)
    elif length == 2:
        if left_open and right_open:
            return (OPEN_TWO, length)
        elif left_open or right_open:
            return (HALF_OPEN_TWO, length)

    return (0, length)


def _evaluate_position(board: List[List[str]], player: str, opponent: str) -> int:
    """
    Advanced evaluation: sum pattern scores for both players.
    Prioritizes threats and double-attacks.
    """
    player_score = 0
    opponent_score = 0

    # Check for immediate win/loss in evaluation
    winner = _check_winner(board)
    if winner == player:
        return PATTERN_SCORES[WIN]
    if winner == opponent:
        return -PATTERN_SCORES[WIN]

    # Scan board for patterns
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board[r][c] == player:
                for dr, dc in DIRS:
                    pat, length = _scan_direction(board, player, r, c, dr, dc)
                    if pat:
                        player_score += PATTERN_SCORES[pat]
            elif board[r][c] == opponent:
                for dr, dc in DIRS:
                    pat, length = _scan_direction(board, opponent, r, c, dr, dc)
                    if pat:
                        opponent_score += PATTERN_SCORES[pat]

    # Bonus for central control (early game)
    stage = _get_game_stage(board)
    if stage == 0:
        center = BOARD_SIZE // 2
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if board[r][c] == player:
                    dist = abs(r - center) + abs(c - center)
                    player_score += max(0, 10 - dist)

    return player_score - opponent_score


# ==================== Move Generation & Ordering ====================


def _score_single_move(
    board: List[List[str]], r: int, c: int, player: str, opponent: str
) -> int:
    """Static heuristic score for a single move (for move ordering)."""
    board[r][c] = player
    score = 0

    # 1. Immediate win is highest priority
    if _check_winner(board) == player:
        board[r][c] = ""
        return 10**8

    # 2. Check patterns created by this move
    for dr, dc in DIRS:
        # Forward direction
        pat_f, _ = _scan_direction(board, player, r, c, dr, dc)
        score += PATTERN_SCORES.get(pat_f, 0) // 10

        # Backward direction
        pat_b, _ = _scan_direction(board, player, r, c, -dr, -dc)
        score += PATTERN_SCORES.get(pat_b, 0) // 10

    # 3. History heuristic bonus
    score += _history_table[r][c]

    board[r][c] = ""
    return score


def _generate_moves(
    board: List[List[str]],
    player: str,
    opponent: str,
    radius: int,
    max_candidates: int,
) -> List[Tuple[int, int, int]]:
    """
    Generate candidate moves within radius of existing stones.
    Returns list of (row, col, score) sorted by score descending.
    """
    stones = [(r, c) for r in range(BOARD_SIZE) for c in range(BOARD_SIZE) if board[r][c]]
    candidates = set()

    if not stones:
        center = BOARD_SIZE // 2
        return [(center, center, 0)]

    # Gather empty positions in influence area
    for sr, sc in stones:
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                r, c = sr + dr, sc + dc
                if _in_bounds(r, c) and board[r][c] == "":
                    candidates.add((r, c))

    # Score and sort moves
    scored = []
    for r, c in candidates:
        # Score from AI perspective
        ai_score = _score_single_move(board, r, c, player, opponent)
        # Score from opponent perspective (for blocking priority)
        opp_score = _score_single_move(board, r, c, opponent, player)
        # Combined score: prioritize threats and blocks
        total_score = max(ai_score, opp_score * 0.9)
        scored.append((r, c, total_score))

    # Sort by score descending, then by proximity to center for ties
    center = BOARD_SIZE // 2
    scored.sort(
        key=lambda x: (x[2], -(abs(x[0] - center) + abs(x[1] - center))), reverse=True
    )

    return scored[:max_candidates]


# ==================== Core Search Algorithm ====================


def _minimax(
    board: List[List[str]],
    depth: int,
    alpha: int,
    beta: int,
    maximizing: bool,
    player: str,
    opponent: str,
    max_candidates: int,
    radius: int,
    node_hash: int,
    ply: int,
) -> Tuple[int, Optional[Tuple[int, int]]]:
    """
    Alpha-beta search with transposition table, killer moves, and history heuristic.
    Returns (score, best_move).
    """
    # Transposition table probe
    tt_entry = _transposition_table.get(node_hash)
    if tt_entry:
        tt_depth, tt_score, tt_flag, tt_move = tt_entry
        if tt_depth >= depth:
            if tt_flag == 0:  # EXACT
                return tt_score, tt_move
            elif tt_flag == 1 and tt_score >= beta:  # LOWERBOUND
                return tt_score, tt_move
            elif tt_flag == 2 and tt_score <= alpha:  # UPPERBOUND
                return tt_score, tt_move

    # Terminal check
    winner = _check_winner(board)
    if winner == player:
        return PATTERN_SCORES[WIN] - ply, None
    if winner == opponent:
        return -PATTERN_SCORES[WIN] + ply, None

    # Depth cutoff
    if depth == 0:
        return _evaluate_position(board, player, opponent), None

    # Generate and order moves
    current_player = player if maximizing else opponent
    current_opponent = opponent if maximizing else player
    moves = _generate_moves(board, current_player, current_opponent, radius, max_candidates)

    best_move = None
    flag = 2  # UPPERBOUND initially

    if maximizing:
        value = -math.inf
        for r, c, _ in moves:
            board[r][c] = player
            child_hash = node_hash ^ _zobrist_keys[r][c][0]  # XOR for player O (AI)
            score, _ = _minimax(
                board,
                depth - 1,
                alpha,
                beta,
                False,
                player,
                opponent,
                max_candidates,
                radius,
                child_hash,
                ply + 1,
            )
            board[r][c] = ""

            if score > value:
                value = score
                best_move = (r, c)
                # Update killers (keep two best at each depth)
                if depth not in _killer_moves:
                    _killer_moves[depth] = [None, None]
                if (r, c) not in _killer_moves[depth]:
                    _killer_moves[depth][1] = _killer_moves[depth][0]
                    _killer_moves[depth][0] = (r, c)

            alpha = max(alpha, value)
            if alpha >= beta:
                # Beta cutoff: update history
                _history_table[r][c] += depth * depth
                break

        flag = 0 if alpha > beta else 1  # EXACT or LOWERBOUND
        result = (value, best_move)
    else:
        value = math.inf
        for r, c, _ in moves:
            board[r][c] = opponent
            child_hash = node_hash ^ _zobrist_keys[r][c][1]  # XOR for player X (human)
            score, _ = _minimax(
                board,
                depth - 1,
                alpha,
                beta,
                True,
                player,
                opponent,
                max_candidates,
                radius,
                child_hash,
                ply + 1,
            )
            board[r][c] = ""

            if score < value:
                value = score
                best_move = (r, c)

            beta = min(beta, value)
            if alpha >= beta:
                _history_table[r][c] += depth * depth
                break

        flag = 0 if beta < alpha else 2  # EXACT or UPPERBOUND
        result = (value, best_move)

    # Store in transposition table
    if depth >= 2:  # Only store meaningful depths
        _transposition_table[node_hash] = (depth, value, flag, best_move)

    return result


def _aspiration_search(
    board: List[List[str]],
    depth: int,
    prev_score: int,
    player: str,
    opponent: str,
    params: Dict,
    node_hash: int,
) -> Tuple[int, Optional[Tuple[int, int]]]:
    """Search with aspiration window around prev_score."""
    margin = 500 if depth >= 4 else 1000
    alpha = prev_score - margin
    beta = prev_score + margin

    score, move = _minimax(
        board,
        depth,
        alpha,
        beta,
        True,
        player,
        opponent,
        params["max_candidates"],
        params["radius"],
        node_hash,
        0,
    )

    # If outside window, re-search with full window
    if score <= alpha:
        score, move = _minimax(
            board,
            depth,
            -math.inf,
            beta,
            True,
            player,
            opponent,
            params["max_candidates"],
            params["radius"],
            node_hash,
            0,
        )
    elif score >= beta:
        score, move = _minimax(
            board,
            depth,
            alpha,
            math.inf,
            True,
            player,
            opponent,
            params["max_candidates"],
            params["radius"],
            node_hash,
            0,
        )

    return score, move


# ==================== Public API ====================
Cell = str
Board = List[List[Cell]]

#def choose_best_move(board: List[List[str]], difficulty: str = "standard") -> Optional[Dict]:
def choose_best_move(board: Board, difficulty: str = "standard") -> Optional[dict]:  
    """
    Production-grade Gomoku AI with iterative deepening, transposition tables,
    killer moves, history heuristic, and advanced pattern evaluation.
    Maintains stable API for Django backend.
    """
    # Initialize module state if needed
    _init_zobrist()
    global _transposition_table, _killer_moves

    # Validate inputs
    if difficulty not in DIFFICULTY_PARAMS:
        difficulty = "standard"

    params = DIFFICULTY_PARAMS[difficulty]
    player, opponent = "O", "X"

    # Quick exit: immediate win
    win_move = _find_immediate_win(board, player)
    if win_move:
        return {"row": win_move[0], "col": win_move[1], "score": PATTERN_SCORES[WIN], "depth": 0}

    # Quick exit: block opponent's immediate win
    block_move = _find_immediate_win(board, opponent)
    if block_move:
        return {
            "row": block_move[0],
            "col": block_move[1],
            "score": PATTERN_SCORES[WIN] - 1,
            "depth": 0,
        }

    # Reset transposition table for fresh searches (prevent memory bloat)
    # Keep it small: clear if too many entries
    if len(_transposition_table) > 500_000:
        _transposition_table.clear()
        _killer_moves.clear()

    # Iterative deepening with aspiration windows
    node_hash = _zobrist_hash(board)
    best_move = None
    best_score = -math.inf
    start_time = time.time()

    for depth in range(1, params["max_depth"] + 1):
        try:
            # Use aspiration window except at depth 1
            if depth == 1:
                score, move = _minimax(
                    board,
                    depth,
                    -math.inf,
                    math.inf,
                    True,
                    player,
                    opponent,
                    params["max_candidates"],
                    params["radius"],
                    node_hash,
                    0,
                )
            else:
                score, move = _aspiration_search(
                    board, depth, best_score, player, opponent, params, node_hash
                )

            # Only update if we got a valid move
            if move:
                best_move = move
                best_score = score

            # Time check (soft limit)
            if difficulty == "standard" and time.time() - start_time > 1.5:
                break
            if difficulty == "challenge" and time.time() - start_time > 3.0:
                break

        except Exception:
            # If any depth fails, fall back to previous best move
            break

    if not best_move:
        # Emergency fallback: pick highest-scored candidate
        moves = _generate_moves(board, player, opponent, params["radius"], params["max_candidates"])
        if not moves:
            return None
        best_move = (moves[0][0], moves[0][1])

    # Add small noise to evaluation for easier difficulty (humanize)
    if params["noise"] > 0:
        best_score += random.randint(-params["noise"], params["noise"])

    return {
        "row": best_move[0],
        "col": best_move[1],
        "score": int(best_score),
        "depth": params["max_depth"],
    }
