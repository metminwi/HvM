# game/ai/engines/base.py
from typing import Any, Optional, TypedDict

class Move(TypedDict):
    row: int
    col: int

class EngineResult(TypedDict, total=False):
    move: Optional[Move]
    score: float
    depth: int
    engine: str
    detail: Any
