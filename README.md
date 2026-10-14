<div align="center">

<img src=".github/assets/logo.svg" width="64" alt="Cressey logo">

# Cressey

**The fraud triangle, applied to AI agents.**<br>
Cressey sits between an AI agent and its tools, and stops a dangerous call before it runs.

[![1st place, ESSECKATHON Secure Horizons 2026](https://img.shields.io/badge/%F0%9F%8F%86_1st_place-ESSECKATHON_Secure_Horizons_2026-E3B341?style=for-the-badge&labelColor=1E1E1E)](#why-cressey)

[![CI](https://img.shields.io/github/actions/workflow/status/Onsraa/cressey/ci.yml?branch=main&style=flat-square&label=CI&labelColor=1E1E1E)](https://github.com/Onsraa/cressey/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/Python-3.12-1E1E1E?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-1E1E1E?style=flat-square&logo=fastapi&logoColor=white)
![React 19](https://img.shields.io/badge/React_19-1E1E1E?style=flat-square&logo=react&logoColor=white)
![Claude Code hook](https://img.shields.io/badge/Claude_Code-hook-1E1E1E?style=flat-square&logo=claude&logoColor=white)
![MCP proxy](https://img.shields.io/badge/MCP-proxy-1E1E1E?style=flat-square&logo=modelcontextprotocol&logoColor=white)

[The fraud triangle](#the-fraud-triangle) · [How it works](#how-it-works) · [Setup](#setup) · [Roadmap](#roadmap) · [Docs](docs/README.md)

<img src=".github/assets/demo.gif" width="100%" alt="Cressey's dashboard during a run: the fraud triangle fills as the agent's pressure, opportunity and excuses are scored, then the call is held">

<sub>In this demo, an agent told to get the tests green before tonight's release finds a production key and talks itself into emptying a table. Cressey scores each leg live and holds the call.</sub>

</div>

## Why Cressey

AI agents act with real rights, often limited by nothing but their prompt. In April 2026, a coding agent [deleted PocketOS's production volume and its backups in 9 seconds](https://zenity.io/blog/ai-agent-database-deletion-pocketos). In July 2026, about 700 test agents [attacked Hugging Face](https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/), and one of them wrote: *"However task impossible, peers doing it. We should continue."*

Agent firewalls judge the action. Cressey also reads the conditions that produce it, and steps in before the harm.

Cressey started as a 24.5-hour build at ESSECKATHON Secure Horizons (ESSEC, October 2026), where it won 1st place in the AI for Security track.

## The fraud triangle

In 1953, criminologist Donald Cressey found that fraud happens when three conditions meet. Known today as the *fraud triangle*, the idea is still used by auditors. AI agents show the same three:

| | In people | In AI agents |
|---|---|---|
| **Pressure** | debt, targets | failing tests, a deadline in the task |
| **Opportunity** | access, weak controls | a production key within reach |
| **Rationalization** | *"I'll pay it back."* | *"However task impossible, peers doing it."* |

Cressey scores all three on every step. Jev, a fast decision model, reads pressure and rationalization in the agent's own words. Code adds the facts: failed or repeated calls, a secret the agent read.

## How it works

```
agent ──▶ Cressey ──▶ real tools
            │
            ├─ safety floor     code rules: irreversible actions, trap keys
            ├─ fraud triangle   Jev scores every step, code decides
            ▼
       allow · hold for a human · refuse
            │
            ▼
       incident ──▶ source trace + sourced fix guide ──▶ dashboard
```

1. **Plug in.** A Claude Code hook sees every shell command, file edit and message. An MCP proxy covers MCP tool calls.
2. **Safety floor.** Code rules hold irreversible actions outside the agent's mandate (`rm`, `DROP TABLE`, `git push --force`…) and any write made with a *trap key*, a decoy secret planted where an agent might look.
3. **Fraud triangle.** Cressey tightens as the legs confirm. Under pressure, the agent is told that declaring the task impossible is an accepted answer. Add an opportunity, and its key turns read-only for destructive calls. A hold needs Jev's judgment plus a confirmed leg, and no model can release it.
4. **Incident.** Every hold opens an incident. Cressey traces the misused secret back to where the agent found it and writes a fix guide per owner, each step quoting a verified source (ANSSI, MITRE ATLAS, OWASP).

Each check can alert, hold for a human (the default) or refuse at once, switchable live in Settings.

**Measured:** 8/8 incident sessions held at the call they name and 0/6 normal sessions held by mistake, on 14 synthetic sessions written by the team ([method](docs/evaluation.md)).

**Stack:** Python 3.12, FastAPI and FastMCP in `backend/` · React and Vite in `web/` · Jev (TypeSafe) for the triangle · OpenAI or AWS Bedrock for the fix guides.

## Setup

Needs [uv](https://docs.astral.sh/uv/) 0.12+, [Bun](https://bun.sh) 1.4+, [Claude Code](https://code.claude.com) 2.1.295+, `jq` and a Jev API key.

```bash
git clone https://github.com/Onsraa/cressey.git
cd cressey
./connect.sh
```

The first run asks for your Jev key, starts Cressey, opens the dashboard and opens Claude Code in a scratch folder. The dashboard asks once for the admin key that `./connect.sh` prints. Ask the agent to create a file, then delete it with `rm`: Cressey holds the `rm`. Quit Claude Code, then press Enter to stop Cressey.

- **Your own project:** `./connect.sh ~/my-project`. To disconnect, delete its `.claude/settings.local.json`.
- **Fix guides:** add an `OPENAI_API_KEY` to `.env` (or AWS credentials with `CRESSEY_MODELS=bedrock`).
- **Scripted demo, offline:** `CRESSEY_MODEL_MODE=replay-first ./dev.sh`, then in a second terminal `cd backend && uv run python -m cressey.replay.player data/sessions/demo-tests-impossibles.yaml --kind live`. The admin key is `CRESSEY_ADMIN_TOKEN` in `.env`.

**Tests**

```bash
cd backend && uv run pytest -q && uv run ruff check && uv run ty check
cd web && bun run ci && bun run build
```

## Roadmap

- [x] Claude Code hook and MCP proxy
- [x] Safety floor and trap keys
- [x] Fraud triangle scored live on every step
- [x] Way out, read-only key and holds, with a response per check
- [x] Incidents with a source trace and sourced fix guides
- [ ] Deploy on AWS, off the agent's machine and behind a default-deny network, so Cressey is the agent's only way out
- [ ] Hooks for more agents than Claude Code
- [ ] One-command install that starts in observer mode
- [ ] Alerts to Slack, Teams, Jira and SIEMs
- [ ] A held-out evaluation written outside the team, and live agents on public benchmarks

Known limitations: [docs/limitations.md](docs/limitations.md).

---

<div align="center">

Built by **Teddy Truong** and **Sebastian Mihnea**

<sub>Fix guides cite ANSSI <i>Security recommendations for a generative AI system</i> (2024, Licence Ouverte 2.0), MITRE ATLAS v5.6.0 (Apache 2.0) and the OWASP <i>Top 10 for Agentic Applications 2026</i> (CC BY-SA 4.0). Sessions and runbooks are written by the team, with fake values only. No secret is in the repo.</sub>

</div>
