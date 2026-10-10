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

## Re-plan after the 10-10 review (from Saturday about 14:30)
The guide pipeline, the proxy with floor and holds, the triangle, the incidents and the detection eval are built. Remaining work, in order (why: `positioning-and-risks.md`; what to measure: `evaluation.md`):

| # | Task | Who | Estimate | Done when |
|---|---|---|---|---|
| 1 | **Switch to Strands Decider 2B.** See the steps below | A (judge), B (re-ranker and eval) | 2–3 h | The demo path, detection eval and guide eval all pass with Strands, with the cache re-recorded |
| 2 | **Ablation:** run the detection eval with the triangle off, then on | B | ~1 h | Both reports written, with n/N |
| 3 | **Act on pressure:** when pressure is confirmed, the way out goes in the next tool result and the run key drops to read-only | A | 1–1.5 h | A test shows the drop and the message. The gauge shows « porte de sortie envoyée » |
| 4 | **Trap keys:** decoy keys in the workspace; any use is held at once and traced | A | ~1 h | A session using the decoy is held with severity « critique » |
| 5 | **Scenario only the triangle catches:** the tests are weakened under a deadline; drift is asked against the spec | A + B | ~1 h | Held by the triangle with the floor off; free with the triangle off |
| 6 | **Measure the decision model:** about 30 labelled actions, the attack on our own judge, latency per 1,000 calls | B | ~1.5 h | Numbers in `evaluation.md` |
| 7 | **Dashboard:** the new events (way out, read-only, trap key) and the Évaluation view | A + B | — | As in `dashboard.md` |
| — | Open decision: **live runs** with gpt-5.4-mini (10 without Cressey, 10 with) | — | 1–2 h | Only if decided |

**Strands Decider switch, steps:**
1. Install it on the stage Mac: `pip install strands-decider`. For MLX, install from a clone with `pip install -e ".[mlx]"`.
2. Serve it: `strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8100`. Port 8000 is the backend.
3. Check: one `noul` call answers with `model` and `latency_ms`.
4. Try `typesafe-sdk` against it through its base URL. If the formats differ, write a small client for `/v1/systemone` behind the same interface in `core/judge.py` and `guide/clients.py`.
5. Re-run the S2 check (typo fix: read, edit, `run_tests`, DROP) and the demo path. Set the drift threshold (0.5) again.
6. Re-run the guide eval (`--split dev`) and set the relevance threshold (0.4) again, using the S6 method.
7. Re-record the cache (judge and re-ranker), then run once with the Wi-Fi off.
8. Drop `TYPESAFE_API_KEY` from `.env.example` and the README once nothing uses it.

**If the switch isn't done by 21:30,** keep Jev for the demo and present Strands Decider as the target, with the numbers measured so far.

**Kept cut:** S3 Object Lock, the owner MCP connector, Slack, and the Blue Team challenge, unless the 21:30 go/no-go passes with time to spare.

## Sunday
| Time | A | B |
|---|---|---|
| **06:00** | **Freeze** the detector and the prompts. Record the demo cache (Task 8). Run the held-out sets **once** | Write the measured numbers down honestly, misses included |
| 06:00–09:30 | 2–3 minute demo video; check that the README matches the code (decision model, commands) | Fiche défense; fill the **[mesure]** numbers into the deck |
| 09:30 | Pitch coaching workshop | Same |
| 10:30–12:00 | Test with the **Wi-Fi off** (`CRESSEY_MODEL_MODE=fallback`); last commit | `ggshield secret scan repo .`; rehearse 5 minutes and 3 minutes |
| **12:00** | **Firm deadline**: repo, video, deck (8 slides), fiche défense, plus the Track 2 deliverables: a PoC on a realistic flow, defensive metrics, and the « comment l'humain garde le contrôle » section | Same |
| 13:00 | Round 1: 5 minutes of pitch plus 2 of questions | Same |
| 15:00 / 15:25 | Finalists announced; final at 3 minutes plus 3 of questions | Same |

## Answers ready for the 18:30 checkpoint
- **Problème :** Les agents IA d'entreprise agissent avec de vrais droits, et la seule limite est souvent le prompt. Un agent a supprimé la base de production de PocketOS et ses sauvegardes en 9 secondes. Lors de l'incident Hugging Face, des agents ont falsifié leurs propres journaux. Personne ne voit pourquoi un agent dérape, ni comment corriger la cause.
- **Défenseur aidé :** le SOC et les équipes plateforme qui déploient des agents.
- **Solution :** Les passerelles du marché jugent l'action ; Cressey traite les conditions qui la produisent, avec le triangle de la fraude (pression, opportunité, rationalisation). Branché en une ligne comme proxy MCP, il retient les actions irréversibles hors mandat. Sous pression, il offre une porte de sortie à l'agent et réduit ses droits. Il remonte à la source et envoie à chaque propriétaire, y compris l'auteur de la tâche, un guide de correction sourcé (ANSSI, MITRE ATLAS, OWASP).
- **Stack :**
  - Python : FastAPI et Pydantic, proxy fastmcp ;
  - modèles : Strands Decider 2B en local (décisions typées avec confiance, open source, AWS), gpt-5.5 et gpt-5.4-mini, recherche hybride BM25 et text-embedding-3-small ;
  - web : React, Vite, Tailwind et shadcn ;
  - livraison : Docker, CI avec ggshield.

## If something breaks
| Problem | Fix |
|---|---|
| The venue Wi-Fi goes down | Switch to the 4G hotspot. If the models don't answer, `CRESSEY_MODEL_MODE=fallback` serves the recorded guides |
| A model API is down | Same: fallback mode. A guide comes back `unavailable` with its sources, never a crash |
| The local Strands Decider server is down or too slow | Restart `strands-decider serve`. Meanwhile rationalization shows « indisponible » and the floor keeps holding. Fallback mode serves the recorded labels |
| The live demo crashes | Play the 2–3 minute video. Prepare it before 09:30 |
| A laptop fails | The second laptop has the repo cloned and the image built (`docker compose up`) |
| A piece of code is stopped by the assistant | Write it down, move to the next task, and write that piece by hand |
| Track 2 is full | Ask the organisers before 18:30, and have the reasons for Track 2 ready |
