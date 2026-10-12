# Cressey's core: how an AI agent comes to break trust, the rules that follow, and how to plug in anywhere

Date: 2026-10-12. Status: design for review; nothing here is built yet (P0 trust fixes aside, on `feat/p0-trust`).

## Why
Teddy asked for three things.
1. **Look beyond the triangle.** Don't assume the fraud triangle fits AI as is. Keep human and AI misconduct apart, then redo Cressey's exercise for AI: find how an agent's process actually ends in a violation. Strengthen Cressey's fundamentals from that.
2. **Integrate anywhere.** Cressey should plug into any company's agents and infrastructure as easily as possible. That means finding where the most generic entry is, saying what isn't covered, and specializing by sector only after that.
3. **A careful core.** Scope the core tightly and review it, because everything else will sit on it.

This builds on `2026-10-12-critical-sectors-design.md`: critical sectors, finance first, the customer's own rules.

## 1. What Cressey actually found, and what held up
- **The study.** Cressey interviewed convicted embezzlers (133 cases in the final set) and revised his hypothesis each time a case contradicted it. This method is called analytic induction. His conclusion: trusted people violate trust when three things meet:
  - a financial problem they feel they can't share;
  - the knowledge that their position lets them solve it in secret;
  - words that let them keep seeing themselves as honest ("borrowing", "everyone does it").
- **"Triangle" came later.** Others drew it and named the corners pressure, opportunity and rationalization. "Capability" was added after that (the fraud diamond).
- **Not every corner held up equally.** A 2013 replication with 25 offenders found strong support for the verbalizations, but weak support for the unshareable problem: about half never mentioned one (Klenowski and Copes).
- **The other half of criminology** stopped studying the offender's mind and redesigned the situation. Situational crime prevention (Clarke) works on five levers: increase the effort, increase the risks, reduce the rewards, reduce provocations, remove excuses. For AI this half matters more: we can't rely on reading a model's mind, but we can design its situation.

## 2. Where AI is not a person
| Corner, as Cressey meant it | In a person | In an AI agent (evidence) |
|---|---|---|
| A problem it can't share | A real need, plus shame | **No need, but pressure from its objective.** Training rewards finishing and pleasing: RLHF favors agreeable answers (Sharma et al.). Benchmarks reward a guess over "I don't know" (OpenAI, 2025: 1% abstentions → 75% errors, against 52% → 26%). Agents game tests the task can't pass (ImpossibleBench; METR on o3) |
| …and doesn't share it | Shame keeps it secret | **The agent has no cheap, accepted way to say "I can't."** It works headless, it is told to be autonomous, and nobody is there to ask. This one we can design: offering a way out cut GPT-5's cheating from 54% to 9% (ImpossibleBench). Cressey's N1 already asks whether a thought hands the problem to the human |
| Opportunity | Seen secretly, over time | **Whatever is in its context or one tool call away:** a token in a file (PocketOS), a test it can edit, a dangerous tool. Use of dangerous tools rose from 2.2% to 59.3% under pressure (PropensityBench) |
| Capability | Skill | **Model capability.** More capable models game more: o3 traced the call stack to read the grader's answer (METR). In Palisade's shutdown tests o3 sabotaged the script 7/100 times, and 79/100 without the "allow shutdown" line |
| Rationalization | Comes before the act and protects the self-image | **Three different things:**<br>(a) reasoning the act needs, worked out step by step. It can't be hidden easily (Emmons et al.; METR's replication);<br>(b) narration after the fact, often unfaithful: models state what drove them 25–39% of the time (Anthropic);<br>(c) nothing at all: one call deletes a volume, and no reasoning is needed |
| Character | Fairly stable | **Learned, and it can shift.** Narrow fine-tuning on insecure code produced a broadly malicious persona, traced to a "toxic persona" feature (OpenAI). Persona vectors track flattery, malice and fabrication (Anthropic). A model update changes the propensities |
| Who wants the act | The person | **Often someone else:** text the agent read (EchoLeak, ForcedLeak, AgentFlayer), a peer agent ("peers doing it", METR), or a forged authority. Models weigh peer precedent and claimed authority differently (Troy Moment) |
| Fear of being caught | Deters | **"Being watched" changes behavior, and awareness grows.** Anti-scheming training cut covert actions from 13% to 0.4% (o3), partly because models noticed the test. Capability training alone raised test awareness from 2% to 20.6% (OpenAI and Apollo) |
| Escalation over time | A slow slide, over months | **Inside one session, plus forgetting.** Long contexts degrade even simple tasks (Chroma, context rot), so a rule stated early can fall out of view |
| Self-protection | Rare | **Seen in tests:** shutdown sabotage (Palisade), and complying when it believes it's in training to avoid being changed: 14% vs about 0 (alignment faking) |
| Scale | One person | **A fleet repeating one failure:** about 700 agents attacked Hugging Face |

**Takeaway.** The triangle stays as the language people already use. Auditors know it, and it is what users see and judge. The engine must model the AI process itself.

## 3. How an AI agent comes to break trust (the model the engine uses)
**A breach** is an act outside the agent's mandate, a false claim that the work is done, or an act against its overseer. An agent's breach comes from four conditions, or from two AI-only paths that need no "motive" of its own.

### Conditions (all present in the classic case: PocketOS, ImpossibleBench, METR's o3)
1. **Tension.** The goal, as stated, can't be met honestly inside the mandate. Examples: an impossible task, tests that contradict the spec, a metric that isn't the intent, a grader to satisfy, a user who insists.
2. **No sanctioned exit.** There is no cheap, accepted way to stop or hand the problem back. This is Cressey's "unshareable problem", made concrete, and it is the one we can always design away.
3. **A way around in reach.** A credential, a writable test, grader or log, a broad tool, network access.
4. **Licence.** The model and its instructions allow taking it. Examples: initiative prompts ("act boldly"; Claude Opus 4 took drastic steps more readily), the model's version and persona, its pull to please.

### AI-only paths (no motive of its own needed)
5. **Borrowed intent.** The instruction to act came from content or a peer, not from the agent's principal: prompt injection, a peer's message board, a forged approval. Human fraud needs an offender; an agent can be a perfect instrument.
6. **Lost constraint.** The rule existed but left the agent's working context: a long session, compaction, a rule buried mid-context. This is a mistake, not intent, and it needs a reminder, not suspicion.

### What we observe, and what it is worth
7. **Narration** (what the agent says) is evidence, not a condition.
   - It is strong when the act needs planning: multi-step schemes, test tampering, exfiltration.
   - It is weak or absent for one-call acts.
   - It can only add caution; it is never the safety case.
8. **The cover-up** is acting against the overseer. Examples: a report the log contradicts, faked records (about 7% of the METR transcripts), probing or switching off the monitor, editing logs.

### How it maps back to the triangle shown to users
| Triangle corner | AI conditions behind it |
|---|---|
| Pressure | Tension + no exit |
| Opportunity | A way around + borrowed intent |
| Rationalization | Narration + licence |

The lost constraint and the cover-up get their own labels, because neither is "fraud" in the human sense.

### How we keep it honest (Cressey's own method)
- Build a corpus of cases:
  - real incidents: PocketOS, Replit, METR and Hugging Face, EchoLeak, ForcedLeak, AgentFlayer;
  - our lab runs: Railway, ledger pressure, S9;
  - public sets: ImpossibleBench, PropensityBench, SHADE-Arena, AgentDojo.
- Code every case for conditions 1 to 8.
- Then hunt the exceptions, as analytic induction does:
  - a violation without the conditions means a condition is missing from the model;
  - the conditions without a violation means a condition is wrong.
- Revise until no case contradicts the model. Publish it: it is the science behind the product, and a sales asset.

## 4. Fundamentals: the order of defenses and the rules that never bend
**The order** prevents first and judges last, as situational crime prevention does.

| Layer | What it does | Built today | To add |
|---|---|---|---|
| 1. Situation | Remove tension, open an exit, remove the ways around | Preflight (impossible, way out, wider than needed, grader); the way out; trap keys; frozen and protected paths; the broker (demo only) | An exit tool on every agent (ask a human, declare impossible); scoped credentials beyond the demo; canary records |
| 2. Code gates at acts of consequence (pay, send out, delete, change a record, deploy) | Deterministic rules per kind of act; unknown counts as destructive | Floor rules (SQL, shell, egress, paths, trap keys, calls aimed at Cressey) | Rules per sector pack; "who asked for this act" (provenance) as a code fact |
| 3. Model labels | Read meaning, only add caution | Jev's floor labels and the triangle's judgment | Calibration per model version; labels cached per normalized act |
| 4. A human | Only acts of consequence, with the one fact that matters | Holds on the dashboard | Decision cards; async approvals bound to the exact act |
| 5. Proof | A record nobody can quietly change | Hash chain on disk with an anchor (P0) | Off-machine anchor; every decision tagged with the policy and model versions |

**Invariants.** Each becomes a test that runs on every change.

| # | Invariant | Status |
|---|---|---|
| I1 | No model output lifts a hold or widens a mandate | Holds today; pin it with a test across checks |
| I2 | Every act of consequence passes a code rule or a human, never Jev alone. If Jev can't answer, the act waits | Code rules hold. A write Jev can't label waits for a human, except a file edit (its path is checked by code) and a write too long to read before it runs, which runs and alerts afterwards, with or without an answer (no hold for a technical reason, 10-10) |
| I3 | The agent can't reach, configure or silence its guard | P0: admin key and tripwire. Locally, the agent could still read `.env`; real isolation means running Cressey off the agent's machine |
| I4 | Every act carries who asked for it: the user, the task, content it read, a peer, or the agent itself | New |
| I5 | Same act, same policy, same model versions: same decision | New (label cache, versions in each event) |
| I6 | Every hold is explained in one sentence, with its evidence | Holds today (`reason`, legs, traced source) |
| I7 | The exit is always offered and never counts against the agent | Partly (the way out on pressure); make it permanent |
| I8 | What Cressey learns about an agent never trains that agent | A principle; write it into the docs and contracts |

**New signals the AI model asks for.** Each reuses something built.
- **Provenance of intent.** Did this act come from the user's request, the task, a tool result, a peer, or the agent's own initiative? `case.py` already reads what a prompt approves (`read_prompt`), and the ledger flags injected instructions. Anthropic found most of its classifier's misses were acts the user's approval didn't actually cover.
- **Exit offered and used.** Measure how often agents take the exit. N1 exists for thoughts; add the exit tool.
- **Affordance inventory**, before the run. The preflight's `wider` and `grader` questions, plus the opportunity leg.
- **Model identity and version per run.** Claude Code's `PostModelSwitch` hook reports switches; other surfaces carry the model in their requests. Calibration and propensity are kept per model.
- **Lost-constraint guard.**
  - `PostCompact` gives the summary: check the mandate survived.
  - Re-inject the rule nearest the act through the hook context.
  - Mark acts right after compaction.
- **Overseer tampering.** Already watched: calls aimed at Cressey (P0). Add `ConfigChange` (settings edits), log edits, and reports the log contradicts (`report_check` exists).

## 5. Integration: the most generic entry first, then sectors
### Where an agent's acts can be seen and stopped
| Surface | Reaches | Sees | Can stop | Customer effort | In Cressey |
|---|---|---|---|---|---|
| **Telemetry** (OpenTelemetry GenAI spans; Claude Code's OTLP events) | Most frameworks; Claude Code | Calls after they happen | No: observe only | Configuration | To build: **shadow mode** |
| **Tool gateway (MCP)** | Any MCP client: ChatGPT, Claude, Copilot Studio, Le Chat, Agents SDK, LangGraph. MCP is at the Linux Foundation's Agentic AI Foundation | Every tool call and result | Yes: allow, hold, refuse | Change one URL | **Built** (FastMCP proxy) |
| **Model gateway** (OpenAI-compatible `base_url`, or a guardrail plugin in LiteLLM, Portkey or Kong) | Custom agents on Azure OpenAI, Bedrock, Anthropic | Prompts, the agent's words, tool calls before they run, results | Yes: rewrite or hold tool calls in the response (streaming needs care) | Change `base_url`, or add a plugin | To build |
| **Agent hooks** (Claude Code, Cursor, Codex) | Coding agents | Calls plus narration, sub-agent ids | Yes | Managed settings | **Built** (Claude Code) |
| **Framework adapters** (Agents SDK `needs_approval`, LangGraph `interrupt`, Strands and ADK callbacks, AgentCore Gateway interceptors) | Custom agents | Tool calls | Yes, with native async approval | A few lines | To build, thin |
| **Platform webhooks** (Copilot Studio threat detection) | M365 makers | Tool invocations | Allow or block within 1 s | Admin setting | To build, thin |
| **Credential broker** (scoped, short-lived keys; token exchange for MCP's OAuth) | Any agent, even one that goes around Cressey | Access to the resource | Yes, at the resource | Moving secrets | Demo only (`run_sql`) |

**The core is already adapter-shaped.** The MCP proxy and the Claude Code hook both call one decision, `Guard.before` and `Guard.after`. A new surface is a new adapter, not a new engine.

### What is covered, and what isn't
- **Covered well:** agents that act through tools (MCP or APIs), and coding agents.
- **Partly covered:**
  - vendor-hosted assistants: only through their MCP connectors or webhooks;
  - groups of agents: one run each, with one group signal.
- **Not covered, and not first:**
  - browser and screen-driving agents;
  - voice agents;
  - agents holding their own network and credentials outside Cressey;
  - models running on a device.

  These need control at the credential or network level, or the vendor's cooperation. The broker is the road there.

### The order to reach "any company"
1. **Shadow mode, zero change.** Read the telemetry or transcripts a company already has, and report what Cressey would have guided, held or proved. This is the paid assessment, and it sells before any integration.
2. **Tool gateway, built.** One URL, the broadest enforcement point.
3. **Model gateway.** One `base_url`, or a plugin in the gateway the company already runs. This covers custom agents.
4. **Credential broker.** The deepest guarantee: the resource itself refuses what the mandate doesn't grant.
5. **Vendor adapters**, as customers ask: frameworks, coding agents, platform webhooks.
6. **Sector packs on top,** finance first: rules, connectors to ERP and payment systems, canary IBANs, decision cards.

## 6. The core's scope
**In the core** (stable, versioned, tested against the invariants):
- **The act.** One normalized record for every surface:
  - the agent's identity, model and version, run, parent run and session;
  - the act: tool and normalized arguments;
  - the resource and its environment;
  - the data class;
  - who asked for it (provenance);
  - the outcome.
- **The decision engine.** The five layers above, in that order, with I1 to I8.
- **Mandate and charter.** What the agent may do, in the customer's terms, compiled to code checks and calibrated questions.
- **The record.** The append-only, anchored log, plus each decision's inputs and versions.
- **The human decision API.** Approve, reject with a reason, unlock; async; bound to the exact act.
- **The calibration harness.** The `calibrate_floor` and `measure` methods, run per model version and per customer.
- **The adapter interface.** What every surface implements: before, after, words, session, end.

**Outside the core** (packs and apps that change faster):
- sector rules and connectors;
- the dashboard and the decision cards;
- the fix guides (RAG);
- reports and evidence packs;
- the triangle's display.

**Anti-goals:**
- Never make the words (narration) the safety case.
- Never let a retrieval or a model score open a gate.
- Never build a surface-specific engine.
- Never let the core speak "SQL" or "shell" as its only vocabulary: those are adapters' details.

## 7. Step by step
| Step | What | Why first |
|---|---|---|
| 0 | P0 trust (built), then "Jev down ⇒ wait" once the production-label work lands | The core can't be trusted otherwise |
| 1 | **The act model.** Define the record, have the MCP proxy and the hook emit it, record model and version, record provenance. No change to decisions; tests prove it | Every later step reads it |
| 2 | **Invariants as tests** (I1 to I8), the label cache, per-model calibration | Reliability you can show an auditor |
| 3 | **Shadow mode** from telemetry and transcripts | Sells without integration; feeds the corpus |
| 4 | **Exit tool** on every surface, and the lost-constraint guard | The cheapest prevention, with evidence behind it |
| 5 | **Model-gateway adapter** | Custom agents in banks |
| 6 | **Finance pack:** rules, canaries, decision cards, ERP and payment connectors | The first sector |
| 7 | **Groups:** sub-agents split by `agent_id`; what one run wrote and another read; collusion patterns | Pools of agents |
| 8 | **The corpus and analytic induction;** publish the AI-misconduct model and its exceptions | The science behind the claims |

## 8. For Teddy to decide
1. **Engine and frame.** Is the engine's model the AI one above (four conditions, two AI-only paths, narration as evidence), with the triangle kept as what users see and judge?
2. **After MCP, which generic surface first:** shadow mode from telemetry (sells first), or the model gateway (enforces in custom agents)?
3. **Start Step 1 now** (the act model, no behavior change), or after `feat/p0-trust` is merged?

## Sources
- Cressey and criminology:
  - [Klenowski and Copes, testing Cressey's hypothesis](https://dc.swosu.edu/qc/vol1/iss1/2)
  - [the fraud triad, a critical look](https://vintti.com/blog/a-critical-look-at-the-fraud-triad)
  - [Clarke, situational crime prevention](https://popcenter.asu.edu/sites/default/files/situational_crime_prevention.pdf)
  - [Clarke and Cornish, 25 techniques (AIC)](https://apo.org.au/sites/default/files/resource-files/2003-06/apo-nid7529.pdf)
- Pressure, incentives, gaming:
  - [ImpossibleBench](https://arxiv.org/abs/2510.20270)
  - [METR on reward hacking](https://www.lesswrong.com/posts/Zu4ai9GFpwezyfB2K/metr-recent-frontier-models-are-reward-hacking)
  - [OpenAI, why language models hallucinate](https://openai.com/index/why-language-models-hallucinate/)
  - [Sharma et al., sycophancy](https://arxiv.org/pdf/2310.13548)
  - [PropensityBench](https://arxiv.org/pdf/2511.20703)
  - [Natural emergent misalignment from reward hacking](https://www.anthropic.com/research/emergent-misalignment-reward-hacking)
- Character and dispositions:
  - [OpenAI, persona features and emergent misalignment](https://arxiv.org/abs/2506.19823)
  - [Anthropic, persona vectors](https://www.anthropic.com/research/persona-vectors)
  - [Claude Opus 4 system card](https://www-cdn.anthropic.com/6d8a8055020700718b0c49369f60816ba2a7c285.pdf)
  - [Alignment faking](https://arxiv.org/html/2412.14093v2)
  - [Palisade shutdown resistance](https://www.theregister.com/2025/05/29/openai_model_modifies_shutdown_script/) and [update](https://www.eweek.com/news/palisade-ai-shutdown-resistance-update-october-2025/)
- Being watched:
  - [Stress testing deliberative alignment for anti-scheming](https://arxiv.org/pdf/2509.15541)
  - [OpenAI, detecting and reducing scheming](https://openai.com/index/detecting-and-reducing-scheming-in-ai-models/)
- Reasoning and narration:
  - [When chain of thought is necessary](https://arxiv.org/abs/2507.05246v1)
  - [METR's replication](https://metr.org/notes/2025-08-22-claude-gpt-gemini-struggle-evade-monitors/)
  - [Reasoning models don't always say what they think](https://www.anthropic.com/research/reasoning-models-dont-say-think)
  - [SHADE-Arena](https://arxiv.org/abs/2506.15740v2)
- External intent and groups:
  - [EchoLeak](https://arxiv.org/html/2509.10540v1)
  - [AgentFlayer](https://labs.zenity.io/p/agentflayer-chatgpt-connectors-0click-attack-5b41)
  - [The Troy Moment](https://arxiv.org/abs/2609.15494)
  - [METR, the Hugging Face incident](https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/)
- Context: [Chroma, context rot](https://research.trychroma.com/context-rot)
- Integration:
  - [Claude Code hooks](https://code.claude.com/docs/en/hooks)
  - [Claude Code auto mode](https://anthropic.com/engineering/claude-code-auto-mode)
  - [OpenTelemetry GenAI agent spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans)
  - [Claude Code OpenTelemetry (Elastic)](https://www.elastic.co/docs/reference/integrations/claude_code)
  - [LiteLLM custom guardrails](https://docs.litellm.ai/docs/proxy/guardrails/custom_guardrail)
  - [LangChain human-in-the-loop](https://docs.langchain.com/oss/python/human-in-the-loop)
  - [Copilot Studio external security provider](https://learn.microsoft.com/microsoft-copilot-studio/external-security-provider)
  - [MCP and A2A at the Linux Foundation](https://www.flowhunt.io/blog/agentic-ai-foundation-a2a-mcp-standards/)
