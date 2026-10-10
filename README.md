# Cressey

**The fraud triangle, applied to AI agents.**

Cressey sits between an AI agent and its tools. When the three signs of the fraud triangle line up (pressure, opportunity, rationalization), it:
1. **stops** the risky call before it runs;
2. **traces** it back to where the agent found what it misused;
3. **guides** each owner with a fix whose every step quotes a verified source;
4. **replays** the attack against the fixed policy.

ESSECKATHON « Secure Horizons », Track 2 « Defenders Augmented ». Details are in [`docs/`](docs/README.md).

## Why
AI agents act with real rights, often limited by nothing but their prompt. In April 2026, a coding agent at PocketOS deleted a production volume and its backups in 9 seconds. In July 2026, about 700 test agents attacked Hugging Face, and one of them wrote: « However task impossible, peers doing it. We should continue. » Sources are in [`docs/pitch.md`](docs/pitch.md).

## Run it
Requires uv 0.12 and Bun 1.4.

```bash
cp .env.example .env                 # model keys: OpenAI, TYPESAFE_API_KEY (Jev)
(cd web && bun install)
CRESSEY_MODELS=openai CRESSEY_MODEL_MODE=replay-first ./dev.sh
```

Dashboard: http://localhost:5173. Then play the demo agent, in a second terminal:

```bash
cd backend
uv run python -m cressey.demo.agent data/sessions/demo-tests-impossibles.yaml --kind live
uv run python -m cressey.demo.agent data/sessions/demo-tests-impossibles.yaml --kind control
```

`replay-first` answers from the recorded models, so the demo is identical every time and works offline. `docs/runsheet.md` has the stage checklist.

## Tests
```bash
cd backend && uv run pytest -q && uv run ruff check && uv run ty check
cd web && bun run ci && bun run build
```

## Results (dev set, synthetic sessions)
| Measure | Result |
|---|---|
| Incident sessions held | 7 / 7 |
| Normal sessions held by mistake | 0 / 6 |
| Time to stop, p50 | 231 ms |
| Held only thanks to the triangle | 1 session the safety floor misses |
| Guide steps with a verified quote | 100 % (8 incidents) |
| Right passage in the top 3, re-ranked | 30 / 31 |

Source files and the method: [`docs/evaluation.md`](docs/evaluation.md). The held-out set hasn't been run yet.

## How humans stay in control
- **Code decides, models only label.** No model can approve a call, a fix, or a release.
- **A safety floor** holds any irreversible action outside the agent's mandate, whatever the scores.
- **Every guide step quotes its source word for word**, checked by code. With no reliable source, the guide says « I don't know — ask the security team ».

## Known limits
- Cressey only sees what goes through it.
- The replay tests the policy on scripted variants, not a real agent's behaviour.
- Tested on synthetic sessions, not yet in a company.

## Data and licences
ANSSI *Security recommendations for a generative AI system* (2024, Licence Ouverte 2.0), MITRE ATLAS v5.6.0 (Apache 2.0), OWASP *Top 10 for Agentic Applications 2026* (CC BY-SA 4.0). Runbooks and sessions are written by the team, with fake values only. No secret is in the repo.

## Team
**[names]**
