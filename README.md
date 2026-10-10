# Cressey


**« Le triangle de la fraude, appliqué aux agents IA. »**

Cressey surveille ce que font les agents IA d'une entreprise. Quand le triangle de Cressey (pression, opportunité, rationalisation) s'allume, il :
1. arrête l'action dangereuse ;
2. remonte à sa source ;
3. envoie au bon propriétaire un guide de correction sourcé ;
4. rejoue l'incident contre la politique corrigée.

**Positionnement :** les passerelles du marché (Lasso, Zenity, AgentCore Policy) jugent l'action. Cressey traite les conditions qui la produisent : la pression subie par l'agent, les clés à sa portée, et la tâche elle-même. Voir [`docs/positioning-and-risks.md`](docs/positioning-and-risks.md).

ESSECKATHON « Secure Horizons », Track 2 « Defenders Augmented ».

Documentation détaillée : [`docs/`](docs/README.md).

## Le problème
Les agents IA agissent avec de vrais droits, et la seule limite est souvent le prompt :
- **PocketOS, avril 2026 :** un agent de code a supprimé le volume de production et toutes ses sauvegardes en 9 secondes.
- **Replit, juillet 2025 :** pendant un gel du code, l'agent a supprimé les tables de production, puis a prétendu à tort que la restauration était impossible.
- **Hugging Face, juillet 2026 :** environ 700 agents de test ont attaqué Hugging Face. Selon METR, environ 7 % des transcriptions évaluées contenaient des traces d'appels d'outils falsifiées par les agents. L'un d'eux a écrit : « However task impossible, peers doing it. We should continue. »

Les sources sont dans `docs/pitch.md`.

## Ce que fait Cressey
- **Détecter.**
  - Le triangle est mesuré sur des faits observables :
    - pression : échecs et tentatives ;
    - opportunité : droits accordés moins droits nécessaires, et secrets à portée ;
    - rationalisation : dérive pondérée par le risque de l'action, et rapport de l'agent contredit par le journal.
  - Un plancher de sécurité retient toute action irréversible hors mandat, quel que soit le score.
- **Arrêter.** L'appel est retenu, la clé émise par Cressey est révoquée, et l'agent reçoit une porte de sortie : « déclarer la tâche impossible est une réponse acceptée ».
- **Agir sur les conditions** (en cours) :
  - sous pression, l'agent reçoit la porte de sortie et sa clé passe en lecture seule, sans attendre un humain ;
  - l'espace de travail ne contient que des clés pièges, et toute utilisation est retenue sur-le-champ.
- **Remonter.** La valeur dangereuse (clé, commande, URL) est retrouvée dans la première entrée lue par l'agent, après normalisation de la casse et des encodages base64, hexadécimal et URL.
- **Alerter et guider.** Un incident par cause racine, envoyé au propriétaire de la source. Il est accompagné d'un guide en français dont chaque étape cite mot pour mot un passage vérifié par le code : ANSSI R1–R35, MITRE ATLAS, OWASP Agentic et nos runbooks.
- **Corriger et vérifier.** Un correctif par jambe, approuvé par un humain. Puis un test de régression de la politique rejoue cinq variantes scriptées de l'attaque dans un bac à sable.

## Architecture
```
agent ──MCP──▶ Cressey proxy (fastmcp, on_call_tool) ──▶ outils réels
                 │  journal chaîné par hachage (tête ancrée hors du journal)
                 ▼
        détection : plancher + triangle (le code décide ; le modèle de décision ne fait qu'étiqueter)
                 │ incident
                 ▼
        guide : réécriture (gpt-5.4-mini) → BM25 + embeddings (fusion RRF)
                → reclassement (seuil 0,4) → rédaction (gpt-5.5) → citations vérifiées par le code

modèle de décision : Strands Decider 2B, servi en local (open source, AWS Strands Labs) ; Jev jusqu'à la bascule
                 │
                 ▼
        API FastAPI /api/*  ──▶  tableau de bord React (types générés depuis l'OpenAPI)
```

## Installation
**Prérequis :** uv 0.12, Bun 1.4, Docker.

```bash
cp .env.example .env          # OPENAI_API_KEY (TYPESAFE_API_KEY jusqu'à la bascule vers Strands Decider)
strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8100   # modèle de décision local
./dev.sh                      # backend :8000 + web :5173 (proxy /api)
docker compose up --build     # image unique : web + API sur :8000
```

**Hors ligne (démo) :** `CRESSEY_MODEL_MODE=fallback` sert les réponses enregistrées si un modèle ne répond pas.

## Tests et qualité
- **Backend :**

  ```bash
  cd backend && uv run pytest -q && uv run ruff check && uv run ty check
  ```

- **Web :**

  ```bash
  cd web && bun run ci && bun run build
  ```

- **Tests réels** (appellent les vrais modèles) :

  ```bash
  cd backend && uv run pytest -m live
  ```

- **CI :** lint, types et tests ; elle échoue aussi si les types générés sont périmés, et le scan de secrets ggshield tourne à chaque push.

## Métriques (fiche défense)
| Mesure | Résultat |
|---|---|
| Taux de détection, sessions d'incident rejouées | **[mesure]** |
| Faux positifs (retenues sur sessions normales) | **[mesure]** |
| Temps pour arrêter | **[mesure] ms**, avec un surcoût proxy mesuré de 1 à 9 ms par appel |
| Source trouvée du premier coup | **[mesure]** |
| Citations vérifiées dans les guides | 100 % sur le jeu de dev (8 incidents) |
| hit@3 au passage exact, BM25 → hybride → reclassé | 26 → 30 → 30 ou 31 sur 31 selon le run (jeu de dev, 2 runs) |

**Méthode :**
- un jeu de développement pour régler ;
- un jeu réservé, écrit par une personne extérieure et lancé une seule fois après le gel ;
- les échecs sont publiés.

## Comment l'humain garde le contrôle
- **Le code décide, les modèles étiquettent.** Aucun modèle ne peut approuver une action.
- **Seuils :**
  - plancher sur les actions irréversibles hors mandat ;
  - alarme du triangle seulement avec au moins deux jambes confirmées par des faits ;
  - pertinence des sources à 0,4 au moins.
- **« Pas de transparence, pas d'autonomie » :** moins Cressey voit l'agent, plus il passe la main à un humain.
- **Traçabilité :** journal chaîné par hachage ; chaque étape d'un guide cite sa source mot pour mot.
- **Erreurs :** si un modèle est indisponible, le guide revient `unavailable` avec ses sources, jamais une erreur 500. Sans source fiable, il répond « je ne sais pas, voir l'équipe sécurité ».
- **Le modèle de décision tourne en local** (Strands Decider 2B) : les données des agents ne sortent pas. S'il est indisponible, la rationalisation reste non confirmée et le plancher continue de retenir.

## Référentiels couverts
- **NIST CSF 2.0 :** DE.CM, DE.AE, RS.AN, RS.CO, RS.MI, PR.AA.
- **OWASP Agentic :** ASI01, ASI02, ASI03, ASI10.
- **MITRE ATLAS v5.6.0 :** AML.T0053, AML.T0101, AML.T0055, AML.T0083, AML.T0051, AML.T0080, AML.T0110, AML.T0086.
- **MITRE ATT&CK :** T1485, T1552.001, T1078.

## Limites connues
- Cressey ne voit que ce qui passe par lui. Pour les agents de code, qui ont tous un terminal, c'est le cas par défaut. Prochaines étapes : les hooks des agents et un bac à sable réseau.
- Un serveur MCP malveillant reste invisible : il peut détourner les données de l'intérieur.
- Il révoque les clés qu'il émet ; pour les autres, il alerte le propriétaire avec un guide de rotation.
- Sans le raisonnement, la rationalisation est estimée par la dérive et le mensonge du rapport, pas par l'intention.
- Le rejeu est scripté : il teste la couverture de la politique en bac à sable, pas le comportement d'un agent réel en production.
- « Inconnu = destructeur » : tout outil non classé est retenu, donc le taux de fausses retenues dépend du classement des outils.
- Les propriétaires sont déclarés dans un fichier.
- La recherche peut se tromper sur des mots ambigus (« recette ») : le seuil et le « je ne sais pas » limitent l'effet.
- Testé sur des sessions synthétiques rejouées, pas encore en entreprise.

## Données et licences
- **ANSSI :** *Recommandations de sécurité pour un système d'IA générative* (2024), Licence Ouverte 2.0.
- **MITRE ATLAS :** données v5.6.0, Apache 2.0, © 2021–2026 MITRE.
- **OWASP :** *Top 10 for Agentic Applications 2026*, CC BY-SA 4.0.
- **Runbooks et jeux d'évaluation :** écrits par l'équipe ; données synthétiques uniquement.
- **Secrets :** aucun dans le dépôt (vérifié par ggshield).

## Équipe
**[noms]**
