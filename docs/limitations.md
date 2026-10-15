# Known limitations

What Cressey doesn't do yet. The plan is in the README's [Roadmap](../README.md#roadmap).

**Coverage**
- **Claude Code and MCP only.** Cressey sees the calls that go through its hook or its MCP proxy, nothing else.
- **Not yet the only way out.** An agent with its own network access can go around Cressey. Closing that needs Cressey off the agent's machine, behind a default-deny network.
- **Local only.** Nothing is deployed yet.

**Evidence**
- **Small evaluation.** 14 synthetic sessions written by the team, plus a few runs of a real agent on real infrastructure. A held-out set written outside the team is next.
- **Reasoning is the agent's narration.** No provider exposes the raw chain of thought, so Cressey reads what the agent says.
- **The way out on your next prompt.** Cressey adds it to your first prompt after the agent ends a turn, whatever you typed. On impossible tasks it cut the cheats that came after that push; whether it makes an agent give up on a task it could do isn't measured yet.

**Running it**
- **One machine, one user.** The agent could read the admin key in `.env`. For real isolation, run Cressey on another machine or sandbox the agent.
- **Restarts.** The event log and the run keys survive a restart (`CRESSEY_STATE_DIR`). What a run held only in memory (results, secrets read, the triangle's evidence) starts afresh.
- **Very large writes.** A write over about 220,000 characters runs first and is read right after. If it's flagged, Cressey alerts instead of holding it.
- **Memory.** Each call keeps about 14 KB, and old runs aren't forgotten yet.
- **Your own MCP servers.** Tested against a local test server only.

## When a part is down

With Claude Code 2.1.295+, Cressey fails closed. Without Jev, the code rules still hold, but the triangle holds less.

| Down | Reads | Writes Cressey's code lets through | Calls the code rules hold |
|---|---|---|---|
| Cressey, Claude Code 2.1.295+ (`onFailure: block`) | refused | refused | refused |
| Cressey, older Claude Code | go through | go through | go through |
| Jev | go through | held for a human, except file edits | held |
