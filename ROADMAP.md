# ROADMAP.md — HvM (Human vs Machine)

## 1. Vision produit

### Mission

Faire de **HvM** la référence du **jeu cognitif compétitif** en temps réel, où l’humain se mesure à l’IA et à d’autres joueurs, dans un environnement fiable, mesurable et stimulant.

### Proposition de valeur

* Jeu **simple à comprendre**, **difficile à maîtriser**
* Confrontation **Humain vs IA** et **Humain vs Humain**
* Progression mesurable (ELO, stats, historique)
* Expérience temps réel fluide et juste (backend autoritaire)

### Positionnement marché

* À l’intersection de :

  * Jeux de réflexion (chess, gomoku, go)
  * Compétition PvP en ligne
  * IA appliquée au grand public
* Cible :

  * joueurs cognitifs
  * étudiants / professionnels
  * amateurs de compétition et d’IA

---

## 2. Phases d’évolution produit

### Phase 0 — Stabilisation V2 (actuelle)

**Objectif : produit techniquement fiable**

Priorités :

* Corriger bugs d’intégration
* Stabiliser PvP temps réel
* Verrouiller sécurité et typage
* Zéro régression

---

### Phase 1 — Lancement public (MVP SaaS)

**Objectif : ouvrir HvM au public**

Focus :

* onboarding simple
* PvP stable
* expérience utilisateur claire
* premières métriques d’usage

---

### Phase 2 — Croissance produit

**Objectif : engagement, rétention, profondeur**

Focus :

* compétition structurée
* profils joueurs riches
* social léger
* amélioration UX

---

### Phase 3 — Monétisation avancée

**Objectif : revenus récurrents**

Focus :

* premium
* compétitif payant
* features IA différenciantes

---

### Phase 4 — Scalabilité globale

**Objectif : plateforme SaaS mondiale**

Focus :

* infra cloud
* multi-régions
* performance temps réel
* extension produit

---

## 3. Fonctionnalités clés par phase

### Phase 0 — Stabilisation V2

* PvP matchmaking fiable
* Détection victoire serveur (`winning_line`)
* WebSocket robuste (fallback REST)
* Dashboard cohérent
* Admin analytics sécurisé
* Typage strict frontend (0 `any`)

---

### Phase 1 — MVP SaaS

* PvP public
* Profils utilisateurs basiques
* Historique des parties
* Dashboard personnel
* Feedback utilisateur intégré
* Déploiement public

---

### Phase 2 — Croissance produit

* **Ranked PvP + ELO**
* Rematch après partie
* Spectateurs (read-only)
* Badges & streaks
* Statistiques avancées
* UX compétitive (animations, feedback visuel)

---

### Phase 3 — Monétisation

* Freemium / Premium
* IA avancée (depth, analysis, replay)
* Tournois payants
* Skins / personnalisation
* Abonnements mensuels

---

### Phase 4 — Scalabilité & expansion

* Mobile (React Native / PWA)
* Tournois globaux
* Classements mondiaux
* Multi-jeux cognitifs
* API publique HvM

---

## 4. Stratégie de monétisation

### Modèle Freemium

* Gratuit :

  * PvP casual
  * IA standard
* Premium :

  * Ranked
  * IA avancée
  * Stats détaillées
  * Replays

### Revenus complémentaires

* Tournois payants
* Skins / cosmétiques
* Features IA premium
* Abonnements entreprise / éducatif

---

## 5. Stratégie de croissance

### Acquisition

* PvP viral (inviter un ami)
* Classements partageables
* Contenu compétitif (replays)

### Rétention

* Ranked + ELO
* Streaks
* Badges
* Progression visible

### Expansion

* Internationalisation rapide
* Communautés locales
* Partenariats éducatifs

---

## 6. Architecture & scalabilité produit

### Court terme

* SQLite → Postgres
* Redis obligatoire (Channels)
* Séparation services claire

### Moyen terme

* Hébergement cloud (Docker)
* Workers asynchrones
* Cache lecture stats

### Long terme

* Multi-régions
* Sharding matchmaking
* WebSocket scale horizontal

---

## 7. Indicateurs clés (KPIs SaaS)

### Usage

* DAU / MAU
* Nombre de parties / jour
* Durée moyenne d’un match

### Engagement

* Rétention J1 / J7 / J30
* % joueurs PvP
* % ranked vs casual

### Business

* Conversion premium
* ARPU
* Churn

---

## 8. Jalons temporels

### 0–3 mois

* Stabilisation V2
* PvP public
* Dashboard fiable

### 3–6 mois

* Ranked + ELO
* Profils avancés
* Début monétisation

### 6–12 mois

* Tournois
* Mobile
* Croissance internationale

### 12–24 mois

* Multi-jeux
* API publique
* e-sport cognitif

---

## 9. Vision long terme

HvM devient :

* une **plateforme de jeux cognitifs compétitifs**
* une **arena d’entraînement IA / humain**
* un **écosystème SaaS temps réel**
* un produit prêt pour :

  * pré-seed
  * seed
  * partenariats stratégiques

**HvM = intelligence, compétition, temps réel.**
