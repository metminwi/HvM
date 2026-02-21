from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

Board = List[List[str]]  # "" | "X" | "O"

DIRECTIONS: List[Tuple[int, int]] = [
    (1, 0),   # vertical
    (0, 1),   # horizontal
    (1, 1),   # diag \
    (1, -1),  # diag /
]


def _in_bounds(n: int, r: int, c: int) -> bool:
    return 0 <= r < n and 0 <= c < n


def is_draw(board: Board) -> bool:
    return all(cell != "" for row in board for cell in row)


def check_winner_from_last_move(
    board: Board,
    row: int,
    col: int,
    player: str,
    win_len: int = 5,
) -> bool:
    """
    Efficient winner check using the last move only.
    player must be "X" or "O".
    """
    n = len(board)
    if not _in_bounds(n, row, col):
        return False
    if board[row][col] != player:
        return False

    for dr, dc in DIRECTIONS:
        count = 1

        # forward
        r, c = row + dr, col + dc
        while _in_bounds(n, r, c) and board[r][c] == player:
            count += 1
            r += dr
            c += dc

        # backward
        r, c = row - dr, col - dc
        while _in_bounds(n, r, c) and board[r][c] == player:
            count += 1
            r -= dr
            c -= dc

        if count >= win_len:
            return True

    return False


def find_winning_line_from_last_move(
    board: Board,
    row: int,
    col: int,
    player: str,
    win_len: int = 5,
) -> Optional[List[Dict[str, int]]]:
    """
    Returns winning line as [{"row": r, "col": c}, ...] if win, else None.
    Uses last move only.
    """
    n = len(board)
    if not _in_bounds(n, row, col):
        return None
    if board[row][col] != player:
        return None

    for dr, dc in DIRECTIONS:
        line: List[Tuple[int, int]] = [(row, col)]

        # forward
        r, c = row + dr, col + dc
        while _in_bounds(n, r, c) and board[r][c] == player:
            line.append((r, c))
            r += dr
            c += dc

        # backward
        r, c = row - dr, col - dc
        while _in_bounds(n, r, c) and board[r][c] == player:
            line.insert(0, (r, c))
            r -= dr
            c -= dc

        if len(line) >= win_len:
            # Return the whole segment (nicer for UI). If you prefer exactly 5, slice: line[:win_len]
            return [{"row": rr, "col": cc} for rr, cc in line]

    return None


def check_winner_board(
    board: Board,
    win_len: int = 5,
    last_move: Optional[Tuple[int, int]] = None,
) -> Dict[str, Any]:
    """
    Main API used by views:
    Returns:
      {
        "winner": "X"|"O"|None,
        "winning_line": [{"row":int,"col":int}, ...] or [],
        "draw": bool
      }

    If last_move is provided, checks around it first (fast path).
    """
    n = len(board)
    if n == 0:
        return {"winner": None, "winning_line": [], "draw": False}

    # fast path with last move
    if last_move is not None:
        lr, lc = last_move
        if _in_bounds(n, lr, lc):
            p = board[lr][lc]
            if p in ("X", "O"):
                line = find_winning_line_from_last_move(board, lr, lc, p, win_len=win_len)
                if line:
                    return {"winner": p, "winning_line": line, "draw": False}

    # full scan (still fine for 15x15)
    for r in range(n):
        for c in range(n):
            p = board[r][c]
            if p not in ("X", "O"):
                continue
            line = find_winning_line_from_last_move(board, r, c, p, win_len=win_len)
            if line:
                return {"winner": p, "winning_line": line, "draw": False}

    if is_draw(board):
        return {"winner": None, "winning_line": [], "draw": True}

    return {"winner": None, "winning_line": [], "draw": False}
