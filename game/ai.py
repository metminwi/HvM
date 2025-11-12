# game/ai.py
# IA Gomoku simple : Minimax + alpha-beta, sélection de coups candidats proches
from math import inf

HUMAN = "X"
AI = "O"
EMPTY = ""

DIRECTIONS = [(1,0),(0,1),(1,1),(1,-1)]

def in_bounds(r, c, n):
    return 0 <= r < n and 0 <= c < n

def has_five(board, r, c, player):
    n = len(board)
    for dr, dc in DIRECTIONS:
        cnt = 1
        # forward
        rr, cc = r+dr, c+dc
        while in_bounds(rr, cc, n) and board[rr][cc] == player:
            cnt += 1; rr += dr; cc += dc
        # backward
        rr, cc = r-dr, c-dc
        while in_bounds(rr, cc, n) and board[rr][cc] == player:
            cnt += 1; rr -= dr; cc -= dc
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

def line_score(count, open_ends):
    """
    Heuristique simple :
    - cinq : victoire
    - 4 ouvert : 100000
    - 4 fermé : 10000
    - 3 ouvert : 1000
    - 2 ouvert : 100
    """
    if count >= 5: return 1_000_000
    if count == 4 and open_ends == 2: return 100_000
    if count == 4 and open_ends == 1: return 10_000
    if count == 3 and open_ends == 2: return 1_000
    if count == 2 and open_ends == 2: return 100
    return 0

def evaluate_player(board, player):
    n = len(board)
    opp = HUMAN if player == AI else AI
    score = 0
    for r in range(n):
        for c in range(n):
            if board[r][c] != player:
                continue
            for dr, dc in DIRECTIONS:
                cnt = 1
                rr, cc = r+dr, c+dc
                # forward
                while in_bounds(rr, cc, n) and board[rr][cc] == player:
                    cnt += 1; rr += dr; cc += dc
                open1 = in_bounds(rr, cc, n) and board[rr][cc] == EMPTY
                # backward
                rr, cc = r-dr, c-dc
                while in_bounds(rr, cc, n) and board[rr][cc] == player:
                    cnt += 1; rr -= dr; cc -= dc
                open2 = in_bounds(rr, cc, n) and board[rr][cc] == EMPTY
                score += line_score(cnt, open1 + open2)
    # léger bonus centre
    mid = n // 2
    for r in range(n):
        for c in range(n):
            if board[r][c] == player:
                score += max(0, 5 - (abs(r - mid) + abs(c - mid)))
    # pénalité si l’adversaire contrôle beaucoup
    opp_score = 0
    for r in range(n):
        for c in range(n):
            if board[r][c] != opp:
                continue
            for dr, dc in DIRECTIONS:
                cnt = 1
                rr, cc = r+dr, c+dc
                while in_bounds(rr, cc, n) and board[rr][cc] == opp:
                    cnt += 1; rr += dr; cc += dc
                open1 = in_bounds(rr, cc, n) and board[rr][cc] == EMPTY
                rr, cc = r-dr, c-dc
                while in_bounds(rr, cc, n) and board[rr][cc] == opp:
                    cnt += 1; rr -= dr; cc -= dc
                open2 = in_bounds(rr, cc, n) and board[rr][cc] == EMPTY
                opp_score += line_score(cnt, open1 + open2)
    return score - int(0.8 * opp_score)

def evaluate(board):
    return evaluate_player(board, AI)

def neighbors(board, dist=2):
    """
    Génère les cases vides proches de pions existants (limite l’arbre de recherche).
    """
    n = len(board)
    occ = [(r, c) for r in range(n) for c in range(n) if board[r][c] in (HUMAN, AI)]
    if not occ:
        # premier coup au centre
        m = n // 2
        return [(m, m)]
    cand = set()
    for r, c in occ:
        for rr in range(max(0, r - dist), min(n, r + dist + 1)):
            for cc in range(max(0, c - dist), min(n, c + dist + 1)):
                if board[rr][cc] == EMPTY:
                    cand.add((rr, cc))
    return list(cand)

def minimax(board, depth, alpha, beta, maximizing):
    winner = check_win(board)
    if winner == AI: return 1_000_000
    if winner == HUMAN: return -1_000_000
    if depth == 0: return evaluate(board)

    if maximizing:
        best = -inf
        for (r, c) in neighbors(board):
            board[r][c] = AI
            val = minimax(board, depth - 1, alpha, beta, False)
            board[r][c] = EMPTY
            if val > best: best = val
            if best > alpha: alpha = best
            if beta <= alpha: break
        return best
    else:
        best = inf
        for (r, c) in neighbors(board):
            board[r][c] = HUMAN
            val = minimax(board, depth - 1, alpha, beta, True)
            board[r][c] = EMPTY
            if val < best: best = val
            if best < beta: beta = best
            if beta <= alpha: break
        return best

def best_move(board, depth=2):
    """
    Retourne (row, col) pour l’IA.
    depth=2 (rapide), depth=4 (mode Pro).
    """
    n = len(board)
    # Copie “mutable” garantie : board est une liste de listes de str
    best_val = -inf
    move = None
    for (r, c) in neighbors(board):
        board[r][c] = AI
        val = minimax(board, depth - 1, -inf, inf, False)
        board[r][c] = EMPTY
        if val > best_val:
            best_val = val
            move = (r, c)
    # fallback si aucun move (grille pleine)
    if move is None:
        for r in range(n):
            for c in range(n):
                if board[r][c] == EMPTY:
                    return (r, c)
    return move
