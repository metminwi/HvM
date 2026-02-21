# game/ai_router.py
from __future__ import annotations
from typing import Any, Dict, Optional, Tuple




from game.ai.engines.engine_engine import compute_ai_move as compute_engine_move
from game.ai.engines.gemini_engine import compute_ai_move as compute_gemini_move
from game.ai.engines.openspiel_engine import compute_ai_move as compute_openspiel_move


""" def compute_ai_move(*, board, engine: str, difficulty: str | None) -> Dict[str, Any]:
    difficulty = (difficulty or "standard").lower()

    if engine == "engine":
        depth_map = {"easy": 2, "standard": 3, "challenge": 4}
        depth = depth_map.get(difficulty, 3)
        row, col, meta = compute_engine_move(board, difficulty=difficulty, current_player=current_player)
        move = {"row": row, "col": col}
        return {"move": move, "meta": {"engine": "engine", **(meta or {})}}

    if engine == "gemini":
        move = get_gemini_move(board)
        return {"move": move, "meta": {"engine": "gemini"}}

    if engine == "openspiel":
        rollout_map = {"easy": 100, "standard": 400, "challenge": 1200}
        rollouts = rollout_map.get(difficulty, 400)
        move = get_openspiel_move(board, rollouts=rollouts)
        return {"move": move, "meta": {"engine": "openspiel", "rollouts": rollouts}}

    raise ValueError(f"Unknown engine '{engine}'. Expected engine|gemini|openspiel")
 """



def _engine_move(board, board_size: int, difficulty: str) -> Dict[str, Any]:
    # TODO: plug your minimax engine here
    move = _first_empty(board, board_size)
    return {"move": move, "ai_eval": 0, "depth": _depth_from_difficulty(difficulty), "winner": None}


def _gemini_move(board, board_size: int, difficulty: str) -> Dict[str, Any]:
    # TODO: call Gemini backend here
    move = _first_empty(board, board_size)
    return {"move": move, "ai_eval": 0, "depth": 0, "winner": None}


def _openspiel_move(board, board_size: int, difficulty: str) -> Dict[str, Any]:
    # TODO: call OpenSpiel engine here
    move = _first_empty(board, board_size)
    return {"move": move, "ai_eval": 0, "depth": 0, "winner": None}


def _first_empty(board, board_size: int) -> Optional[Dict[str, int]]:
    for r in range(board_size):
        for c in range(board_size):
            if board[r][c] == "empty":
                return {"row": r, "col": c}
    return None


def _depth_from_difficulty(difficulty: str) -> int:
    if difficulty == "easy":
        return 1
    if difficulty == "standard":
        return 2
    return 4  # challenge



def pick_ai_move(
    *,
    engine_id: str,
    board: List[List[int]],
    difficulty: str = "standard",
    current_player: int = -1,  # -1 = AI(O), 1 = Human(X)
) -> Tuple[int, int, Optional[Dict[str, Any]]]:
    """
    Returns (row, col, meta)
    meta is engine-specific (ex: {"score":..., "depth":...})
    """
    engine_id = (engine_id or "engine").lower()
    difficulty = (difficulty or "standard").lower()

    if engine_id == "engine":
        return compute_engine_move(board, difficulty=difficulty, current_player=current_player)

    if engine_id == "gemini":
        return compute_gemini_move(board, difficulty=difficulty, current_player=current_player)

    if engine_id == "openspiel":
        return compute_openspiel_move(board, difficulty=difficulty, current_player=current_player)

    # fallback safe
    return compute_engine_move(board, difficulty="easy", current_player=current_player)
