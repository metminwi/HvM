# game/ai/difficulty.py
from dataclasses import dataclass

DifficultyId = str  # "easy" | "standard" | "challenge"

@dataclass(frozen=True)
class DifficultyConfig:
    depth: int
    time_limit_ms: int
    temperature: float  # useful for LLM/randomness later

DIFFICULTY_MAP = {
    "easy": DifficultyConfig(depth=1, time_limit_ms=250, temperature=0.7),
    "standard": DifficultyConfig(depth=2, time_limit_ms=500, temperature=0.4),
    "challenge": DifficultyConfig(depth=3, time_limit_ms=900, temperature=0.15),
}

def get_difficulty_config(difficulty: str | None) -> DifficultyConfig:
    if not difficulty:
        return DIFFICULTY_MAP["standard"]
    return DIFFICULTY_MAP.get(difficulty, DIFFICULTY_MAP["standard"])
