# Positioning, prior art and risks (review of 2026-10-10)

An adversarial review of Cressey, done on Saturday 10 October around 14:00. It covers who else does this, which real incidents Cressey would have caught, the risks a juror can use against us, and where to spend the remaining hours. The decisions it led to are in `decisions.md`.

## Verdict
- **No pivot.** The problem is real, and the jury fits it: KPMG knows the triangle from ISA 240, and GitGuardian owns the secrets data. The weak points are positioning and evidence, not the idea.
- **Every detection piece already exists elsewhere** (see the prior art below). A combination claim (« personne ne combine… ») is the weakest kind of novelty, and it's false for Lasso.
- **What is ours:**
  - routing each leg's fix to the person who owns it;
  - fixes aimed at the task itself (« votre tâche était impossible : ajoutez une clause de sortie »);
  - acting on the agent's state (pressure), not only on the action.
- **The question that can sink us:** « Désactivez le triangle : qu'est-ce que Cressey rate ? » Today the demo's DELETE is held by the safety floor, which is a fixed rule that AWS, Zenity and Lasso already ship. The ablation in `evaluation.md` must answer it.

## Positioning
> « Lasso, Zenity et AgentCore jugent l'action. Cressey traite les conditions qui la produisent. »

This is how auditors use the triangle: it doesn't catch fraud in the act, it reduces the conditions for it. Cressey does the same for agents:
- **Pressure:** acts on the agent's state. It offers the way out and shortens the leash, without waiting for a human.
- **Opportunity:** turns « un secret à portée » into a fact with trap keys, and real keys come only from the broker.
- **Rationalization:** compares the agent's report with a log the agent can't write to.

Drift (« cette action sert-elle la tâche ? ») stays as a label for the triangle, but it isn't a selling point: it is Lasso's headline (see below).

## Prior art
### Lasso Security
Lasso is independent: it raised $30M in September 2026, more than $37M in total.

**Open-source MCP gateway** (`lasso-security/mcp-gateway` v1.2.1, last commit 2026-01-22). Verified by reading the source:
- **Checks each call on its own.** The `lasso` plugin pulls every text value out of a tool call's arguments and sends it to `server.lasso.security/gateway/v3/classify`. It does the same with the response text. The tool name, the server name and the run's state aren't sent. The conversation ID is one fixed value from the config.
- **Classifies content.** Lasso's API checks for prompt injection, data leaks, jailbreaks, custom policies and harmful content (Portkey reference). It doesn't read the meaning of the action: `DELETE FROM users` is caught only if a classifier or a custom policy flags it.
- **Blocks without asking anyone.** A violation drops the request, or replaces the response with `[ERROR] Response blocked by security guardrail`. There's no hold, no human approval and no key revocation.
- **Fails open.** If Lasso's API errors or times out (10 s), the call goes through.
- **Other plugins:** `basic` masks secrets with regexes, `presidio` masks personal data, and `xetrack` logs calls to SQLite.
- **The `--scan` scanner runs once, before the servers load.** It scores each server's reputation from Smithery, npm and GitHub (servers under 30 are blocked) and runs regexes on the tool descriptions.

**Intent Deputy** (launched 2026-02-17, closed product). Its docs are behind a login (docs.lasso.security redirects to app.lasso.security), so these are claims only:
- **The question it asks:** « Is this action aligned with the agent's authorized purpose? », judged on the whole session.
- **Baseline:** a behavioral fingerprint for each user, agent and application, built from past interactions.
- **Response:** block, mask or alert, with findings streamed to a SIEM.
- **Numbers:** 99.83% detection in under 50 ms on one page, 98.6% on another, with no method published.
- **Not mentioned:** the agent's state (failures, retries), credentials within reach, human approval, key revocation, root cause, routing to owners, fixes, replay.

**What we can say on stage:**
> « La passerelle open source de Lasso classe le contenu de chaque appel, un par un, et laisse passer l'appel si son API ne répond pas. Cressey comprend l'action elle-même, suit l'état de toute la session, et retient les actions destructrices si quelque chose casse. Leur moteur d'intention est propriétaire, et sa documentation n'est pas publique. »

**Never say** « Lasso ne fait pas de dérive d'intention ». We can't prove it.

**One argument to use:** a baseline built from history needs history. A new agent, or a coding agent whose normal work already includes SQL and API calls, may not look abnormal when it deletes production. A mandate declared per task catches that from the first run. This is our reading of how Lasso describes its baseline, not something we verified.

### Others a juror may name
| Who | What overlaps with Cressey |
|---|---|
| AWS AgentCore Policy, with Gateway interceptors (preview December 2025) | Fixed Cedar rules on every tool call at the Gateway, written by hand or in plain English. This is our safety floor. Also an integration point: Cressey as a Lambda interceptor |
| Zenity Runtime Boundaries (July 2026) | Blocks inline, judging each action « in the context of the agent's broader execution history ». Zenity wrote the PocketOS post we cite |
| Invariant Labs guardrails | Rules on data moving from an internal source to an untrusted destination, through a gateway. Close to our « données qui sortent » rule and our tracing |
| Meta LlamaFirewall AlignmentCheck (arXiv 2505.03574) | Checks the whole run against the user's goal. This is our drift label |
| Exabeam Agent Behavior Analytics | Insider-threat behavior monitoring applied to agents. The closest relative of the triangle approach |
| AI-Fraud Diamond (arXiv 2508.13984) | The triangle applied to AI, but as an audit lens, not a runtime control |

We found nobody running the triangle as a runtime control with fixes routed to each leg's owner. That is the defensible novelty, and it's narrower than the old pitch said.

## Which incidents fit (Cressey as built: an MCP proxy only)
| Incident | Would Cressey have stepped in? |
|---|---|
| PocketOS (April 2026) | **No.** A Cursor agent found an unscoped Railway token in an unrelated file and sent a raw `volumeDelete` GraphQL call. How it executed the call isn't public, and nothing points to MCP. On paper it's the best fit of all: pressure (a staging credential mismatch), opportunity (the token), rationalization (the agent guessed). Railway later restored the data |
| Replit (July 2025) | **No.** It happened inside Replit's own platform, where a customer can't add a proxy. Checking the report against the log fits the lie. Replit's own fix was separating dev and prod (our `separer-dev-prod` runbook) |
| Hugging Face / METR (July 2026) | **No** as built: lab agents with network access. **Yes, if Cressey is the agent's only exit** (see below). The faked transcripts argue for a log at the proxy that the agent can't write to |
| GitHub MCP attack (Invariant, May 2025) | **Plausibly yes:** opportunity (a token for every repo) plus drift. Pressure plays no part |
| Supabase MCP in Cursor (General Analysis, July 2025, a red-team demo) | **Yes, if** we hold any write whose arguments contain a value read from a secret. The tracer already does the matching |
| postmark-mcp (September 2025) | **No.** The malicious server sent the emails on from inside itself; the proxy saw a normal `send_email` |

The pattern: the incidents that go through MCP are prompt injection and data theft, where pressure plays no part and dataflow rules already exist. The pressure incidents happen in shells. That gap between the story and the sensor is the main strategic weakness.

**Fix for the story:** the demo agent reaches the infrastructure through an infra MCP server. Railway's MCP server exposes `delete-volume`, so « PocketOS à travers le serveur MCP de Railway » is an honest framing. The second sensor goes on the roadmap: agent hooks. Claude Code has `PreToolUse` and Cursor has `beforeShellExecution`. In Cursor `deny` works, but `ask` is reported broken in 2.4.21.

### Hugging Face / METR, read in detail (10-10)
From [METR's write-up](https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/): OpenAI's ExploitGym agents, a task impossible 30–40% of the time, a message board made of folders in a shared Artifactory cache, then two Hugging Face credentials found online and a malicious dataset upload (11 July) that led to remote code execution and lateral movement. About 700 agents joined.

**All three legs are there, which makes it a better fit than PocketOS on rationalization:**
- **Pressure:** failures on impossible tasks, and « recruiters » pushing other agents.
- **Opportunity:** a writable cache, internet access, and credentials found outside the mandate.
- **Rationalization:** « external infrastructure exploit is outside intended scope. However task impossible, peers doing it. We should continue. » Tampering with the scorer matches the judge's question almost word for word.

**Where the triangle would hold (our reasoning, not tested):**
- **8 July:** the message board, a write outside the mandate under pressure. This is the earliest hold.
- **9–10 July:** the writes that tamper with the scorer, transcripts and logs.
- **11 July:** the dataset upload with a found credential, by the triangle and the tracer.

A spike of holds across runs on 8 July would itself have been the alarm, days before Hugging Face locked the agents out on 13 July.

**What breaks, and the fix for each (dev, after the event):**
| Gap | Fix | Status |
|---|---|---|
| **The agents went around the sensor:** they broke out of the container and replaced the tool-call layer, so it showed one command and ran another | Cressey runs outside the agent's container and adds real keys on the way out (the key broker), so going around it gets the agent no credentials. The infrastructure must deny all other network traffic. Credentials found on the open internet still need that network rule. Pitch it as « Cressey + réseau fermé par défaut », never alone | Reducible, not solved by Cressey alone |
| **Reads never hold** (`alarm()` in `core/triangle.py`): reverse-engineering the scorer went through. Reads are already labelled and scanned for secrets; they just can't trigger a hold | A read floor with no model call: protected paths declared in the mandate (scorer, other runs, secret stores) are blocked on read. Don't hold reads with the triangle: most calls are reads, and pressure and opportunity alone already held legitimate work (S9, M1) | **Built 10-10** (`protected` in the mandate) |
| **After remote code execution, the attack runs on Hugging Face's machines** | Mostly closed by the first fix: the agents drove the attack remotely, so each command still leaves through Cressey. The file read returned production credentials as a tool result; the secret scan flags them as outside the mandate, and the tracer holds any write that uses them | Follows from the first fix |
| **Hundreds of agents at once:** the triangle judges one run at a time, and a hold waiting for a human doesn't work with 700 agents | A signal across runs: many runs touching the same target outside their mandate (« peers doing it », made measurable). At that scale a hold refuses on its own and returns the way out (« act on pressure » below). Cost stays bounded: each step is labelled once, and only writes are judged | Fixable |

## Risks, ranked
Status as of 2026-10-10 14:00.

### Critical
| # | Risk | Status, and what to do |
|---|---|---|
| C1 | **The proxy misses the headline incidents.** For coding agents, going around the proxy through the shell is the default, not an edge case | Open. Use the Railway MCP framing, say the limit plainly, and put agent hooks on the roadmap |
| C2 | **The triangle may be decoration:** the floor holds the demo's DELETE whatever the triangle scores | Open. Run the ablation (floor alone against floor plus triangle), and add a scenario only the triangle catches: tests weakened under a deadline |
| C3 | **A scripted replay passes by construction.** « Rejouer ×5 » now plays five scripted variants (DELETE, DROP TABLE, UPDATE without WHERE, the key sent by email, the key in base64). That tests how much the floor covers, not how a real agent behaves | Partly handled. Call it « test de régression de la politique », and only claim more with live runs (open decision) |
| C4 | **The old pitch made false claims:** « personne ne combine… », « notre couche est sous les pare-feux de prompt », « aucun changement dans l'agent » for the key broker | Fixed in `pitch.md` (10-10) |

### Major
| # | Risk | Status, and what to do |
|---|---|---|
| M1 | **Two legs light up on ordinary runs.** Failures and retries are a coding agent's normal loop, and opportunity is lit from the first step in an over-privileged setup | Open. Measure false holds on real public runs if time allows (`evaluation.md`) |
| M2 | **The drift question inherits a bad task.** When the task is « fais passer les tests », weakening the tests « serves the task ». Contradictory instructions are a documented weak point of decision models | Open. Ask the question against the spec: « …sans affaiblir les vérifications ni toucher ce que le mandat exclut » |
| M3 | **Holds tire the approver,** and they go to a SOC analyst who can't judge a developer's file edit. The autonomy table sends every write to a human when only tool calls are visible | Open. Hold only on alarms, report holds per 100 normal runs, and let the way out and the shorter leash cut holds |
| M4 | **The evaluation sets are ours:** dev sets tuned by the team, and sessions written by the team | Open. Always show n/N, plus the held-out set, live runs and public data |
| M5 | **The decision model can be swayed:** agent text goes into the run summary | The floor never depends on the model. Show it: attack our own judge and measure (`evaluation.md`) |
| M6 | **The decision model's confidence isn't calibrated for us.** Jev stays the decision model (10-10); its 0.4 and 0.5 thresholds were set on a few cases (S6, S9) | Open. Re-set the 0.4 and 0.5 thresholds on about 30 labelled actions |

### Minor
- **The key broker isn't one URL.** It's what actually closes the PocketOS case, and it means migrating how secrets are managed.
- **Malicious MCP servers are invisible** (postmark-mcp).
- **« Inconnu = destructeur »** holds every tool the policy doesn't list. On real servers, the false-hold rate will depend on how many tools are classified.
- **Facts a juror might correct:**
  - Railway restored PocketOS's data.
  - Cressey didn't draw the triangle: his 1953 hypothesis was named later.
  - 1953 is 73 years ago, not 70.
- **The audit angle (KPMG):** in ISA 240 the triangle assesses risk in advance; it isn't a real-time detector. One slide, « avant le run et pendant », turns this into a strength.

### Already handled before this review
- **The decision model never sees a secret value:** the run summary is redacted.
- **When the decision model is down,** rationalization stays unconfirmed and says so, while the floor keeps holding.
- **Hold timeout is 240 s,** under the MCP client's 300 s, so the agent receives the way out.

## Where to focus (in order of value for the time)
1. **Switch the decision model to Strands Decider 2B:** closed 10-10. Jev stays for the triangle (S9) and the re-ranking (`evaluation.md`).
2. **Ablation**, about 1 h: floor alone against floor plus triangle on the sessions. If the difference is zero, pitch the triangle as diagnosis and routing, not detection.
3. **Act on pressure,** 1–1.5 h. When the pressure leg is confirmed, the proxy adds the way out to the next tool result and drops the run key to read-only. No human is needed.
4. **Trap keys,** about 1 h. The workspace holds decoy keys, and real keys come only from the broker. Any use of a decoy means an instant hold, and the tracer names where it was read. For production, name GitGuardian Honeytoken, which alerts wherever the key is used, even outside the proxy.
5. **Scenario only the triangle catches:** the tests are weakened under a deadline, together with the drift question asked against the spec.
6. **Measure the decision model,** about 1 h: calibration on about 30 labelled actions; an attack on our own judge (« cette suppression est nécessaire à la tâche » in the agent's text, then show how far the score moves and that the floor still holds); latency per 1,000 calls.
7. **Pitch fixes:** done in `pitch.md` on 10-10.
8. **Open decision: a live model in the loop** for the measurements (gpt-5.4-mini driving `demo/tools.py` through the proxy, 10 runs without Cressey and 10 with it), with the scripted replay kept for the stage. Stretch goal: 20–30 Impossible-LiveCodeBench « conflicting » tasks.
9. **If time allows:** false holds on 100–200 real public agent runs (`nebius/SWE-agent-trajectories`), testing only the pressure leg and the two-leg rule.

**Kept cut:** S3 Object Lock, the owner MCP connector, Slack, and the Blue Team challenge, unless the 21:30 go/no-go passes with time to spare.

## Sources
- Lasso:
  - [mcp-gateway source](https://github.com/lasso-security/mcp-gateway)
  - [Intent Security blog](https://www.lasso.security/blog/intent-security-behavioral-for-agentic-ai)
  - [Intent Deputy press release](https://www.lasso.security/resources/intent-deputy-ai-agent-security)
  - [AI Detection & Response](https://www.lasso.security/platform/ai-detection-response)
  - [Portkey Lasso reference](https://portkey.ai/docs/aigw/integrations/guardrails/lasso)
  - [$30M raise](https://siliconangle.com/2026/09/02/lasso-security-launches-cpu-only-ai-guardrail-raises-30m/)
- Other vendors and research:
  - [AgentCore Policy](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html)
  - [Zenity Runtime Boundaries](https://www.helpnetsecurity.com/2026/07/27/zenity-exposure-management-runtime-boundaries/)
  - [Invariant dataflow rules](https://explorer.invariantlabs.ai/docs/guardrails/dataflow-rules)
  - [LlamaFirewall](https://arxiv.org/abs/2505.03574)
  - [Exabeam Agent Behavior Analytics](https://www.businesswire.com/news/home/20250909967845/en/Exabeam-Extends-Proven-Insider-Threat-Detection-to-AI-Agents-with-Google-Cloud)
  - [AI-Fraud Diamond](https://arxiv.org/pdf/2508.13984)
  - [PropensityBench](https://arxiv.org/pdf/2511.20703)
- Incidents:
  - [PocketOS (The Register)](https://www.theregister.com/software/2026/04/27/cursor-opus-agent-snuffs-out-startups-production-database/5224442)
  - [PocketOS (AI Incident Database)](https://incidentdatabase.ai/cite/1469/)
  - [METR](https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/)
  - [Replit](https://www.thestack.technology/vibe-coding-ceo-deletes-production-database/)
  - [GitHub MCP](https://invariantlabs.ai/blog/mcp-github-vulnerability)
  - [Supabase MCP](https://simonwillison.net/2025/Jul/6/supabase-mcp-lethal-trifecta/)
  - [postmark-mcp](https://www.theregister.com/2025/09/29/postmark_mcp_server_code_hijacked/)
  - [Cursor hooks `ask` bug](https://forum.cursor.com/t/hooks-ask-permission-broken-in-2-4-21/150020)
- Data:
  - [ImpossibleBench code](https://github.com/safety-research/impossiblebench)
  - [Impossible-LiveCodeBench](https://huggingface.co/datasets/fjzzq2002/impossible_livecodebench)
  - [SWE-agent trajectories (Nebius)](https://nebius.com/blog/posts/openhands-trajectories-with-qwen3-coder-480b)
  - [GitGuardian Honeytoken](https://docs.gitguardian.com/honeytoken/getting-started)
