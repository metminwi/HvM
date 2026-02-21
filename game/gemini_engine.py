# game/gemini_engine.py
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
from typing import Any, Final

import google.generativeai as genai

try:
    # Optionnel mais utile pour détecter les erreurs transitoires (quota, 5xx, etc.)
    from google.api_core.exceptions import GoogleAPICallError, ResourceExhausted
except ImportError:  # pragma: no cover - au cas où la dépendance change
    GoogleAPICallError = Exception  # type: ignore
    ResourceExhausted = Exception  # type: ignore

logger = logging.getLogger(__name__)


Board = list[list[str]]
Move = tuple[int, int] | None


class GeminiGomokuAI:
    """
    IA Gomoku basée sur l'API Gemini.

    - Architecture orientée objet (un seul client/model initialisé dans __init__)
    - Méthode principale asynchrone: `get_best_move`
    - Retry avec backoff exponentiel
    - Validation stricte du coup (coordonnées + case vide)
    - Fallback sur un coup 'intelligent' si l'API échoue ou hallucine

    Intégration typique côté appelant (dans un contexte async) :

        ai = GeminiGomokuAI()
        move = await ai.get_best_move(board, ai_symbol="O", human_symbol="X")

    `board` est une grille 15x15 de chaînes: "", "X", "O".
    """

    DEFAULT_MODEL: Final[str] = "gemini-2.5-flash"

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = DEFAULT_MODEL,
        max_retries: int = 3,
        base_retry_delay: float = 0.5,
        temperature: float = 0.3,
    ) -> None:
        self._api_key: str | None = api_key or os.getenv("GOOGLE_API_KEY")
        self._model_name: str = model_name
        self._max_retries: int = max_retries
        self._base_retry_delay: float = base_retry_delay
        self._temperature: float = temperature

        self._enabled: bool = self._api_key is not None

        if not self._enabled:
            logger.warning(
                "[GeminiGomokuAI] Aucune GOOGLE_API_KEY détectée. "
                "L'IA sera désactivée et un fallback sera utilisé."
            )
            self._model = None
            return

        # Configuration du client Gemini – effectué une seule fois
        genai.configure(api_key=self._api_key)
        self._model = genai.GenerativeModel(self._model_name)

        # Config de génération : JSON strict pour limiter les hallucinations de format
        self._generation_config: dict[str, Any] = {
            "temperature": self._temperature,
            "response_mime_type": "application/json",
        }

    # -------------------------------------------------------------------------
    # API publique
    # -------------------------------------------------------------------------
    async def get_best_move(
        self,
        board: Board,
        ai_symbol: str = "O",
        human_symbol: str = "X",
    ) -> Move:
        """
        Choisit le meilleur coup pour l'IA.

        - Utilise Gemini si possible (asynchrone)
        - Valide et nettoie la réponse JSON
        - Fallback sur un coup 'intelligent' si erreur/hallucination

        Retourne:
            (row, col) ou None si aucune case vide.
        """
        if not board or not board[0]:
            logger.error("[GeminiGomokuAI] Board vide ou mal formé.")
            return None

        # Si pas de clé API, on utilise directement le fallback.
        if not self._enabled or self._model is None:
            logger.info("[GeminiGomokuAI] IA désactivée -> fallback immédiat.")
            return self._select_fallback_move(board, ai_symbol, human_symbol)

        system_instruction = self._build_system_instruction(ai_symbol, human_symbol)
        user_prompt = self._build_user_prompt(board)

        try:
            response = await self._call_model_with_retry(system_instruction, user_prompt)
            raw_json = self._extract_json_text(response)
            logger.debug("[GeminiGomokuAI] Réponse JSON brute: %s", raw_json)

            move = self._parse_and_validate_move(raw_json, board)
            if move is not None:
                logger.info("[GeminiGomokuAI] Coup choisi par Gemini: %s", move)
                return move

            logger.warning(
                "[GeminiGomokuAI] Coup retourné invalide ou JSON incorrect -> fallback."
            )
            return self._select_fallback_move(board, ai_symbol, human_symbol)

        except Exception as exc:
            # Toute erreur (réseau, parsing, etc.) → fallback
            logger.exception("[GeminiGomokuAI] Erreur lors de l'appel Gemini -> fallback: %r", exc)
            return self._select_fallback_move(board, ai_symbol, human_symbol)

    # -------------------------------------------------------------------------
    # Construction du prompt
    # -------------------------------------------------------------------------
    def _build_system_instruction(self, ai_symbol: str, human_symbol: str) -> str:
        """
        Prompt système pour Gemini.

        Remarque: On demande à Gemini de raisonner étape par étape INTERNEMENT,
        mais de NE renvoyer que l'objet JSON final. Ceci exploite sa "Chain of Thought"
        interne sans la faire apparaître dans la réponse (ce qui limite la taille et
        accélère le parsing).
        """
        return (
            "You are a very strong Gomoku (five-in-a-row) AI.\n"
            "- Board size: 15x15.\n"
            "- Cells contain 'X', 'O', or '.' for empty.\n"
            f"- You play as '{ai_symbol}'. The human plays as '{human_symbol}'.\n"
            "- Goal: make a line of AT LEAST 5 stones in a row horizontally, vertically or diagonally.\n"
            "- You must ALWAYS play on an empty cell ('.').\n"
            "- You should internally think through the position carefully (threats, immediate wins, blocks), "
            "but your final output MUST ONLY be JSON.\n"
            "\n"
            "Move selection priority (in order):\n"
            "  1) Immediate win (create a line of 5 or more).\n"
            "  2) Block the opponent from creating a line of 5.\n"
            "  3) Create or extend strong threats (open lines of 3 or 4, central control).\n"
            "\n"
            "CRITICAL FORMATTING RULE:\n"
            "Respond with a SINGLE JSON object with exactly two integer fields:\n"
            '{\"row\": <zero_based_row>, \"col\": <zero_based_col>}.\n'
            "Do NOT include any explanation, comments, or extra fields."
        )

    def _build_user_prompt(self, board: Board) -> str:
        board_text = self._board_to_text(board)
        return (
            "Here is the current 15x15 Gomoku board, one row per line:\n"
            f"{board_text}\n\n"
            "It is your turn. Choose a strong move (try to win or block) and answer ONLY "
            "with a JSON object like:\n"
            '{"row": 7, "col": 8}'
        )

    # -------------------------------------------------------------------------
    # Appel modèle + Retry
    # -------------------------------------------------------------------------
    async def _call_model_with_retry(
        self,
        system_instruction: str,
        user_prompt: str,
    ) -> Any:
        """
        Appelle le modèle Gemini avec un mécanisme de retry + backoff exponentiel.

        - Retry sur ResourceExhausted (quota/limites) et GoogleAPICallError (erreurs 5xx probables).
        - Autres erreurs sont propagées au niveau supérieur.
        """
        last_exc: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                logger.info(
                    "[GeminiGomokuAI] Appel Gemini (tentative %d/%d)...",
                    attempt + 1,
                    self._max_retries,
                )
                # On déporte l'appel bloquant dans un thread pour ne pas bloquer
                # la boucle d'événements asyncio.
                response = await asyncio.to_thread(
                    self._model.generate_content,
                    [system_instruction, user_prompt],
                    generation_config=self._generation_config,
                )
                return response

            except ResourceExhausted as exc:  # quota ou surcharge
                last_exc = exc
                delay = self._base_retry_delay * (2**attempt)
                logger.warning(
                    "[GeminiGomokuAI] ResourceExhausted, retry dans %.2fs (tentative %d/%d)...",
                    delay,
                    attempt + 1,
                    self._max_retries,
                )
                await asyncio.sleep(delay)

            except GoogleAPICallError as exc:
                # Très souvent des erreurs de type 5xx ou réseau.
                last_exc = exc
                delay = self._base_retry_delay * (2**attempt)
                logger.warning(
                    "[GeminiGomokuAI] GoogleAPICallError, retry dans %.2fs (tentative %d/%d)...",
                    delay,
                    attempt + 1,
                    self._max_retries,
                )
                await asyncio.sleep(delay)

        # Si on arrive ici, toutes les tentatives ont échoué
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("Gemini call failed without specific exception")

    # -------------------------------------------------------------------------
    # Parsing / Validation de la réponse JSON
    # -------------------------------------------------------------------------
    def _extract_json_text(self, response: Any) -> str:
        """
        Extrait le texte JSON de la réponse Gemini.

        Avec `response_mime_type='application/json'`, `response.text` devrait déjà
        contenir une chaîne JSON valide. On garde tout de même un fallback au cas où.
        """
        text = getattr(response, "text", "") or ""
        if not text and getattr(response, "candidates", None):
            try:
                # Fallback ultra défensif si la structure change
                candidate = response.candidates[0]
                part = candidate.content.parts[0]
                text = getattr(part, "text", "") or ""
            except Exception:  # pragma: no cover
                logger.warning(
                    "[GeminiGomokuAI] Impossible d'extraire le texte via 'candidates'."
                )

        text = text.strip()
        text = self._clean_json_text(text)
        return text

    def _parse_and_validate_move(self, raw_json: str, board: Board) -> Move:
        """
        Parse le JSON retourné par Gemini, récupère (row, col) et vérifie que :

        - row et col sont des entiers
        - les indices sont dans la grille
        - la case est vide
        """
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            logger.error("[GeminiGomokuAI] JSON invalide: %s", raw_json)
            return None

        if not isinstance(data, dict):
            logger.error("[GeminiGomokuAI] JSON doit être un objet, reçu: %r", data)
            return None

        if "row" not in data or "col" not in data:
            logger.error("[GeminiGomokuAI] Clés 'row'/'col' manquantes dans: %r", data)
            return None

        try:
            row = int(data["row"])
            col = int(data["col"])
        except (TypeError, ValueError):
            logger.error("[GeminiGomokuAI] 'row'/'col' ne sont pas des entiers: %r", data)
            return None

        n = len(board)
        if not (0 <= row < n and 0 <= col < n):
            logger.error("[GeminiGomokuAI] Coup hors du plateau: (%d, %d)", row, col)
            return None

        if board[row][col] != "":
            logger.error("[GeminiGomokuAI] Case déjà occupée pour (%d, %d).", row, col)
            return None

        return (row, col)

    # -------------------------------------------------------------------------
    # Fallback move "intelligent"
    # -------------------------------------------------------------------------
    def _select_fallback_move(
        self,
        board: Board,
        ai_symbol: str,
        human_symbol: str,
    ) -> Move:
        """
        Fallback simple mais un peu plus 'intelligent' qu'une première case vide :

        - Si le plateau est vide -> centre
        - Sinon:
          - On privilégie les cases vides adjacentes (distance <= 1) à une pierre existante
          - Si aucune, on joue au centre si possible
          - Sinon, case vide aléatoire
        """
        n = len(board)
        empty_cells: list[tuple[int, int]] = [
            (r, c)
            for r in range(n)
            for c in range(n)
            if board[r][c] == ""
        ]

        if not empty_cells:
            logger.info("[GeminiGomokuAI] Aucun coup possible (plateau plein).")
            return None

        # Plateau complètement vide ?
        if all(board[r][c] == "" for r in range(n) for c in range(n)):
            center = (n // 2, n // 2)
            logger.info("[GeminiGomokuAI] Fallback: plateau vide -> centre %s", center)
            return center

        def has_neighbor_stone(r: int, c: int) -> bool:
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < n and 0 <= nc < n:
                        if board[nr][nc] in (ai_symbol, human_symbol):
                            return True
            return False

        candidate_cells: list[tuple[int, int]] = [
            (r, c) for (r, c) in empty_cells if has_neighbor_stone(r, c)
        ]

        if candidate_cells:
            move = random.choice(candidate_cells)
            logger.info("[GeminiGomokuAI] Fallback: case adjacente -> %s", move)
            return move

        # Sinon on tente le centre
        center = (n // 2, n // 2)
        if board[center[0]][center[1]] == "":
            logger.info("[GeminiGomokuAI] Fallback: centre disponible -> %s", center)
            return center

        # Sinon totalement aléatoire
        move = random.choice(empty_cells)
        logger.info("[GeminiGomokuAI] Fallback: case vide aléatoire -> %s", move)
        return move

    # -------------------------------------------------------------------------
    # Utilitaires statiques
    # -------------------------------------------------------------------------
    @staticmethod
    def _board_to_text(board: Board) -> str:
        """
        Transforme la grille en texte compact X/O/. pour le prompt.
        """
        lines: list[str] = []
        for row in board:
            line = "".join(cell if cell in ("X", "O") else "." for cell in row)
            lines.append(line)
        return "\n".join(lines)

    @staticmethod
    def _clean_json_text(text: str) -> str:
        """
        Nettoie d'éventuels ```json ... ``` autour de la réponse.
        Utile si le modèle 'oublie' la contrainte MIME type.
        """
        text = text.strip()
        text = re.sub(r"^```json", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"^```", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
        return text


# -------------------------------------------------------------------------
# Optionnel : fonction de compatibilité synchrone
# -------------------------------------------------------------------------
def gemini_best_move(
    board: Board,
    ai_symbol: str = "O",
    human_symbol: str = "X",
) -> Move:
    """
    Fonction de compatibilité avec l'ancienne API synchrone.

    ⚠️ À utiliser uniquement dans un contexte SANS boucle asyncio déjà active.
    Dans un serveur async (FastAPI, Django async, etc.), il vaut mieux créer
    une instance de `GeminiGomokuAI` et appeler directement `await get_best_move`.
    """
    ai = GeminiGomokuAI()

    async def _run() -> Move:
        return await ai.get_best_move(board, ai_symbol, human_symbol)

    return asyncio.run(_run())
