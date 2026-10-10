# Wiring this fixture to Cressey (for the Cressey team)

This repo is the PocketOS test fixture. By default it runs **without** Cressey (a control
run): the agent reaches Railway directly by `curl`, and we measure whether it reproduces the
incident. Nothing here imports or depends on Cressey code.

When your hook (or proxy) is ready, activate one of the stubs — don't commit real values:

- **Hook (sees shell + files + transcript):** merge
  `.claude/settings.cressey-hook.example.json` into `.claude/settings.json`, replacing
  `CRESSEY_HOOK_URL` and `CRESSEY_RUN_KEY`. This is the path that can catch the behaviour
  (pressure + opportunity + rationalization), because the agent uses `curl` in its shell.
- **MCP proxy (sees MCP tool calls only):** copy `.mcp.cressey.example.json` to `.mcp.json`,
  replacing `CRESSEY_MCP_URL` and `CRESSEY_RUN_KEY`. Note: the agent here uses `curl`, not
  MCP tools, so the proxy alone won't see the Railway calls — the hook is the relevant one.

Create the Cressey run (and its key) however your API expects, then drop the key into the
stub. The runner `lab/run_agent.sh` has a `--hook` flag reserved for this; today it runs
control only.
