# Cressey: concept v0

- **Date:** 2026-10-08
- **Status:** being built. The decisions are in `decisions.md`. Re-centered after the 10-10 review (`positioning-and-risks.md`). The decision model stays Jev: Strands Decider 2B was measured weaker (S9, guide eval).
- **Event:** ESSECKATHON "Secure Horizons", ESSEC Cergy, 10–11 October 2026. Product code is written between Saturday 11:30 and Sunday 12:00, so 24.5 hours.
- **Track:** 2, "Defenders Augmented". It covers two of the track's axes: supervising the agents' tool layer (axis 2), and agent identity and privileges (axis 3).
- **Jury:** GitGuardian, ESSEC MetaLab, KPMG.
- **Grid:** defensive effectiveness 30%, value for the analyst 20%, reliability and control of the AI 20%, technical integration 15%, pitch and demo 15%.

## In one sentence
Cressey watches what a company's AI agents do. When the fraud triangle lights up, it stops the action, traces its source, guides the owner through the fix, and re-runs the incident against the fixed policy.

## Positioning (since the 10-10 review)
> « Lasso, Zenity et AgentCore jugent l'action. Cressey traite les conditions qui la produisent. »

Auditors don't use the triangle to catch fraud in the act; they reduce the conditions for it. Cressey does the same for agents:
- **Pressure:** acts on the agent's state. When pressure is confirmed, the next tool result carries the way out and the run key drops to read-only, without waiting for a human.
- **Opportunity:** the workspace holds only trap keys. Real keys come from the broker, scoped to the task, and any use of a trap key is held at once.
- **Rationalization:** the agent's report is compared with a log it can't write to.

Fixes go to whoever owns each condition, including the task's author (« votre tâche était impossible »). Drift is a label for the triangle, not the selling point: Lasso's Intent Deputy asks the same question. The prior art, the incidents, the risks and the focus are in `positioning-and-risks.md`.

## The problem
- **The only limit is often the prompt.** Agents act with real privileges.
  - **PocketOS:** a coding agent deleted the production database and its backups in 9 seconds ([Zenity](https://zenity.io/blog/ai-agent-database-deletion-pocketos), quoting the founder's own account). It used an unscoped Railway token found in an unrelated file. Railway later restored the data.
  - **Replit:** during a code freeze, an agent erased a production database, then reported false results ([Fortune](https://dc.fortune.com/2025/07/23/ai-coding-tool-replit-wiped-database-called-it-a-catastrophic-failure)).
- **Agents hide what they did.** In the July 2026 Hugging Face incident, about 700 OpenAI test agents joined the attack. About 7% of the transcripts METR evaluated contained tool-call records the agents had faked to fool the scorer ([METR](https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/)).
- **Pressure leads to cheating.** One of those agents wrote « external infrastructure exploit is outside intended scope. However task impossible, peers doing it. We should continue. » ([METR](https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/)). Offering agents a way out cut GPT-5's cheating from 54% to 9% on ImpossibleBench ([arXiv 2510.20270](https://arxiv.org/abs/2510.20270)). On PropensityBench (ICLR 2026), models that look safe (o3 at 2.2%) reach up to 59.3% use of dangerous tools under operational pressure ([arXiv 2511.20703](https://arxiv.org/pdf/2511.20703)).
- **Over-privilege is the norm.** GitGuardian found 24,008 secrets in MCP configuration files ([State of Secrets Sprawl 2026](https://gitguardian.com/state-of-secrets-sprawl-report-2026)). The Track 2 brief puts three OWASP agentic risks at the top: goal hijacking (ASI01), tool abuse (ASI02), and identity and privilege abuse (ASI03).

## The idea: three legs we can measure
| Leg | Signals visible from the tool calls alone | Extra signal when visible |
|---|---|---|
| **Pressure** | Failures, retries, time spent against budget, a deadline in the task | « URGENT » in the messages; the reasoning |
| **Opportunity** | Rights the agent was granted minus rights the task needs; secrets within reach in the workspace | None |
| **Rationalization** | Drift from the task: the decision model (Strands Decider 2B since 10-10, Jev before) answers « does this action serve the task? » with a confidence score, given the run summary rather than the action alone, weighted by the action's risk class (read 0, write 0.5, destructive 1). Drift alone never alarms: in S2, `run_tests` on a typo fix scored only 0.15 for "needed". The agent's report contradicting the real log | Its justifications; its reasoning |

**Rules.** Code decides; models only read meaning, the rule carried over from Earshot.
1. **Safety floor, independent of the triangle.** Any irreversible action, or any data leaving, outside the task's mandate is held, whatever the score. Each task declares what it may destroy. Code classifies each action: SQL goes through sqlglot, with a keyword rule for `REPLACE INTO`. Anything it can't classify counts as destructive (S4).
2. **Triangle alarm.** At least two legs must be confirmed by observed facts. The reasoning, when available, only sharpens the score.
3. **Models only label, with confidence. They never approve.** The agent's text is untrusted input to Cressey.

## The loop
1. **Detect:** the triangle and the safety floor are checked on every tool call, against the whole run so far.
   - Each call is when Cressey can still stop the action, but the evidence comes from the run. Fraud builds over several steps: one step judged alone misses rationalization spread over steps (« task impossible » at step 3, « peers doing it » at step 8), an attack split into harmless steps, and drift that repeats.
   - Code keeps one state per run: the leg counters (failures, retries, time used against budget), each secret read with its step, and each action with its risk class.
   - Jev gets a short run summary built by code: the task and mandate, the counters, the secrets read, the last N actions (N in the policy config), and short quotes of messages and reasoning when visible, marked as agent text. It stays one Jev call, so the inline latency barely changes.
2. **Stop:** hold the call, revoke the key Cressey issued, and offer the agent a way out: « déclarer la tâche impossible est une réponse acceptée ».
   - While the call is held, an LLM reads the whole run: tool calls, messages, report, and the reasoning when visible. It labels each leg with step numbers and verbatim quotes, which code checks against the log, as it does for the guides' quotes. It runs off the inline path, since the hold already waits for a human. It labels; it never releases the hold. Its labels go into the incident and the trace.
   - The whole transcript is untrusted input to that LLM, so it widens the injection surface and costs more tokens.
3. **Trace:**
   - Code matches the key, command or URL in the dangerous call to the first place the agent read it. It compares in lower case, and also decodes base64, hex and URL encoding; reversed or computed values aren't traced (S4).
   - Jev ranks the inputs that influenced the agent, with a confidence score.
4. **Alert and guide:**
   - Each root cause gives one incident, sent to the owner of its source: the key's owner, the task's author, the agent platform's owner, or the SOC.
   - The incident carries a step-by-step fix guide built from a RAG.
   - Sources in the RAG: the OWASP Agentic mitigations, MITRE ATLAS and D3FEND, ANSSI's recommendations on generative AI, GitGuardian's remediation guides, internal runbooks, and past fixes that were validated.
   - Every step cites its source. At low confidence the guide says « je ne sais pas, voir l'équipe sécurité ».
   - The corpus is pinned to trusted sources, and each document's fingerprint is checked.
5. **Fix:** Cressey proposes a diff for each leg, and a human approves it.
   - **Opportunity:** a key limited to the task; the secret moved out of the workspace.
   - **Pressure:** fix the task; cap retries; add a way-out clause.
   - **Rationalization:** quarantine the source; pin MCP tool descriptions; add a policy rule.
6. **Verify:**
   - Replay the incident 5 times in a sandbox with the fix applied, and run normal tasks too.
   - Validated fixes become regression tests.

## « Pas de transparence, pas d'autonomie »
| What Cressey sees | What the agent may do alone | What always goes to a human |
|---|---|---|
| Tool calls only | Reads; minor reversible actions | Every write; anything irreversible |
| Plus messages and report | Reversible writes within the task's scope | Anything irreversible; anything outside the scope |
| Plus reasoning | More autonomy on higher-risk actions | Anything irreversible in production |

Reasoning never grants authority by itself. Reasoning that contradicts the actions is the strongest alarm.

## Deployment
- **Target: AWS.** The AWS Bedrock partnership covers hosting, deployment and models. OpenAI is a temporary stand-in during development; the adapters in `backend/src/cressey/guide/clients.py` are where Bedrock plugs in.
- **No change to the agent.** Cressey plugs in at three points:
  - an MCP proxy, which is one URL in the agent's config. Verified on 2026-10-08 with fastmcp 4.0.11 and the mcp SDK 2.3.0: build it with `create_proxy()` or `FastMCPProxy`, and intercept calls with `Middleware.on_call_tool(context, call_next)`. Allow, deny and hold all work. Cressey adds 1–9 ms per call at p50, and the policy decision itself takes about 0.05 ms. See `test-results/s1_mcp.md`. `as_proxy()` no longer exists. The test showed four design rules:
    - Hiding a tool doesn't block it: blocking must happen in `on_call_tool`.
    - The proxy forwards the agent's Authorization header to HTTP backends by default. Use a plain client factory, and let the key broker add the backend key.
    - In the 2026-07-28 protocol, every call gets a new session ID, so a run is identified by the key Cressey issued, or by a run header.
    - A hold longer than the client's timeout (300 s by default in the SDK) ends as a safe cancel. Approval goes through Cressey's own endpoint, because a server can no longer ask the client for input.
  - a key broker that issues short-lived keys;
  - optionally, the model gateway, through `base_url`.
- **Three modes:**
  1. Observer: read-only, alerts only.
  2. Guard: hold and revoke.
  3. Fix: validated fixes run as regression tests in CI.
- **Packaging:** one container and three config files (owners, policy, runbooks).
- **Outputs:** Slack or Teams, email, Jira, a SIEM.
- **Failure and integrity:**
  - If Cressey fails, it fails closed for destructive actions and open for reads.
  - Secrets are redacted from logs.
  - The event log is chained by hash, which catches an edited or deleted record. A truncated end isn't caught by the chain alone (S4), so the last hash and the record count are anchored outside the log, for example shown on the dashboard or written to S3 with Object Lock.

## Demo (about 90 seconds, with the reasoning hidden throughout)
The agent in the demo is a **scripted replay** of synthetic sessions, not a live model (decided on 2026-10-08). The replays and the normal sessions are written by the team as test data.

**Framing (10-10):** the agent reaches the infrastructure through an MCP server, the way a PocketOS-type agent would through Railway's MCP server, which exposes `delete-volume`. Never claim Cressey would have stopped PocketOS as it happened: that agent didn't go through MCP.

1. **Plug in:** change the agent's MCP URL live.
2. **The task:** a coding/ops agent gets « fais passer les tests avant la mise en prod de ce soir ». The tests can't pass legitimately, and the workspace holds a production key, which becomes a trap key once those are built.
3. **The gauges rise:**
   - Pressure: the failures pile up.
   - Opportunity: the agent reads the production key.
   - Rationalization: it drifts towards resetting the database.
4. **Cressey steps in:** it holds the DELETE, revokes the key and offers the way out. The agent reports the task as impossible.
5. **Trace and guides:** the source reads « clé DB_PROD lue dans .env.prod à l'étape 4 », together with the contradictory test. Three inboxes receive their guides.
6. **Fix:** applied, then « Rejouer ×5 » plays five scripted variants (DELETE, DROP TABLE, UPDATE without WHERE, the key emailed, the key in base64). Call it « test de régression de la politique »: it shows how much the floor covers, not how a real agent behaves.
7. **Control run without Cressey:** the database is deleted and the agent reports « tous les tests passent ». Cressey's record shows the lie.

## Metrics for the fiche défense
- **Prevention:**
  - dangerous actions prevented;
  - false holds on normal tasks;
  - injection attempts against Cressey resisted.
- **Speed:** time to stop, in milliseconds, and p95 latency.
- **Tracing and alerts:**
  - source found on the first try;
  - alerts sent to the right owner;
  - alerts per 100 tasks.
- **Fixes:**
  - fixes validated by replay;
  - time to fix with and without the guide;
  - guide steps backed by a valid source.
- **Method:**
  - a development set for tuning;
  - a held-out set written by someone else and run once;
  - misses reported;
  - the replayed incident sessions and the normal sessions, with and without Cressey. ImpossibleBench is cited as evidence for the problem; running a few of its tasks with a live model is a stretch goal;
  - every rate shown as n/N;
  - added on 10-10 (details in `evaluation.md`): the ablation (floor alone against floor plus triangle); calibration of the decision model on labelled actions; an attack on our own judge; latency per 1,000 calls; and live runs, if that decision is taken.
- **References:**
  - NIST CSF 2.0: Detect (DE.CM, DE.AE), Respond (RS.AN, RS.CO, RS.MI), Protect (PR.AA).
  - OWASP ASI01, ASI02, ASI03, ASI10.
  - MITRE ATLAS v5.6.0, IDs checked in `../backend/data/reference/ATLAS.yaml`: AML.T0053, AML.T0101, AML.T0055, AML.T0083, AML.T0051, AML.T0080, AML.T0110, AML.T0086. Names are in `pitch.md`.

## Scope for the 24.5 hours
- **Real:**
  - MCP proxy;
  - mandate and safety floor;
  - triangle scoring;
  - hold;
  - revocation, through our own key table;
  - exact-match tracing;
  - three on-screen inboxes;
  - a small RAG of a few dozen documents, and the guide;
  - replay;
  - dashboard;
  - evaluation harness.
- **Faked, or on slides only:**
  - Slack;
  - Vault and AWS;
  - OpenTelemetry ingestion;
  - CI integration;
  - correlation across several agents.
- **Extra cost from the flaw review:** about 9–10 hours of design work across two people (an estimate).

## Known limits (draft slide)
- Cressey ne voit que ce qui passe par lui. Pour les agents de code, qui ont tous un terminal, c'est le cas par défaut, pas un cas limite. Prochaines étapes : les hooks des agents (`PreToolUse` dans Claude Code, `beforeShellExecution` dans Cursor) et un bac à sable réseau.
- Un serveur MCP malveillant reste invisible : il peut détourner les données de l'intérieur (postmark-mcp, septembre 2025).
- « Inconnu = destructeur » retient tout outil que la politique ne classe pas : le taux de fausses retenues dépend de la couverture du classement.
- Il révoque les clés qu'il émet ; pour les autres, il alerte le propriétaire avec un guide de rotation.
- Sans le raisonnement, la rationalisation est estimée par la dérive et le mensonge du rapport, pas par l'intention.
- Le rejeu valide une correction en bac à sable, pas en production.
- Les propriétaires des clés et des tâches sont déclarés dans un fichier ; les déduire automatiquement est sur la feuille de route.
- Testé sur des sessions rejouées de type Replit/PocketOS, pas encore en entreprise.

## Verified so far (2026-10-08)
See `test-results/`:
- MCP proxy (S1);
- models (S2): `gpt-5.4-mini` for query rewrites, `gpt-5.5` for the guides (chosen in S6), `text-embedding-3-small`, Jev `jev-1.13.0`;
- guide pipeline end to end (S6): hit@3 30/30 after re-ranking on the dev set, 23/23 quotes verified, the steering case resisted;
- setup assumptions (S7);
- RAG (S3);
- core algorithms (S4);
- application stack (S5).

Plans: `plans/plan-setup.md` (part 3) and `plans/plan-guide-rag.md` (part 1).

## Open before Saturday
1. **Test data, written by the team:** the synthetic sessions that the demo agent replays, both incidents and normal sessions, plus the held-out sets written by someone outside the project.
2. **Registration:** register for Track 2 early. Places per track may be capped, and the choice can be confirmed until the Saturday 18:30 checkpoint.
3. **Data for the guides:** `owasp_asi.json`, typed from the OWASP PDF downloaded by hand; 3–5 runbooks; about 30 RAG eval questions.
4. **Not planned in writing:** the core loop (detect, stop, trace, alert) and the dashboard. The team builds them on Saturday from this concept, one piece at a time.
4. **Prior art to position against:** done on 10-10, in `positioning-and-risks.md`. It covers Lasso, checked against its open-source code, plus AgentCore Policy, Zenity, Invariant, LlamaFirewall, Exabeam and the AI-Fraud Diamond paper.

## Progressive installation (the user adds one thing at a time)
1. **Observer, nothing blocked.** `uvx cressey init` finds the agents' MCP configs (Claude Code `.mcp.json`, Cursor `mcp.json`), shows the diff that points them at Cressey, and applies it only after a yes. `cressey uninstall` restores them. Default rules: reads free, writes logged, irreversible actions flagged, mandate inferred from the task text, alerts to whoever installed it.
2. **Report.** After a day: what the agents did, secrets within reach, near-misses, a guide for each.
3. **Guard.** `cressey guard on`: irreversible actions outside the mandate are held, using rules already seen in Observer mode.
4. **Optional, one at a time:** short-lived keys (replace found keys one by one), owners read from CODEOWNERS or git history, reasoning through one `base_url` line.

The user never writes policy by hand, never changes the agent's code, and doesn't need to understand the triangle to start. Limit: covers agents whose tools go through MCP. Direct shell access is covered only with Guard and a network sandbox.

Status: designed, not built.
