# game/ai/engines/gemini_engine.py
from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import random


def compute_ai_move(
    board: List[List[int]],
    difficulty: str = "standard",
    current_player: int = -1,
) -> Tuple[int, int, Optional[Dict[str, int]]]:
    """
    Placeholder: random legal move.
    Replace later with real Gemini call.
    """
    n = len(board)
    legal = [(r, c) for r in range(n) for c in range(n) if board[r][c] == 0]
    if not legal:
        return 0, 0, None
    r, c = random.choice(legal)
    return r, c, None


# ✅ ALIAS (si ton code attend get_gemini_move)
def get_gemini_move(board, difficulty="standard", current_player=-1):
    return compute_ai_move(board, difficulty=difficulty, current_player=current_player)
