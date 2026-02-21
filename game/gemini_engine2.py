# game/gemini_engine.py
import os
import json
import re
#import google.generativeai as genai
import google.generativeai as genai

def board_to_text(board):
    """
    Transforme la grille en texte compact X/O/. pour le prompt.
    """
    lines = []
    for row in board:
        line = "".join(cell if cell in ("X", "O") else "." for cell in row)
        lines.append(line)
    return "\n".join(lines)


def _clean_json_text(text: str) -> str:
    """
    Enlève les éventuels ```json ... ``` autour de la réponse de Gemini.
    """
    text = text.strip()
    text = re.sub(r"^```json", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"^```", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def gemini_best_move(board, ai_symbol="O", human_symbol="X"):
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        print("[GEMINI] Pas de GOOGLE_API_KEY -> fallback première case vide.")
        n = len(board)
        for r in range(n):
            for c in range(n):
                if board[r][c] == "":
                    return (r, c)
        return None

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    board_text = board_to_text(board)

    system_instruction = (
        "You are a strong Gomoku AI (five-in-a-row game).\n"
        "- The board size is 15x15.\n"
        "- 'X' and 'O' are players, '.' are empty.\n"
        f"- You play as '{ai_symbol}', the human plays as '{human_symbol}'.\n"
        "- The goal is to make a line of AT LEAST 5 stones in a row "
        "(horizontally, vertically, or diagonally).\n"
        "- You must always play on an EMPTY cell ('.').\n"
        "- Always prefer moves that:\n"
        "  1) Win immediately (create a line of 5 or more), otherwise\n"
        "  2) Block the opponent from creating 5 in a row, otherwise\n"
        "  3) Improve your own threats (open lines of 3 or 4).\n"
        "You must ALWAYS return ONLY a JSON object with keys 'row' and 'col', "
        "both zero-based integers. No explanation text, only JSON."
    )


    user_prompt = (
        "Here is the current board (each line is a row):\n"
        f"{board_text}\n\n"
        "It is your turn. Choose a strong move (try to win or block) "
        "and reply ONLY with JSON like:\n"
        '{"row": 7, "col": 8}'
    )

    try:
        print("[GEMINI] Appel API en cours...")
        response = model.generate_content(
            [system_instruction, user_prompt],
            generation_config={"temperature": 0.3},
        )
        content = response.text or ""
        print("[GEMINI] Réponse brute:", content[:200], "...")
        content = _clean_json_text(content)
        data = json.loads(content)
        row = int(data["row"])
        col = int(data["col"])
        print(f"[GEMINI] Coup choisi: ({row}, {col})")
        return (row, col)
    except Exception as e:
        print("[GEMINI] Erreur API/JSON -> fallback:", repr(e))
        n = len(board)
        for r in range(n):
            for c in range(n):
                if board[r][c] == "":
                    return (r, c)
        return None
