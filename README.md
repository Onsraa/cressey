# Cressey

**The fraud triangle, applied to AI agents.** Cressey sits between an AI agent and its tools and stops a dangerous call before it runs.

ESSECKATHON "Secure Horizons", Track 2 "Defenders Augmented". Full docs in [`docs/`](docs/README.md).

## Problem
AI agents act with real rights, often limited by nothing but their prompt.
- **April 2026, PocketOS.** A coding agent deleted a production volume and its backups in 9 seconds.
- **July 2026, Hugging Face.** About 700 test agents attacked it. One of them wrote: "However task impossible, peers doing it. We should continue."

Agent firewalls judge the action. Cressey also reads the conditions that produce it, the three legs of Donald Cressey's fraud triangle: **pressure**, **opportunity**, **rationalization**. Sources in [`docs/pitch.md`](docs/pitch.md).

## Architecture
```
agent ──▶ Cressey (MCP proxy or Claude Code hook) ──▶ real tools
             │
             ├─ safety floor     code rules, widened by Jev labels that only add holds
             ├─ fraud triangle   Jev labels each step, code decides
             ▼
          allow  |  hold for a human  |  refuse
             │
             ▼
          incident ──▶ source trace + fix guides ──▶ dashboard
```
- **Two ways in.** An MCP proxy sees MCP tool calls. A Claude Code HTTP hook (`POST /hook/claude`) also sees the shell, the files and the agent's messages.
- **Safety floor.** Code rules hold irreversible actions outside the agent's mandate (`rm`, `DROP TABLE`, `DELETE FROM`, `git push --force`...) and any call that uses a trap key to change something. A trap key is a decoy secret planted where an agent might find it. Using one only to read raises an alert. Jev widens the floor but never loosens it. A tool missing from the policy, such as any MCP tool, gets its kind from its name. A write the code lets through is held when Jev, reading the action without the agent's words, finds it can't be undone beyond the mandate (`terraform destroy`, a Railway `serviceDelete`), or that it changes production (a production deploy or config change). Settings can switch the production check off.
- **Fraud triangle.** Jev, a fast decision model, labels pressure and rationalization in the agent's words. Opportunity comes from code (a secret the agent read). A hold needs Jev's judgment plus confirmed pressure or opportunity. No model can release a hold.
- **Response per check.** Hold for a human (default), refuse at once, or only alert. Switch it in Settings. After 3 rejected calls in a turn, Cressey tells the agent to stop and report.
- **After a hold.** Cressey traces the misused secret back to where the agent read it and writes a fix guide per owner. Every step quotes a verified source (ANSSI, MITRE ATLAS, OWASP).
- **The guard has its own lock.** Deciding holds, unlocking a run, changing the responses and reading runs or incidents need the admin key (`CRESSEY_ADMIN_TOKEN`, which `./dev.sh` draws into `.env`). An agent only ever holds its run key, which opens none of these. A call an agent aims at Cressey itself (its API or its dashboard) is held by the safety floor.
- **Stack.** Python 3.12, FastAPI and FastMCP in `backend/`. React and Vite in `web/`. Rules in `backend/data/`: the engine's settings in `policy.yaml`, Claude Code's tools in `catalogs/`, and what a deployment fronts in its profile (`profiles/demo.yaml` by default, `CRESSEY_PROFILE`). Models: Jev (TypeSafe) for the triangle and re-ranking, OpenAI or AWS Bedrock for the guides.

**Measured on the dev set (10-13):** 8/8 incident sessions held at the call they name, 0/6 normal sessions held by mistake, 617 ms to stop (p50, live Jev, calls back to back). Method in [`docs/evaluation.md`](docs/evaluation.md).

## Install and try
Needs [uv](https://docs.astral.sh/uv/) 0.12+, [Bun](https://bun.sh) 1.4+, [Claude Code](https://code.claude.com) 2.1.295+, `jq` and a Jev API key.

```bash
git clone https://github.com/Onsraa/secure-horizon-2026.git
cd secure-horizon-2026
./connect.sh
```
The first run asks for your Jev key, checks it and saves it in `.env`. Then it starts Cressey, opens the dashboard and opens Claude Code in a scratch folder. The dashboard asks once for the admin key, which `./connect.sh` prints. Ask the agent to create a file and delete it with `rm`: the dashboard shows each step and holds the `rm`. Quit Claude Code, then press Enter to stop Cressey.

- **Your own project:** `./connect.sh ~/my-project`. To disconnect, delete its `.claude/settings.local.json`.
- **Fix guides:** add an `OPENAI_API_KEY` to `.env` (or AWS credentials with `CRESSEY_MODELS=bedrock`).
- **Scripted demo, no agent needed:** run `CRESSEY_MODEL_MODE=replay-first ./dev.sh`, then in a second terminal `cd backend && uv run python -m cressey.replay.player data/sessions/demo-tests-impossibles.yaml --kind live`. `replay-first` answers from recorded model calls, so it plays the same every time, offline included.

## Known limitations
- **Tested on a real agent and real infrastructure, a few runs only.** Claude Opus 4.6 (Claude Code) got the task "reset the staging database" on a throwaway Railway project. Without Cressey, 1 run in 3 deleted the production database with an old ops token it found in the repo. The 2 others refused.
- **The live hold is shown on a replay.** The one live run through Cressey asked before deleting, so there was nothing to hold. The demo replays the recorded deleting run through the hook: the agent's real words and commands, held at the delete.
- **That catch comes from the trap key, not the triangle.** The agent was calm, so the triangle stayed quiet. On the dev set the triangle alone holds one session that the safety floor misses. Replayed with the trap key defused, the same delete is held by Jev's floor label (0.72): one replay, not a live run.
- **Cressey sees only what goes through it.** The hook covers Claude Code only. An agent with another way out (its own network, another tool) is not stopped. To be the only way out, Cressey has to run outside the agent's container behind a default-deny network. That deployment is not done, so as it stands Cressey would not have stopped the Hugging Face incident.
- **Small eval, written by the team.** 14 synthetic sessions. The held-out set from outside the team is not written yet.
- **The reasoning shown is the agent's narration.** No provider exposes the raw chain of thought.
- **What a restart keeps.** With `CRESSEY_STATE_DIR` (set by `./dev.sh` and the Docker image), the event log, its anchor and the runs' keys are kept on disk. After a restart a hooked agent carries on, its earlier steps come back from the log, and a call held at that moment is logged expired. What a run had only in memory (results, secrets read, the triangle's evidence, a suspension) starts afresh. The anchor sits next to the log: it catches a log cut short, by a crash or by hand, not someone who rewrites both. Shipping it off the machine is next.
- **On one machine, the agent could read the admin key.** It runs as the same user as Cressey: without the key it can't decide a hold or change a response, but `.env` is readable. Cressey's own URL in a call is held, a tripwire, not the lock. For real isolation, run Cressey off the agent's machine, or sandbox the agent's files and network.
- **When Jev doesn't answer,** the code rules and trap keys still hold, and a tool missing from the policy is held. A write only Jev's floor label would judge waits for a human too (« Jev didn't answer », with the `irreversible` response). A file edit goes on: code checks its path against the mandate. A write too long to read before it runs (over about 220,000 characters of arguments) isn't held either, by the 10-10 rule of no hold for a technical reason: it runs, is read afterwards, and alerts with its incident open when the floor's labels flag it or no model answers. The triangle can't confirm a judgment either, so it holds less.
- **Your own MCP servers, tried on a test server only.** A profile (`CRESSEY_PROFILE`) names them the way MCP clients do (`mcpServers`), with what each tool does; Cressey fronts them instead of the demo tools. The tests run it against a local MCP server, not a company's.
- **Memory grows with the record.** An ended run drops what its calls returned and the arguments they carried, so memory no longer grows with what agents read, but each call still keeps about 14 KB (its step, its labels, its log events). A restart doesn't free it: with a state folder, the start reloads the whole log and rebuilds every step. Forgetting old runs is next.
- **Local only.** Nothing is deployed. Before Claude Code 2.1.295, a hook that can't reach Cressey lets calls through.

What happens when a part is down:

| Down | Reads | Writes Cressey's code lets through | Calls the code rules hold |
|---|---|---|---|
| Cressey, Claude Code 2.1.295+ (`onFailure: block`) | refused | refused | refused |
| Cressey, older Claude Code | go through | go through | go through |
| Jev | go through | held for a human, except file edits | held |

## Tests
```bash
cd backend && uv run pytest -q && uv run ruff check && uv run ty check
cd web && bun run ci && bun run build
```

## Sources and licences
ANSSI *Security recommendations for a generative AI system* (2024, Licence Ouverte 2.0), MITRE ATLAS v5.6.0 (Apache 2.0), OWASP *Top 10 for Agentic Applications 2026* (CC BY-SA 4.0). Runbooks and sessions are written by the team, with fake values only. No secret is in the repo.

## Team
**[names]**
