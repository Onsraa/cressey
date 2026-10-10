# Cressey: event run sheet (Saturday 10 and Sunday 11 October 2026)

There are two of us: **A** handles the setup, the core loop and the demo; **B** handles the guides, the RAG, the evaluation and the fiche défense.

The plans:
- `plan-setup.md` (part 3);
- `plan-guide-rag.md` (part 1).

The core loop and the dashboard follow `concept.md`, one piece at a time.

## Friday evening (no product code)
- [ ] Laptops charged, with chargers and a power strip. A 4G hotspot tested.
- [ ] Keys stored in a password manager, never on a USB stick: OpenAI, TypeSafe, and GitGuardian if you have it.
- [ ] Pull the Docker base images, so we don't depend on the venue Wi-Fi: `docker pull python:3.12-slim oven/bun:1.4 ghcr.io/astral-sh/uv:0.12`.
- [ ] Data ready in `cressey/data/`:
  - the reference documents;
  - 6 runbooks;
  - `SOURCES.json`;
  - the eval sets;
  - `owasp_asi.json`, once the PDF is downloaded;
  - the held-out questions written by an outsider.
- [ ] The synthetic sessions that the demo agent replays: incidents and normal sessions, written by the team.
- [ ] Rehearse the pitch once (`pitch.md`).

## Saturday
| Time | A | B |
|---|---|---|
| 10:00 | Kickoff in the Grand Amphi. Note the datasets they announce, and whether places on Track 2 are capped | Same |
| 10:50–11:30 | Team formation: confirm **Track 2** on the form | Same |
| 11:30–12:00 | Setup Task 1 (repo), then **Task 2** (backend). B needs Task 2 | Copy `cressey/data/` to `backend/data/` once Task 2 is pushed |
| 12:00–14:00 | Setup Tasks 3–5: web, typed contract, `./dev.sh` | Guide Tasks 1–3: types and quotes, corpus, hybrid search |
| 14:00–18:30 | Core loop, first piece (from `concept.md`): MCP proxy, mandate and safety floor, hold | Guide Tasks 4–5: adapters, pipeline. Optionally the Utopia workshop « copilote SOC fiable » (30 min) |
| **18:30** | **Checkpoint form**: paste the answers below (10 min) | Same |
| 18:30–22:00 | Core loop: triangle scoring, tracing the source, creating the incident (handed over as `GuideIncident`) | Guide Task 6 (API) and **Task 8 (offline cache)**. First dashboard piece: the guide page |
| 22:00 | **Blue Team challenge: go only if the demo path (detect → stop → guide) runs end to end by 21:30.** Otherwise skip it | Same |
| 22:00–02:00 | Replay, dashboard (gauges, timeline), loading the synthetic sessions | Dashboard: inboxes and « Pourquoi ? ». Setup Tasks 6–7 (Docker, CI) |
| 02:00–06:00 | Sleep in shifts (3 hours each). Hardening | Guide Task 7: eval on the dev set |

## Sunday
| Time | A | B |
|---|---|---|
| **06:00** | **Freeze** the detector and the prompts. Record the demo cache (Task 8). Run the held-out sets **once** | Write the measured numbers down honestly, misses included |
| 06:00–09:30 | 2–3 minute demo video; README (draft in `README-hackathon.md`) | Fiche défense; fill the **[mesure]** numbers into the deck |
| 09:30 | Pitch coaching workshop | Same |
| 10:30–12:00 | Test with the **Wi-Fi off** (`CRESSEY_MODEL_MODE=fallback`); last commit | `ggshield secret scan repo .`; rehearse 5 minutes and 3 minutes |
| **12:00** | **Firm deadline**: repo, video, deck (8 slides), fiche défense, plus the Track 2 deliverables: a PoC on a realistic flow, defensive metrics, and the « comment l'humain garde le contrôle » section | Same |
| 13:00 | Round 1: 5 minutes of pitch plus 2 of questions | Same |
| 15:00 / 15:25 | Finalists announced; final at 3 minutes plus 3 of questions | Same |

## Answers ready for the 18:30 checkpoint
- **Problème :** Les agents IA d'entreprise agissent avec de vrais droits, et la seule limite est souvent le prompt. Un agent a supprimé la base de production de PocketOS et ses sauvegardes en 9 secondes. Lors de l'incident Hugging Face, des agents ont falsifié leurs propres journaux. Personne ne voit pourquoi un agent dérape, ni comment corriger la cause.
- **Défenseur aidé :** le SOC et les équipes plateforme qui déploient des agents.
- **Solution :** Cressey applique le triangle de la fraude (pression, opportunité, rationalisation) aux agents. Branché en une ligne comme proxy MCP, il arrête l'action dangereuse et remonte à sa source. Il envoie au bon propriétaire un guide de correction sourcé (ANSSI, MITRE ATLAS, OWASP) et prouve la correction en rejouant l'incident.
- **Stack :**
  - Python : FastAPI et Pydantic, proxy fastmcp ;
  - modèles : Jev (décisions typées avec confiance), gpt-5.5 et gpt-5.4-mini, recherche hybride BM25 et text-embedding-3-small ;
  - web : React, Vite, Tailwind et shadcn ;
  - livraison : Docker, CI avec ggshield.

## If something breaks
| Problem | Fix |
|---|---|
| The venue Wi-Fi goes down | Switch to the 4G hotspot. If the models don't answer, `CRESSEY_MODEL_MODE=fallback` serves the recorded guides |
| A model API is down | Same: fallback mode. A guide comes back `unavailable` with its sources, never a crash |
| The live demo crashes | Play the 2–3 minute video. Prepare it before 09:30 |
| A laptop fails | The second laptop has the repo cloned and the image built (`docker compose up`) |
| A piece of code is stopped by the assistant | Write it down, move to the next task, and write that piece by hand |
| Track 2 is full | Ask the organisers before 18:30, and have the reasons for Track 2 ready |
