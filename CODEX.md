# CODEX.md — HvM (Human vs Machine)

## 0) Repository layout (source of truth)

Le dépôt HvM est physiquement séparé en deux applications :

- Frontend Next.js :
  `C:\Users\STJeanE\hvm-web`
  → UI, hooks React, client WebSocket, consommation API.

- Backend Django :
  `C:\Users\STJeanE\HvM`
  → API REST, logique métier Gomoku, authentification, WebSockets, IA.

⚠️ Toute modification doit respecter cette séparation physique.
Aucun code frontend ne doit être ajouté dans le backend, et inversement.
Les communications passent uniquement par HTTP (REST) et WebSocket.

---

## 1) Présentation du projet
**HvM (Human vs Machine)** est une plateforme de jeu cognitif **Gomoku** où :
- un joueur humain affronte une **IA** (Engine/Gemini/OpenSpiel),
- et/ou affronte un autre joueur en **PvP temps réel** via **WebSockets**.
L’objectif V2 est d’obtenir un produit **stable, sécurisé, typé strictement**, avec persistance complète (parties + coups), stats et expérience PvP fiable.

---

## 2) Architecture full-stack (séparation stricte)
HvM est composé de **deux applications distinctes** :

### Backend (Django + DRF)
Rôle :
- Authentification **session-based** + **CSRF**
- API REST : gameplay, historique, dashboard, leaderboard, feedback
- Endpoint IA unique : `POST /api/game/ai/move/`
- PvP : matchmaking (queue), états de partie, coups, abandon, règles de victoire
- Temps réel : **WebSocket** (lobby + groupes de game)

### Frontend (Next.js + TypeScript strict)
Rôle :
- UI (arena AI + dashboard + profile + PvP)
- Consommation API via **`apiFetch`** vers `/api/game/*`
- Connexion **WebSocket** pour le PvP (join lobby puis join game)
- Pages PvP : `app/pvp/game/[gameId]/page.tsx`

⚠️ Règle fondamentale : **aucun mélange** backend/frontend (pas de logique Django côté Next, pas de rendu React côté Django). Les interactions passent **uniquement** par HTTP (REST) et WS.

---

## 3) Stack technique détaillée

### Backend
- Python / Django
- Django REST Framework (APIView)
- Auth : session + CSRF (cookies `sessionid` / `csrftoken`)
- DB : SQLite en dev (peut évoluer vers Postgres en prod)
- PvP temps réel : Django Channels + Redis (recommandé) ou InMemory (dev)
- Services :
  - IA : moteurs Python modulaires (`engine`, `gemini`, `openspiel`)
  - PvP rules : détection alignement Gomoku (winner + winning_line)
  - WS notify : broadcast par groupe (lobby, pvp_game_<id>)

### Frontend
- Next.js (App Router)
- TypeScript **strict**
- ESLint strict (interdit `any`)
- `apiFetch` (wrapper central) :
  - gère CSRF bootstrap
  - `credentials: "include"`
  - parsing JSON robuste (évite HTML inattendu)
- WebSocket :
  - `/ws/lobby/` : événements matchmaking + join game
  - `pvp_game_<id>` : events `game.move`, `game.turn`, `game.ended`

---

## 4) Règles strictes de développement (obligatoires)

1. **TypeScript strict obligatoire**
   - Zéro `any` (ESLint interdit).
   - Toujours typer : payloads API, WS events, états React, retours de fonctions.

### Typage inconnu (fallback autorisé)

Si un payload ou événement est inconnu :
- utiliser `unknown` combiné avec `Record<string, unknown>`
- ne jamais utiliser `any`, même temporairement

Exemple standard :
`type UnknownWsEvent = { type: string } & Record<string, unknown>`

2. **Patch minimal uniquement**
   - Corriger le bug / ajouter la feature en modifiant **le minimum de lignes**.
   - Pas de refactor global, pas de renommage massif, pas de restructuration non demandée.

3. **Aucun breaking change**
   - Ne pas casser les routes existantes `/api/game/*`.
   - Ne pas changer les formats JSON sans adapter les clients.
   - Respecter les conventions existantes (APIView côté DRF, `apiFetch` côté Next).

4. **Séparation backend / frontend**
   - Les règles métier (victoire, tour, validation) restent côté **backend**.
   - Le frontend affiche et réagit (UI + state), sans re-implémenter les règles.

5. **Sécurité et stabilité avant tout**
   - Auth/CSRF : ne jamais retirer `credentials: "include"`.
   - Interdire les actions non autorisées : permissions DRF systématiques.
   - Toujours gérer : 400 / 401 / 403 / 404 / 409 / 500 avec messages clairs.

---

## 5) Structure logique du projet

### Backend Django (référence fonctionnelle)
- `game/urls.py` : routes API principales (`/api/game/...`)
- `game/urls_auth_session.py` : auth session (`/api/game/auth/...`)
- `game/views_session_auth.py` : endpoints CSRF/login/signup/logout/me
- `game/views.py` : gameplay AI (start, move, end, dashboard, history, leaderboard, ai/move)
- `game/views_pvp_queue.py` : queue join/cancel/status
- `game/views_pvp_game.py` : state/move/resign + broadcast WS
- `game/matchmaking.py` : `try_match()` (queue -> create PvPGame)
- `game/consumers.py` : `LobbyConsumer` (WS lobby) + group management
- `game/routing.py` + `asgi.py` : configuration Channels
- `game/services/pvp_rules.py` : détection victoire + `winning_line`
- `game/services/ws_notify.py` : helpers `notify_user`, `notify_game`

### Frontend Next.js (référence fonctionnelle)
- `lib/api.ts` : `apiFetch` + `ensureCsrf` (pas de récursion)
- `app/hooks/` :
  - `useSessionUser` : user session `/api/game/auth/me/`
  - `useDashboard` / `useDetailedDashboard` : stats `/api/game/dashboard/`
  - `useGomokuGame` : arena AI (start game, moves, ai move)
  - `usePvpGame` (hook central) : état PvP + WS + playMove + resign
- Pages :
  - AI arena : `app/.../page.tsx` (selon structure actuelle)
  - Dashboard : `app/cognitive-dashboard/page.tsx` (ou route équivalente)
  - PvP game : `app/pvp/game/[gameId]/page.tsx`

---

## 6) Directives de réponse pour Codex (format attendu)
Quand Codex répond / propose un changement, il doit fournir :

1. **Explication courte (2–6 lignes)**
   - Cause du bug / intention de la feature
   - Impact attendu

2. **Diff patch clair**
   - Format recommandé :
     - fichier → bloc de diff (`+` / `-`)
   - Ne montrer **que** les fichiers modifiés.

3. **Aucun `any`**
   - Si un type est inconnu, créer un type précis (`type`, `interface`, union).

4. **Étapes de test rapides**
   - Backend : commandes + endpoints à appeler
   - Frontend : page à ouvrir + cas de test utilisateur

---

## 7) Zones critiques du code (à connaître absolument)

### A) Auth session + CSRF (fragile)
- Le frontend doit toujours envoyer :
  - `credentials: "include"`
  - header `X-CSRFToken` sur méthodes unsafe
- `ensureCsrf()` ne doit **jamais** appeler `apiFetch()` (sinon recursion).
- Les endpoints doivent être **alignés** et stables :
  - `/api/game/auth/csrf/`
  - `/api/game/auth/login/`
  - `/api/game/auth/signup/`
  - `/api/game/auth/logout/`
  - `/api/game/auth/me/`

### B) API_BASE / URL construction
- Éviter “double base URL”.
- Toujours supporter URL absolues vs relatives côté `apiFetch`.

### C) PvP Concurrency + validation server-side
- `try_match()` doit être atomic + `select_for_update`.
- `PvPGameMoveView` doit :
  - vérifier participant
  - vérifier tour
  - vérifier cellule libre
  - créer move
  - calculer victoire/draw
  - persister résultat
  - broadcast WS

### D) Temps réel (WebSockets)
- Group names :
  - Lobby : `pvp_lobby`
  - Game : `pvp_game_<id>`
- Events attendus :
  - `queue.matched`
  - `game.joined`
  - `game.move`
  - `game.turn`
  - `game.ended` (inclut `winning_line`)

### E) Typage strict frontend
- `WsEvent` doit être une union typed.
- Les réponses REST doivent être typées (éviter `apiFetch<any>`).
- Les props UI critiques :
  - `GomokuBoard` : `winningLine`, `lastMove`, `disabled`

---

## 8) Objectif global (stabiliser HvM V2)
Priorité V2 : **produit fiable** sans refactor inutile.

### Objectifs immédiats
- Zéro bug d’intégration (routes/CSRF/cookies)
- PvP stable :
  - matchmaking
  - sync d’état via WS + fallback REST
  - victoire/draw + `winning_line`
- Dashboard stable :
  - stats cohérentes
  - endpoints admin sécurisés

### Objectifs V2 (Roadmap “rapide mais pro”)
1. **Ranked PvP + ELO**
   - `PlayerRating` mis à jour après chaque match ranked
   - calcul ELO (K-factor configurable)
   - historique ELO / progression

2. **Rematch**
   - bouton rematch après `game.ended`
   - création d’un nouveau game entre mêmes joueurs
   - option : switch X/O ou conserver ordre

3. **Spectateurs**
   - mode read-only
   - WS join en tant que spectator
   - pas de permission pour jouer, uniquement recevoir events

4. **Admin analytics**
   - overview (users/games/moves/feedback)
   - stats par joueur
   - stats avancées par engine/difficulty
   - permissions strictes `IsAdminUser`

---

## Commandes de validation standard

### Backend (Django)
- `python manage.py check`
- `python manage.py test`
- `python manage.py runserver`

### Frontend (Next.js)
- `npm run lint`
- `npm run typecheck` (si configuré)
- `npm run dev`

---

## Tests rapides (référence Codex)

### Backend
- Lancer :
  - `python manage.py runserver`
  - (si WS) `daphne -p 8000 <project>.asgi:application` ou config Channels
- Vérifier :
  - `GET /api/game/auth/csrf/` → cookie csrftoken
  - `POST /api/game/auth/login/` → sessionid
  - PvP :
    - join queue → match → create PvPGame
    - `GET /api/game/pvp/games/<id>/state/`
    - `POST /api/game/pvp/games/<id>/move/`
    - victoire → `winning_line` présent

### Frontend
- Lancer :
  - `npm run dev`
- Vérifier :
  - login/signup OK (pas de HTML)
  - PvP :
    - 2 navigateurs (ou incognito) pour 2 users
    - matchmaking puis page `app/pvp/game/[gameId]`
    - move sync instant (WS)
    - victoire highlight via `winningLine`
