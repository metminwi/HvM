# ARCHITECTURE.md — HvM (Human vs Machine)

## 1. Vue d’ensemble système

**HvM (Human vs Machine)** est une plateforme SaaS de jeu cognitif **Gomoku** combinant :
- **Human vs AI** (moteurs IA multiples),
- **PvP temps réel** via WebSockets,
- **authentification session sécurisée**,
- **persistance complète** (parties, coups, stats).

L’architecture repose sur une **séparation stricte backend / frontend** :
- le **backend** est la *source de vérité* (règles, sécurité, données),
- le **frontend** est une *projection UI* synchronisée par REST et WebSocket.

---

## 2. Séparation backend / frontend

### Backend (Django)
Responsabilités :
- Authentification session + CSRF
- API REST (`/api/game/*`)
- Logique métier Gomoku (règles, victoire, ELO futur)
- Matchmaking PvP
- Temps réel via WebSockets (Channels)
- Persistance DB

👉 **Aucune logique UI ou état client persistant.**

### Frontend (Next.js)
Responsabilités :
- Interface utilisateur (AI, PvP, dashboard, profil)
- Appels API via `apiFetch`
- Gestion d’état local (React hooks)
- Connexion WebSocket pour synchronisation temps réel

👉 **Aucune règle métier, aucune décision de validation.**

---

## 3. Composants majeurs

### 3.1 API REST
- `/api/game/start/`, `/move/`, `/end/`
- `/api/game/ai/move/`
- `/api/game/dashboard/`, `/leaderboard/`
- `/api/game/pvp/*` (queue, state, move, resign)

Technologie :
- Django REST Framework (`APIView`)
- Permissions explicites
- JSON strict, stable

---

### 3.2 Services métier (Backend)
- **IA** : moteurs modulaires (`engine`, `gemini`, `openspiel`)
- **PvP rules** : détection victoire Gomoku + `winning_line`
- **Matchmaking** : queue + `try_match()` atomique
- **WS notify** : broadcast lobby / game

---

### 3.3 WebSockets temps réel
- Django Channels + Redis (prod)
- Synchronisation d’état PvP
- Notifications matchmaking

---

### 3.4 Persistance des données
- SQLite (dev) → PostgreSQL (prod)
- Entités clés :
  - User
  - Game / Move
  - PvPGame / PvPMove
  - MatchQueueEntry
  - PlayerRating
  - Stats / Feedback

---

### 3.5 Frontend UI & Hooks
- Pages Next.js (App Router)
- Hooks métier :
  - `useSessionUser`
  - `useGomokuGame`
  - `usePvpGame`
  - `useDashboard`

Chaque hook :
- encapsule un **contrat API clair**,
- est **strictement typé**,
- ne contient **aucune règle serveur**.

---

## 4. Flux fonctionnels

### 4.1 Authentification session
1. Frontend appelle `/auth/csrf/`
2. Login/signup via `/auth/login/`
3. Cookies `sessionid` + `csrftoken`
4. `apiFetch` avec `credentials: "include"`

---

### 4.2 Partie contre IA
1. `POST /api/game/start/`
2. Human move → `POST /moves/`
3. AI move → `POST /ai/move/`
4. Backend valide + persiste
5. Frontend affiche l’état

---

### 4.3 Matchmaking PvP
1. User rejoint la queue
2. `try_match()` (transaction atomique)
3. Création `PvPGame`
4. Notification WS `queue.matched`
5. Redirection vers `/pvp/game/[gameId]`

---

### 4.4 Boucle de jeu PvP temps réel
1. REST pour l’action (`POST move`)
2. Validation serveur (tour, cellule, victoire)
3. Persistance DB
4. Broadcast WS (`game.move`, `game.turn`, `game.ended`)
5. Frontend met à jour l’UI

---

## 5. Contrat WebSocket

### Groupes
- Lobby : `pvp_lobby`
- Game : `pvp_game_<id>`

### Événements
```json
{ "type": "queue.matched", "game_id": 12 }
{ "type": "game.move", "move": { "row": 7, "col": 8, "player": "X" } }
{ "type": "game.turn", "turn": "O" }
{ "type": "game.ended", "result": "x_win", "winning_line": [...] }
