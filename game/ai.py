# game/ai.py
from math import inf
import time

HUMAN = "X"
AI = "O"
EMPTY = ""

DIRECTIONS = [(1, 0), (0, 1), (1, 1), (1, -1)]


def in_bounds(r, c, n):
    return 0 <= r < n and 0 <= c < n


def has_five(board, r, c, player):
    n = len(board)
    for dr, dc in DIRECTIONS:
        cnt = 1
        rr, cc = r + dr, c + dc
        while in_bounds(rr, cc, n) and board[rr][cc] == player:
            cnt += 1
            rr += dr
            cc += dc
        rr, cc = r - dr, c - dc
        while in_bounds(rr, cc, n) and board[rr][cc] == player:
            cnt += 1
            rr -= dr
            cc -= dc
        if cnt >= 5:
            return True
    return False


def check_win(board):
    n = len(board)
    for r in range(n):
        for c in range(n):
            if board[r][c] in (HUMAN, AI):
                if has_five(board, r, c, board[r][c]):
                    return board[r][c]
    return None


def basic_neighbors(board, dist=2):
    """
    Version simple: cases vides proches de n'importe quel pion.
    Utilisé comme fallback dans la génération de coups avancée.
    """
    n = len(board)
    occ = [(r, c) for r in range(n) for c in range(n) if board[r][c] in (HUMAN, AI)]
    if not occ:
        m = n // 2
        return [(m, m)]
    cand = set()
    for r, c in occ:
        for rr in range(max(0, r - dist), min(n, r + dist + 1)):
            for cc in range(max(0, c - dist), min(n, c + dist + 1)):
                if board[rr][cc] == EMPTY:
                    cand.add((rr, cc))
    return list(cand)


# Poids de patterns pour l'évaluation (après mapping du joueur courant sur 'O')
PATTERN_SCORES = {
    "OOOOO": 1_000_000,   # 5 en ligne
    "OOOO_": 100_000,
    "_OOOO": 100_000,
    "_OOOO_": 150_000,    # 4 ouvert des deux côtés
    "OOO_O": 80_000,
    "OO_OO": 80_000,
    "_OOO_": 5_000,       # 3 ouvert
    "OOO__": 3_000,
    "__OOO": 3_000,
    "_OOO": 3_000,        # approximations de 3 "dangereux"
    "OO_O_": 3_000,
    "_O_OO": 3_000,
    "_OO_": 500,          # 2 ouvert
    "__OO_": 300,
    "_OO__": 300,
}


class AdvancedGomokuAI:
    def __init__(self, size=15, ai_player=AI):
        self.size = size
        self.ai_player = ai_player
        self.human_player = HUMAN if ai_player == AI else AI

        # Optimisations de recherche
        self.transposition_table = {}
        self.killer_moves = {}       # depth -> [move1, move2]
        self.history_heuristic = {}  # (player, move) -> score
        self.opening_book = {}       # TODO: bibliothèque d'ouvertures

        # Stats pour benchmarking
        self.nodes = 0
        self.cutoffs = 0
        self.eval_calls = 0

        self.time_limit = None
        self.start_time = None

    # --------- Utilitaires / hash ---------

    def _board_key(self, board, player, depth):
        # Simple clé de transposition (remplaçable par un hash Zobrist plus rapide)
        return (player, depth, tuple(tuple(row) for row in board))

    # --------- Évaluation avancée ---------

    def _extract_lines(self, board):
        n = len(board)
        lines = []

        # Lignes horizontales
        for r in range(n):
            lines.append("".join(board[r][c] if board[r][c] != EMPTY else "." for c in range(n)))

        # Colonnes
        for c in range(n):
            col = []
            for r in range(n):
                col.append(board[r][c] if board[r][c] != EMPTY else ".")
            lines.append("".join(col))

        # Diagonales (↘)
        for k in range(-n + 1, n):
            diag = []
            for r in range(n):
                c = r + k
                if 0 <= c < n:
                    diag.append(board[r][c] if board[r][c] != EMPTY else ".")
            if len(diag) >= 5:
                lines.append("".join(diag))

        # Diagonales (↗)
        for k in range(0, 2 * n - 1):
            diag = []
            for r in range(n):
                c = k - r
                if 0 <= c < n:
                    diag.append(board[r][c] if board[r][c] != EMPTY else ".")
            if len(diag) >= 5:
                lines.append("".join(diag))

        return lines

    def _score_line_patterns(self, line, player_char):
        """
        Score une ligne pour un joueur donné.
        On mappe:
          - player_char    -> 'O'
          - adversaire     -> 'X'
          - vide / autre   -> '_'
        puis on applique PATTERN_SCORES.
        """
        opp_char = self.human_player if player_char == self.ai_player else self.ai_player
        mapped = []
        for ch in line:
            if ch == player_char:
                mapped.append("O")
            elif ch == opp_char:
                mapped.append("X")
            else:
                mapped.append("_")
        mapped = "".join(mapped)

        s = 0
        for pattern, value in PATTERN_SCORES.items():
            idx = mapped.find(pattern)
            while idx != -1:
                s += value
                idx = mapped.find(pattern, idx + 1)
        return s

    def enhanced_evaluation(self, board):
        """
        Évaluation avancée :
        - patterns d'attaque / défense
        - bonus central
        - défense légèrement surpondérée
        """
        self.eval_calls += 1

        winner = check_win(board)
        if winner == self.ai_player:
            return 1_000_000
        if winner == self.human_player:
            return -1_000_000

        ai_score = 0
        human_score = 0
        lines = self._extract_lines(board)

        for line in lines:
            ai_score += self._score_line_patterns(line, self.ai_player)
            human_score += self._score_line_patterns(line, self.human_player)

        # Bonus de contrôle du centre
        n = len(board)
        mid = n // 2
        center_bonus_ai = 0
        center_bonus_human = 0
        for r in range(n):
            for c in range(n):
                if board[r][c] == self.ai_player:
                    center_bonus_ai += max(0, 8 - (abs(r - mid) + abs(c - mid)))
                elif board[r][c] == self.human_player:
                    center_bonus_human += max(0, 8 - (abs(r - mid) + abs(c - mid)))

        ai_score += center_bonus_ai
        human_score += center_bonus_human

        # Défense un peu plus importante
        return ai_score - int(1.1 * human_score)

    # --------- Génération & tri de coups ---------

    def generate_moves(self, board, last_move=None, dist=2):
        """
        Génère les coups candidats autour du dernier coup.
        Fallback sur basic_neighbors si pas assez de candidats.
        """
        n = len(board)
        occ = [(r, c) for r in range(n) for c in range(n) if board[r][c] in (HUMAN, AI)]
        if not occ:
            m = n // 2
            return [(m, m)]

        cand = set()
        if last_move:
            lr, lc = last_move
            for rr in range(max(0, lr - dist), min(n, lr + dist + 1)):
                for cc in range(max(0, lc - dist), min(n, lc + dist + 1)):
                    if board[rr][cc] == EMPTY:
                        cand.add((rr, cc))

        # Si pas assez de candidats, on élargit
        if len(cand) < 6:
            cand.update(basic_neighbors(board, dist))

        return list(cand)

    def advanced_move_ordering(self, board, moves, player, depth, last_move=None):
        """
        Tri heuristique des coups :
        - coups gagnants immédiats
        - blocks gagnants adverses
        - killer moves
        - history heuristic
        - proximité du centre / du dernier coup
        """
        n = len(board)
        mid = n // 2
        opponent = self.human_player if player == self.ai_player else self.ai_player

        killer_list = self.killer_moves.get(depth, [])
        scored = []

        for (r, c) in moves:
            score = 0
            move = (r, c)

            # Proximité du centre
            score -= (abs(r - mid) + abs(c - mid))

            # Killer moves
            if move in killer_list:
                score += 50_000

            # History heuristic
            score += self.history_heuristic.get((player, move), 0)

            # Coups tactiques immédiats
            board[r][c] = player
            if check_win(board) == player:
                score += 1_000_000  # coup gagnant
            else:
                # Coup qui bloque un gain adverse
                board[r][c] = opponent
                if check_win(board) == opponent:
                    score += 200_000
            board[r][c] = EMPTY

            # Proximité du dernier coup
            if last_move and max(abs(r - last_move[0]), abs(c - last_move[1])) <= 1:
                score += 1_000

            scored.append((score, move))

        scored.sort(reverse=True, key=lambda x: x[0])
        return [m for _, m in scored]

    # --------- Quiescence search ---------

    def _is_time_over(self):
        if self.time_limit is None:
            return False
        return (time.time() - self.start_time) >= self.time_limit

    def _is_quiet(self, board):
        """
        Position "calme" si aucun 5 en ligne détecté.
        (On pourrait affiner en détectant aussi les 4 ouverts.)
        """
        n = len(board)
        for r in range(n):
            for c in range(n):
                if board[r][c] in (self.ai_player, self.human_player):
                    if has_five(board, r, c, board[r][c]):
                        return False
        return True

    def quiescence_search(self, board, alpha, beta, player, last_move=None, q_depth=2):
        self.nodes += 1
        stand_pat = self.enhanced_evaluation(board)

        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat

        if q_depth == 0 or self._is_quiet(board):
            return stand_pat

        moves = self.generate_moves(board, last_move=last_move, dist=1)
        ordered = self.advanced_move_ordering(board, moves, player, depth=-1, last_move=last_move)

        opponent = self.human_player if player == self.ai_player else self.ai_player

        for (r, c) in ordered:
            board[r][c] = player
            score = -self.quiescence_search(
                board, -beta, -alpha, opponent, last_move=(r, c), q_depth=q_depth - 1
            )
            board[r][c] = EMPTY

            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

        return alpha

    # --------- Alpha-bêta amélioré ---------

    def alpha_beta(self, board, depth, alpha, beta, player, maximizing, last_move=None, ply=0):
        if self._is_time_over():
            # Si temps dépassé: fallback sur une évaluation statique
            return self.enhanced_evaluation(board)

        self.nodes += 1

        winner = check_win(board)
        if winner == self.ai_player:
            return 1_000_000 - ply  # gagner plus tôt est mieux
        if winner == self.human_player:
            return -1_000_000 + ply  # perdre plus tard est légèrement mieux

        if depth == 0:
            return self.quiescence_search(board, alpha, beta, player, last_move=last_move)

        alpha_orig, beta_orig = alpha, beta

        # Table de transposition
        key = self._board_key(board, player, depth)
        tt_entry = self.transposition_table.get(key)
        if tt_entry is not None:
            stored_val, stored_depth, stored_flag = tt_entry
            if stored_depth >= depth:
                if stored_flag == "EXACT":
                    return stored_val
                elif stored_flag == "LOWERBOUND":
                    alpha = max(alpha, stored_val)
                elif stored_flag == "UPPERBOUND":
                    beta = min(beta, stored_val)
                if alpha >= beta:
                    return stored_val

        moves = self.generate_moves(board, last_move=last_move)
        if not moves:
            return self.enhanced_evaluation(board)

        ordered_moves = self.advanced_move_ordering(board, moves, player, depth, last_move=last_move)
        opponent = self.human_player if player == self.ai_player else self.ai_player

        best_val = -inf if maximizing else inf

        for (r, c) in ordered_moves:
            board[r][c] = player
            val = self.alpha_beta(
                board,
                depth - 1,
                alpha,
                beta,
                opponent,
                not maximizing,
                last_move=(r, c),
                ply=ply + 1,
            )
            board[r][c] = EMPTY

            if maximizing:
                if val > best_val:
                    best_val = val
                if best_val > alpha:
                    alpha = best_val
                if val >= beta:
                    self.cutoffs += 1
                    # killer move & history heuristic
                    killers = self.killer_moves.get(depth, [])
                    move = (r, c)
                    if move not in killers:
                        killers = [move] + killers[:1]
                        self.killer_moves[depth] = killers
                    self.history_heuristic[(player, move)] = (
                        self.history_heuristic.get((player, move), 0) + depth * depth
                    )
                    break
            else:
                if val < best_val:
                    best_val = val
                if best_val < beta:
                    beta = best_val
                if val <= alpha:
                    self.cutoffs += 1
                    killers = self.killer_moves.get(depth, [])
                    move = (r, c)
                    if move not in killers:
                        killers = [move] + killers[:1]
                        self.killer_moves[depth] = killers
                    self.history_heuristic[(player, move)] = (
                        self.history_heuristic.get((player, move), 0) + depth * depth
                    )
                    break

        # Mise à jour de la table de transposition
        flag = "EXACT"
        if best_val <= alpha_orig:
            flag = "UPPERBOUND" if maximizing else "LOWERBOUND"
        elif best_val >= beta_orig:
            flag = "LOWERBOUND" if maximizing else "UPPERBOUND"
        self.transposition_table[key] = (best_val, depth, flag)

        return best_val

    # --------- Iterative deepening ---------

    def iterative_deepening(self, board, max_depth, time_limit):
        self.time_limit = time_limit
        self.start_time = time.time()

        best_move = None
        best_score = None

        for depth in range(1, max_depth + 1):
            self.killer_moves.clear()  # on réinitialise les killer moves à chaque itération
            try_move, try_score = self._search_root(board, depth)
            if self._is_time_over():
                break
            best_move, best_score = try_move, try_score

        return best_move, best_score

    def _search_root(self, board, depth):
        """
        Recherche à la racine : on sait que c'est le tour de l'IA.
        """
        player = self.ai_player
        moves = self.generate_moves(board)
        ordered = self.advanced_move_ordering(board, moves, player, depth, last_move=None)
        opponent = self.human_player

        best_val = -inf
        best_move = None

        alpha, beta = -inf, inf
        for (r, c) in ordered:
            if self._is_time_over():
                break
            board[r][c] = player
            val = self.alpha_beta(
                board,
                depth - 1,
                alpha,
                beta,
                opponent,
                maximizing=False,
                last_move=(r, c),
                ply=1,
            )
            board[r][c] = EMPTY
            if val > best_val:
                best_val = val
                best_move = (r, c)
            if val > alpha:
                alpha = val

        return best_move, best_val

    # --------- API publique ---------

    def best_move(self, board, depth=3, time_limit=None):
        """
        Choisit le meilleur coup pour l'IA.
        - si time_limit est fourni : iterative deepening
        - sinon : profondeur fixe

        Retourne:
          - move : (row, col)
          - stats : dict (score, nodes, cutoffs, eval_calls)
        """
        self.size = len(board)
        self.nodes = 0
        self.cutoffs = 0
        self.eval_calls = 0
        self.transposition_table.clear()

        if time_limit is not None:
            move, score = self.iterative_deepening(board, depth, time_limit)
        else:
            self.time_limit = None
            self.start_time = None
            move, score = self._search_root(board, depth)

        return move, {
            "score": score,
            "nodes": self.nodes,
            "cutoffs": self.cutoffs,
            "eval_calls": self.eval_calls,
        }


# Singleton pratique si tu veux garder une API fonctionnelle simple
_global_ai = AdvancedGomokuAI()


def best_move(board, depth=3, time_limit=None):
    """
    API externe compatible avec ton code actuel :
    - board : plateau (list[list[str]])
    - depth : profondeur max
    - time_limit (sec) : optionnel. Si fourni, utilise iterative deepening.

    Retourne :
      (row, col)
    """
    move, stats = _global_ai.best_move(board, depth=depth, time_limit=time_limit)
    return move
