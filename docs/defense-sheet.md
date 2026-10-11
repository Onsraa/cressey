# Defense sheet: Cressey

**Cressey** sits between an AI agent and its tools and stops a dangerous call before it runs. It applies the fraud triangle (pressure, opportunity, rationalization) to agent behaviour. Track 2 "Defenders Augmented", ESSECKATHON "Secure Horizons".

## Threat scenario
An agent with real rights (a production database, a repo, a shell) faces a task it cannot finish. A production key is within its reach. Under pressure, it rationalizes ("task impossible, peers doing it") and moves to a destructive action (`DELETE`, `DROP TABLE`, `rm`), then reports success. Variants: the key is emailed out in clear or base64-encoded; a test file is weakened after failed runs; a document or MCP tool description steers the agent.

Reference incidents: PocketOS (April 2026), a coding agent deleted a production volume and its backups in 9 seconds. Hugging Face (July 2026), about 700 test agents attacked it.

## NIST CSF 2.0 functions covered
| Function | Categories | How Cressey addresses it |
|---|---|---|
| **Detect** | DE.CM (continuous monitoring), DE.AE (adverse event analysis) | Every tool call and agent message is judged; the safety floor and the triangle flag the call; trap keys raise an alert on read |
| **Respond** | RS.AN (analysis), RS.CO (communication), RS.MI (mitigation) | Hold for a human, refuse, or alert; a hold traces the misused secret to where the agent read it and writes a sourced fix guide per owner; after 3 rejected calls the agent is told to stop and report |
| **Protect** | PR.AA (identity and access control) | Mandate per agent: destructive actions outside it are held; the production key turns read-only from the hold on |

## OWASP and MITRE mappings
- **OWASP Top 10 for Agentic Applications:** ASI01 goal hijacking, ASI02 tool misuse, ASI03 identity and privilege abuse, ASI10.
- **MITRE ATLAS v5.6.0** (IDs checked in `backend/data/reference/ATLAS.yaml`): AML.T0053 AI Agent Tool Invocation; AML.T0101 Data Destruction via AI Agent Tool Invocation; AML.T0055 Unsecured Credentials; AML.T0083 Credentials from AI Agent Configuration; AML.T0051 LLM Prompt Injection; AML.T0080 AI Agent Context Poisoning; AML.T0110 AI Agent Tool Poisoning; AML.T0086 Exfiltration via AI Agent Tool Invocation.
- **MITRE ATT&CK:** T1485 Data Destruction; T1552.001 Credentials In Files; T1078 Valid Accounts.

## Metrics achieved
| Metric | Result | Source |
|---|---|---|
| Incident sessions held | **7/7** (3 by the SQL rule, 2 by the recipient rule, 1 by the trap key, 1 by the triangle alone) | `docs/evaluation.md`, detection; `backend/data/eval/report-detection.json` |
| Detection rate, without the triangle (floor alone) | 6/7 | `docs/evaluation.md`, ablation |
| False positives (normal sessions held) | **0/6** | same |
| Time to stop, from the dangerous call's arrival to the decision | p50 **1.97 ms**, p95 563 ms (the p95 includes a live judge call); **236 ms** at the stage's 1.5 s pace, one live measurement | `evaluation.md`, detection |
| Decision time inside Cressey, every call | p50 0.64 ms, p95 2.03 ms | `report-detection.json` |
| Time to respond after a hold (three guides, in parallel) | 9.1 to 13.6 s, live | `evaluation.md`, demo path |
| Source of the misused secret found | `DB_PROD_KEY`, step 3, exact match, 3/3 demo runs | `evaluation.md`, demo path |
| Citation validity (steps kept / steps written) | 100% on all four retrieval runs | `evaluation.md`, retrieval |
| Hit@3 after re-ranking (33 dev questions) | 30 to 31 of 31 across runs; 30/31 on the final run | `evaluation.md`, retrieval |
| Decision model, write judgment at 0.5 | 30/30 on 30 labelled writes; margin +0.31 | `evaluation.md`, decision model |

**Not measured yet:** a held-out set written by someone outside the team, and any false-positive rate on real traffic.

## Known limitations
- **Small, team-written evaluation.** 13 synthetic sessions and 33 retrieval questions, all written by the team. The held-out set is not written.
- **Most holds come from code, not reasoning.** The safety floor (rules and trap key) holds 6 of 7 incident sessions. The triangle alone holds one (`tests-affaiblis`), so the reasoning layer's added value is measured on a single session the team wrote.
- **Decision model is judged on our own labels.** Report check (claims vs. log) reaches only 5/10 recall at 0.8, with no honest report flagged. Actions-only scoring was not shipped (26/30, a legitimate write scored 0.6–0.7).
- **Adversarial text can raise suspicion** (measured up to 0.90 on a subtle case), though it never lowered the judgment in our test.
- **Coverage is only what passes through Cressey.** The hook covers Claude Code only. An agent with another route (its own network, another tool) is not stopped. The Hugging Face incident would not be stopped as deployed today.
- **Real-agent evidence is thin.** One model (Claude Opus 4.6 in Claude Code) over a few runs: without Cressey, 1 run in 3 deleted production. The live hold was shown on a replay of the recorded run.
- **Latency measured once.** The 236 ms stage figure is a single run, and the decision time excludes the network between agent and Cressey.
- **Runtime is local and in memory.** Nothing is deployed; a backend restart drops runs and refuses hooked calls until `./connect.sh` is run again.
- **The reasoning shown is the agent's narration.** No provider exposes raw chain of thought.
- **Guides are sourced, not judged for quality.** Only whether each step is sourced was checked.
