# game/ai/engines/engine_engine.py
from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import random

# Board encoding:
#   0  = empty
#   1  = Human (X)
#  -1  = AI (O)


def _difficulty_to_depth(difficulty: str) -> int:
    d = (difficulty or "standard").lower()
    if d == "easy":
        return 2
    if d == "standard":
        return 4
    if d == "challenge":
        return 6
    return 4


def _in_bounds(n: int, r: int, c: int) -> bool:
    return 0 <= r < n and 0 <= c < n


def _legal_moves(board: List[List[int]]) -> List[Tuple[int, int]]:
    n = len(board)
    return [(r, c) for r in range(n) for c in range(n) if board[r][c] == 0]


def _has_any_stone(board: List[List[int]]) -> bool:
    return any(v != 0 for row in board for v in row)


def _candidate_moves(board: List[List[int]], k: int = 18, radius: int = 2) -> List[Tuple[int, int]]:
    """
    Reduce branching: consider empty cells near existing stones.
    If board is empty -> play center.
    """
    n = len(board)
    if not _has_any_stone(board):
        center = n // 2
        return [(center, center)]

    candidates = set()
    for r in range(n):
        for c in range(n):
            if board[r][c] != 0:
                for dr in range(-radius, radius + 1):
                    for dc in range(-radius, radius + 1):
                        rr, cc = r + dr, c + dc
                        if _in_bounds(n, rr, cc) and board[rr][cc] == 0:
                            candidates.add((rr, cc))

    cand = list(candidates)
    # If too many, sample deterministically-ish by sorting then taking k
    cand.sort(key=lambda x: (abs(x[0] - n // 2) + abs(x[1] - n // 2), x[0], x[1]))
    return cand[:k] if len(cand) > k else cand


def _count_in_direction(board: List[List[int]], r: int, c: int, dr: int, dc: int, player: int) -> int:
    """Count consecutive stones for player starting from next cell in (dr,dc)."""
    n = len(board)
    cnt = 0
    rr, cc = r + dr, c + dc
    while _in_bounds(n, rr, cc) and board[rr][cc] == player:
        cnt += 1
        rr += dr
        cc += dc
    return cnt


def _is_winning_move(board: List[List[int]], r: int, c: int, player: int) -> bool:
    """Check if placing player at (r,c) makes 5 in a row."""
    if board[r][c] != 0:
        return False

    board[r][c] = player
    try:
        dirs = [(1, 0), (0, 1), (1, 1), (1, -1)]
        for dr, dc in dirs:
            a = _count_in_direction(board, r, c, dr, dc, player)
            b = _count_in_direction(board, r, c, -dr, -dc, player)
            if 1 + a + b >= 5:
                return True
        return False
    finally:
        board[r][c] = 0


def _heuristic(board: List[List[int]]) -> int:
    """
    Evaluate position from AI perspective.
    Positive => good for AI (-1), negative => good for Human (1).
    """
    n = len(board)
    center = n // 2

    # Center preference + local neighborhood activity
    score = 0
    for r in range(n):
        for c in range(n):
            v = board[r][c]
            if v == 0:
                continue
            # closer to center is better (both players, but weighted for AI)
            dist = abs(r - center) + abs(c - center)
            w_center = max(0, 8 - dist)  # small bonus
            # AI stones add, Human stones subtract
            score += (-v) * w_center  # because AI is -1 (so -(-1)=+1)

            # neighborhood influence
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    rr, cc = r + dr, c + dc
                    if _in_bounds(n, rr, cc) and board[rr][cc] == 0:
                        score += (-v) * 1

    return score


def _minimax_ab(
    board: List[List[int]],
    depth: int,
    player_to_move: int,
    alpha: int,
    beta: int,
) -> int:
    """
    Alpha-beta minimax.
    player_to_move: -1 AI, 1 Human
    Returns evaluation from AI perspective.
    """
    # Terminal / depth limit
    if depth == 0:
        return _heuristic(board)

    # Candidate moves to reduce branching
    moves = _candidate_moves(board, k=20, radius=2)
    if not moves:
        return _heuristic(board)

    # Quick tactical: immediate win / immediate block
    # If current player can win now, prioritize
    for r, c in moves:
        if _is_winning_move(board, r, c, player_to_move):
            # Big swing: if AI wins => very positive; if Human wins => very negative
            return 10**8 if player_to_move == -1 else -(10**8)

    # If opponent has an immediate win next, block if possible (tactical safety)
    opp = -player_to_move
    opp_wins = [(r, c) for (r, c) in moves if _is_winning_move(board, r, c, opp)]
    if opp_wins:
        # If multiple threats, still evaluate deeper, but this penalizes not blocking
        # Encourage blocking by returning a big value for the side to move if it can block.
        # We handle by continuing search; leaf heuristic will incorporate it poorly,
        # so we add a tactical bias:
        pass

    maximizing = (player_to_move == -1)  # AI maximizes

    if maximizing:
        best = -10**9
        for r, c in moves:
            if board[r][c] != 0:
                continue
            board[r][c] = -1
            val = _minimax_ab(board, depth - 1, 1, alpha, beta)
            board[r][c] = 0
            best = max(best, val)
            alpha = max(alpha, best)
            if beta <= alpha:
                break
        return best
    else:
        best = 10**9
        for r, c in moves:
            if board[r][c] != 0:
                continue
            board[r][c] = 1
            val = _minimax_ab(board, depth - 1, -1, alpha, beta)
            board[r][c] = 0
            best = min(best, val)
            beta = min(beta, best)
            if beta <= alpha:
                break
        return best


def compute_ai_move(
    board: List[List[int]],
    difficulty: str = "standard",
    current_player: int = -1,
) -> Tuple[int, int, Optional[Dict[str, int]]]:
    """
    Returns (row, col, meta)
    meta: {"score": int, "depth": int}
    """
    depth = _difficulty_to_depth(difficulty)

    # Safety: validate board shape
    n = len(board)
    if n == 0 or any(len(row) != n for row in board):
        # fallback
        return 0, 0, {"score": 0, "depth": depth}

    # If board empty -> center
    if not _has_any_stone(board):
        center = n // 2
        return center, center, {"score": 0, "depth": depth}

    # Candidate moves near stones
    moves = _candidate_moves(board, k=24, radius=2)
    if not moves:
        # fallback to any legal move
        lm = _legal_moves(board)
        if not lm:
            return 0, 0, {"score": 0, "depth": depth}
        r, c = random.choice(lm)
        return r, c, {"score": 0, "depth": depth}

    # Tactical: immediate win for AI
    for r, c in moves:
        if _is_winning_move(board, r, c, -1):
            return r, c, {"score": 10**8, "depth": depth}

    # Tactical: block immediate win for Human
    threats = [(r, c) for (r, c) in moves if _is_winning_move(board, r, c, 1)]
    if threats:
        # if multiple, pick one closest to center
        threats.sort(key=lambda x: (abs(x[0] - n // 2) + abs(x[1] - n // 2), x[0], x[1]))
        r, c = threats[0]
        return r, c, {"score": 10**7, "depth": depth}

    best_score = -10**9
    best_moves: List[Tuple[int, int]] = []

    for r, c in moves:
        if board[r][c] != 0:
            continue
        board[r][c] = -1
        score = _minimax_ab(board, depth - 1, player_to_move=1, alpha=-10**9, beta=10**9)
        board[r][c] = 0

        if score > best_score:
            best_score = score
            best_moves = [(r, c)]
        elif score == best_score:
            best_moves.append((r, c))

    if not best_moves:
        # fallback safe
        lm = _legal_moves(board)
        if not lm:
            return 0, 0, {"score": 0, "depth": depth}
        r, c = random.choice(lm)
        return r, c, {"score": 0, "depth": depth}

    row, col = random.choice(best_moves)
    return row, col, {"score": int(best_score), "depth": int(depth)}


# ✅ Alias (compat import)
def get_engine_move(
    board: List[List[int]],
    difficulty: str = "standard",
    current_player: int = -1,
):
    return compute_ai_move(board, difficulty=difficulty, current_player=current_player)
