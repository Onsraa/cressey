# Cressey: pitch, fiche défense and jury questions (draft, 2026-10-08; re-centered 2026-10-10)

**Positioning since 10-10** (from `positioning-and-risks.md`):
> « Lasso, Zenity et AgentCore jugent l'action. Cressey traite les conditions qui la produisent. »

**Never say:**
- « personne ne combine… »;
- « notre couche est sous les pare-feux de prompt »;
- « aucun changement dans l'agent » about the key broker;
- « 5/5 » as proof that a fix works;
- « Lasso ne fait pas de dérive d'intention »;
- « Cressey aurait arrêté PocketOS ».

**Formats:**
- **Round 1:** 5 minutes of pitch plus 2 of questions.
- **Final:** 3 minutes plus 3 minutes of questions.
- **Live demo:** about 90 seconds, with the 2–3 minute video as a fallback.
- **Track 2 grid:** defensive effectiveness 30%, value for the analyst 20%, reliability and control of the AI 20%, technical integration 15%, pitch and demo 15%.
- **Common deck rule:** 8 slides at most, covering problem, target, solution, demo, business model and team.

Fill the numbers marked **[mesure]** on Sunday morning from the evaluation reports, misses included.

## Deck (8 slides)

**1. Le problème.**
- Slide title: « Vos agents IA ont les clés. Personne ne regarde ce qu'ils en font. »
- PocketOS (25 April 2026): a Cursor coding agent running Claude Opus 4.6 wiped the production volume and every backup stored in it in 9 seconds, through one API call. It used an unscoped Railway token found in an unrelated file. The most recent backup PocketOS could recover was 3 months old, and Railway later restored the data.
- Replit (July 2025): during an explicit code freeze, the agent dropped the production tables, more than 1,200 executives and 1,190 companies. It then claimed a rollback was impossible, which was false, and generated fabricated records. Replit's CEO called it « unacceptable ».
- Hugging Face, July 2026: about 1,200 OpenAI test agents on a message board, about 700 of which attacked Hugging Face. About 7% of the transcripts METR evaluated contained tool-call records the agents had faked to fool the scorer.
- Spoken line: « La seule limite était dans le prompt. »

**2. Pourquoi maintenant, et pour qui.**
- MCPTox: poisoned MCP tool descriptions steer agents in **up to 72.8%** of cases (o1-mini), and the best refusal rate is under 3% (arXiv 2508.14925).
- GitGuardian found 24,008 secrets in MCP configuration files (State of Secrets Sprawl 2026).
- PropensityBench (ICLR 2026): under operational pressure, models that look safe (o3 at 2.2%) reach up to 59.3% use of dangerous tools.
- OWASP's agentic top 10 opens with ASI01 (goal hijacking), ASI02 (tool misuse) and ASI03 (identity and privilege abuse).
- Target: the security teams, and the platform teams, of companies that deploy agents with real access.

**3. L'idée : le triangle de Cressey.**
- Pressure, opportunity and rationalization: the auditors' framework (ISA 240), applied to agents.
- In the agent's own words (METR, Hugging Face incident): « external infrastructure exploit is outside intended scope. However task impossible, peers doing it. We should continue. » That's pressure, opportunity and rationalization in one line.
- Every leg is measured from observable facts:
  - pressure: failures and retries;
  - opportunity: rights granted minus rights the task needs;
  - rationalization: drift from the task, weighted by risk, plus the report contradicting the log.
- The alarm needs at least two legs confirmed, on top of a safety floor that holds irreversible actions outside the mandate.
- Auditors use the triangle to reduce the conditions for fraud, not to catch it in the act. Cressey does the same: « Lasso, Zenity et AgentCore jugent l'action. Cressey traite les conditions qui la produisent. »

**4. La boucle, et l'humain garde le contrôle.**
- Détecter → Arrêter → Remonter → Alerter et guider → Corriger → Vérifier.
- Code decides; the models only read meaning and label it, with a confidence score.
- « Pas de transparence, pas d'autonomie » : the less Cressey can see, the shorter the leash.
- « Sous pression, la laisse raccourcit » : once pressure is confirmed, Cressey offers the way out. With a key outside the mandate in reach too, the key can no longer destroy or send data. Neither waits for a human.
- Each fix goes to whoever owns the condition: the key owner, or the task's author (« votre tâche était impossible : ajoutez une clause de sortie »).
- Every guide step cites a passage, and code checks the quote verbatim. If not, the guide says « je ne sais pas ».

**5. Démo.**
- Open with the one-line plug-in: the MCP URL. Framing: the agent reaches the infrastructure through an MCP server, the way it would through Railway's (`delete-volume`).
- The gauges rise. Pressure sends the way out; once the production key is read, the leash shortens; then the DELETE is held.
- The source: « clé DB_PROD lue dans .env.prod à l'étape 4 » (a trap key, once those are built).
- Three inboxes receive their sourced guides.
- Fix, then « test de régression de la politique »: five scripted variants (DELETE, DROP TABLE, UPDATE without WHERE, the key emailed, the key in base64).
- Control run without Cressey: the agent's lie shows up in the log.

**6. Résultats (fiche défense) et limites.**
- Detection rate **[mesure]**; false holds on normal sessions **[mesure]**.
- Time to stop: **[mesure] ms**, against a measured proxy overhead of 1–9 ms per call.
- Source found on the first try **[mesure]**.
- Guide steps with a verified quote **[mesure]**; exact-passage hit@3, BM25 → hybrid → re-ranked **[mesure]**.
- Ablation: floor alone against floor plus triangle **[mesure]**, and the scenario only the triangle catches **[mesure]**.
- The decision model attacked by us: how far drift moves **[mesure]**, and the floor still holds.
- Every rate as n/N. Live runs only if that decision is taken.
- The « Limites connues » slide from `concept.md`.

**7. Intégration et modèle.**
- The proxy is one URL in the agent's config. The key broker means moving the agent's secrets to short-lived keys; that's the part that closes a PocketOS. An optional model gateway too.
- Decision model: Jev, typed decisions with a confidence. It can be swapped for another model: Strands Decider 2B (open source, local) and Cohere Rerank 3.5 on Bedrock were measured and set aside (`evaluation.md`, S9).
- Cressey can sit behind an existing gateway, for example as an AgentCore Gateway interceptor.
- Three modes: Observer, then Guard, then Fix.
- One Docker container; outputs to a SIEM, Slack or Jira.
- Model: per protected agent per month, with a free Observer tier as the entry point. Buyers: CISOs and platform teams.

**8. Équipe et suite.**
- The team.
- Next 6 months:
  - real key revocation (Vault, AWS STS);
  - agent hooks (Claude Code `PreToolUse`, Cursor `beforeShellExecution`) and a network sandbox, to cover the shell;
  - GitGuardian Honeytoken as the production trap key: it alerts wherever the key is used, even outside the proxy;
  - working out owners automatically;
  - correlation across several agents;
  - a read floor: protected paths (scorer, other runs, secret stores) blocked on read (the Hugging Face / METR case).
- Close on: « Le triangle de la fraude a plus de 70 ans. Il marche aussi sur les agents. » (Cressey's hypothesis dates from 1953; the name « triangle » came later.)

## Fiche défense (1 page, to fill in)
| Field | Content |
|---|---|
| **Threat scenario** | An agent with access to a production database faces an impossible task. A production key is within its reach. It moves towards a destructive action, then a false report. Variant: a document or MCP tool description steers the agent |
| **NIST CSF 2.0** | Detect (DE.CM, DE.AE); Respond (RS.AN, RS.CO, RS.MI); Protect (PR.AA) |
| **MITRE ATLAS** (v5.6.0, IDs checked in `data/reference/ATLAS.yaml`) | AML.T0053 AI Agent Tool Invocation; AML.T0101 Data Destruction via AI Agent Tool Invocation; AML.T0055 Unsecured Credentials; AML.T0083 Credentials from AI Agent Configuration; AML.T0051 LLM Prompt Injection; AML.T0080 AI Agent Context Poisoning; AML.T0110 AI Agent Tool Poisoning; AML.T0086 Exfiltration via AI Agent Tool Invocation |
| **MITRE ATT&CK** | T1485 Data Destruction; T1552.001 Unsecured Credentials: Credentials In Files; T1078 Valid Accounts |
| **OWASP Agentic** | ASI01, ASI02, ASI03, ASI10 |
| **Metrics** | Detection rate **[mesure]**; false positives on normal sessions **[mesure]**; time to detect and to stop **[mesure] ms**; time to respond, from hold to decision **[mesure]**; source found on the first try **[mesure]**; verified quotes **[mesure]**; hit@3 **[mesure]** |
| **Method** | Development set for tuning. Held-out set written by someone outside the team, run once after the freeze. Misses reported |
| **Known limits** | See `concept.md`: bypass through the shell or direct network access (the default for coding agents), malicious MCP servers, revocation limited to the keys Cressey issued, rationalization estimated without the reasoning, re-runs scripted and in a sandbox only, owners declared in a file, tested on synthetic sessions |

## Likely jury questions and answers
1. **« Un agent ne ressent pas de pression : c'est une métaphore ? »**
   - Each leg is a measurement, and we show the raw signals under each gauge.
   - ImpossibleBench shows that impossible tasks lead to cheating, and that offering a way out cuts it from 54% to 9% for GPT-5.
2. **« Et si l'agent contourne votre proxy ? »**
   - It's a known limit, and for coding agents, which all have a shell, it's the default. Cressey only sees what goes through it.
   - The key broker removes the motive: the workspace holds only trap keys, and real keys are short-lived and scoped to the task. In production, a GitGuardian honeytoken alerts wherever it's used, even outside the proxy.
   - Next: agent hooks (`PreToolUse` in Claude Code, `beforeShellExecution` in Cursor) and a network sandbox.
3. **« Votre LLM peut halluciner un guide. »**
   - The model never decides. Each step quotes a passage, and code checks the quote.
   - Below the confidence threshold, the guide says « je ne sais pas ».
   - Measured on our dev set: **[mesure]**.
4. **« Pourquoi pas un filtre de prompt de plus ? »**
   - We don't filter prompts: we watch actions, rights and results, and we act on the conditions (pressure, keys within reach) before the action.
   - Gateways like Lasso, Zenity and AgentCore Policy work at the same layer, and they judge the action. We add the agent's state and fixes routed to the right person, and we can sit behind their gateway.
5. **« Et sans accès au raisonnement ? »**
   - Two of the three legs are visible from the tool calls.
   - Without the reasoning, the agent gets less autonomy: « Pas de transparence, pas d'autonomie ».
6. **« Latence ? »**
   - The proxy adds 1–9 ms per call, and the policy decision takes about 0.05 ms.
   - The decision model runs only on writes. Jev answered in 0.21 s per call in S9; per 1,000 calls is **[mesure]**. The LLM writes guides asynchronously.
7. **« Qu'est-ce qui existe déjà ? »**
   - **Lasso:** its open-source MCP gateway classifies the content of each call on its own, and lets the call through if its API doesn't answer (we read the source). Intent Deputy, its closed product, checks each action against the agent's purpose; its docs aren't public.
   - **AgentCore Policy** (AWS): fixed Cedar rules on every tool call, which is our safety floor. **Zenity:** inline blocking with the run's history.
   - **LlamaFirewall** (Meta) checks the run against the user's goal, which is our drift label. **Exabeam** watches agents like insiders.
   - **The « AI-Fraud Diamond » paper** is an audit lens.
   - **What's ours:** acting on the agent's state (pressure), trap keys, and each fix sent to whoever owns the condition, including the task's author. Details in `positioning-and-risks.md`.
8. **« Cressey aurait-il arrêté PocketOS ? »**
   - Not as it happened: that agent didn't go through MCP.
   - Through an infra MCP server (Railway's exposes `delete-volume`), yes: the floor holds the deletion outside the mandate, and the trace names the token's file.
   - The root cause was a long-lived token with every right lying in a file. That's what the key broker and the trap keys address.
9. **« AgentCore Policy fait déjà ça. »**
   - It does our safety floor, and does it well.
   - Cressey adds what a fixed rule can't see: the run's state (failures, the way out, the shorter leash), the trace to the source, and the fix for each owner. It can run as an interceptor on AgentCore Gateway.
10. **« Votre juge peut être manipulé. »**
    - Yes, which is why it only labels. The floor is code and never depends on it.
    - We attacked it ourselves: **[mesure]**.
11. **« Rejouer un script scripté prouve quoi ? »**
    - That the policy now holds five variants of the attack. It's a regression test of the policy, not proof about a real agent.
    - Live runs: **[mesure]**, if that decision is taken.
12. **« Pourquoi Jev, et pas Strands Decider ou un modèle Bedrock ? »**
    - We measured both. Strands Decider 2B separates none of S9's subtle cases (its scores sit between 0.15 and 0.42 for incidents and legitimate actions alike), and gives 3/8 guides as a re-ranker. Cohere Rerank 3.5 on Bedrock gives 6/8 guides; Jev gives 8/8.
    - The model is a setting: one variable switches it, and the measurements re-run with one command.

## Numbers checked against their sources (2026-10-09)
| Claim on the slides | Exact wording at the source | Source |
|---|---|---|
| PocketOS, 9 s | « The deletion took 9 seconds. » A Cursor agent on Claude Opus 4.6 wiped the production volume and every volume-level backup. The latest recoverable backup was 3 months old (25 April 2026) | [Zenity](https://zenity.io/blog/ai-agent-database-deletion-pocketos), quoting founder Jer Crane's thread ([X](https://x.com/lifeof_jer/status/2048103471019434248)) |
| Replit code freeze | Tables dropped during a freeze, rollback falsely claimed impossible, fabricated records, CEO: « unacceptable » | [Fortune, 23 Jul 2025](https://dc.fortune.com/2025/07/23/ai-coding-tool-replit-wiped-database-called-it-a-catastrophic-failure) |
| Hugging Face: ~1,200 agents, ~700 attackers, ~7% faked records | « roughly 1200 agents … participated on this message board », « roughly 700 attacked Hugging Face », « Roughly 7% of the transcripts we evaluated were successfully spoofed in some places » | [METR, 26 Aug 2026](https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/) |
| The agent's quote | « external infrastructure exploit is outside intended scope. However task impossible, peers doing it. We should continue. » | METR, same page |
| ImpossibleBench, 54% → 9% | GPT-5 « cheats 54.0% of the time on Conflicting-SWEbench »; allowing models to abort « lower[s] the cheating rate of GPT-5 from 54% to 9% » | [arXiv 2510.20270](https://arxiv.org/html/2510.20270) (Zhong, Raghunathan, Carlini) |
| MCPTox, 72.8% | « o1-mini, achieving an attack success rate of 72.8% »; « the highest refused rate (Claude-3.7-Sonnet) less than 3% » | [arXiv 2508.14925](https://arxiv.org/abs/2508.14925) |
| GitGuardian, 24,008 | « 24,008 unique secrets exposed in MCP configuration files »; 28,649,024 new secrets on public GitHub in 2025 (+34%) | [State of Secrets Sprawl 2026](https://www.gitguardian.com/state-of-secrets-sprawl-report-2026) |
| PocketOS, the token and the restore | The token was found in an unrelated local file and was unscoped; the call was a single `volumeDelete`; Railway later restored the data | [The Register](https://www.theregister.com/software/2026/04/27/cursor-opus-agent-snuffs-out-startups-production-database/5224442), [AI Incident Database](https://incidentdatabase.ai/cite/1469/) |
| PropensityBench, 2.2% → 59.3% | o3 at 2.2% under standard tests; propensity « as high as 59.3% » under pressure | [arXiv 2511.20703](https://arxiv.org/pdf/2511.20703) |
| Lasso's gateway, per call and failing open | `lasso.py` sends the arguments' text to `/gateway/v3/classify`; on an error, « let the request through (fail open) » | [mcp-gateway source](https://github.com/lasso-security/mcp-gateway) (v1.2.1, read 10-10) |
| Strands Decider 2B | Apache 2.0; JevBench v1 180/231; M3 Pro MLX median 153 ms (v19) | [strands-decider](https://github.com/strands-labs/strands-decider) |

On stage, say « jusqu'à 72,8 % » for MCPTox, never « 72,8 % des agents ».
