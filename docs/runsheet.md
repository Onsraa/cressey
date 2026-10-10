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
| 1 | **Switch to Strands Decider 2B** | A (judge), B (re-ranker and eval) | 2–3 h | **Closed 10-10: Jev stays for both.** The triangle by S9, the re-ranking by the guide eval (Strands Decider 3/8 guides, Rerank 3.5 on Bedrock 6/8, Jev 8/8). Left: re-record the judge cache (`decisions.md`, Open) |
| 2 | **Ablation:** run the detection eval with the triangle off, then on | B | ~1 h | **Done 10-10:** `report-ablation.json`. No difference on the shipped sessions (5/5 and 0/5 both ways), so item 5 decides whether the triangle adds detections |
| 3 | **Act on pressure:** when pressure is confirmed, the way out goes in the next tool result and the run key drops to read-only | A | 1–1.5 h | A test shows the drop and the message. The gauge shows « porte de sortie envoyée » |
| 4 | **Trap keys:** decoy keys in the workspace; any use is held at once and traced | A | ~1 h | **Done 10-10:** `variant-cle-piege` reads the admin key, a trap key, and checks it with a `SELECT` the floor's other rules let through. It's held as « critique », traced to the read at step 3 (`tests/core/test_trap_keys.py`) |
| 5 | **Scenario only the triangle catches:** the tests are weakened under a deadline; drift is asked against the spec | A + B | ~1 h | Held by the triangle with the floor off; free with the triangle off |
| 6 | **Measure the decision model:** about 30 labelled actions, the attack on our own judge, latency per 1,000 calls | B | ~1.5 h | Numbers in `evaluation.md` |
| 7 | **Dashboard:** the new events (way out, read-only, trap key) and the Évaluation view | A + B | — | As in `dashboard.md` |
| 8 | **Second way in: Claude Code hook**, after the 21:30 go/no-go, before the other stretch goals: `POST /hook/claude` on the same decision as the proxy, `http` hooks in the demo workspace's `.claude/settings.json`, `Bash`, `Edit`, `Write` and `Read` in `policy.yaml`, the « Brancher un agent » card and the « via MCP / via hook » badge | A | 2–3 h (estimate) | A real Claude Code session has its test edit held and shown in the Run view. The video of it is recorded |
| — | Open decision: **live runs** with gpt-5.4-mini (10 without Cressey, 10 with) | — | 1–2 h | Only if decided |

**To try Strands Decider again:** serve it (`strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8100 --device mlx`), set `CRESSEY_DECIDER_URL=http://127.0.0.1:8100`, then record the cache again.

**Kept cut:** S3 Object Lock, the owner MCP connector, Slack, and the Blue Team challenge, unless the 21:30 go/no-go passes with time to spare. The Claude Code hook (item 8) comes first among the stretch goals.

**Local only (10-10):** everything runs on the stage Mac. No AWS deploy. Cut for the event, kept for the roadmap slide: the AWS deploy, a Claude Code plugin, an `npx` installer, other agents' hooks, a `base_url` gateway and framework middleware.

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
  - modèles : Jev (décisions typées avec confiance), gpt-5.5 et gpt-5.4-mini, recherche hybride BM25 et text-embedding-3-small ; Strands Decider 2B et Cohere Rerank 3.5 (Bedrock) mesurés, moins bons ;
  - web : React, Vite, Tailwind et shadcn ;
  - livraison : Docker, CI avec ggshield.

## If something breaks
| Problem | Fix |
|---|---|
| The venue Wi-Fi goes down | Switch to the 4G hotspot. If the models don't answer, `CRESSEY_MODEL_MODE=fallback` serves the recorded guides |
| A model API is down | Same: fallback mode. A guide comes back `unavailable` with its sources, never a crash |
| The live demo crashes | Play the 2–3 minute video. Prepare it before 09:30 |
| Claude Code can't reach its model on stage | Play the recorded hook beat. The main demo is the scripted replay and doesn't need it |
| A laptop fails | The second laptop has the repo cloned and the image built (`docker compose up`) |
| A piece of code is stopped by the assistant | Write it down, move to the next task, and write that piece by hand |
| Track 2 is full | Ask the organisers before 18:30, and have the reasons for Track 2 ready |
