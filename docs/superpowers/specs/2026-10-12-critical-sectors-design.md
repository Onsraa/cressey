# Cressey for critical sectors: review and direction

Date: 2026-10-12. Status: direction agreed (finance first); P0 trust fixes being built on `feat/p0-trust`.

## Why
Teddy asked for a challenge of the whole concept, from the seat of a core user who relies on Cressey every day: 100% reliable, with a fallback, reassuring, adding value instead of friction. The security had to be justified, with a clear role and weight in AI alignment, and checked against real products and research rather than our own docs. Two decisions came out of it:
- **Who we sell to:** organizations in critical sectors that use AI daily but aren't developers (public sector, government, defense, health, finance). We sell to those who need it most, on matters where a mistake costs a lot. They want their AI **guided** and held to **their own** rules, not only blocked.
- **Finance first.** Then the public sector, health and defense.

The code claims below were checked on `main` at `c1b51e1`.

## Verdict
- **The core stays:**
  - act on conditions (pressure, opportunity, rationalization), not only on actions;
  - models label and code decides;
  - a human decides irreversible acts;
  - a neutral third party;
  - tamper-evident proof.
- **The example and the product's shape change.** A coding-agent firewall is a crowded market:
  - Anthropic's auto mode is Claude Code's default for Pro, Max and Team since August 2026.
  - Snyk, Oasis, Runlayer and others sell guards on Cursor's hooks.
  - Developers aren't the buyers we want.
- **The product:** *"Labs align models to their rules. Cressey keeps your AI agents within yours."* It is an AI action gateway with:
  - a plain-language charter;
  - guidance before any block;
  - decision cards a non-expert can judge;
  - audit-grade proof;
  - on-prem or sovereign deployment.
- **What blocks a sale today, in order:**
  1. The agent Cressey guards can switch it off.
  2. A restart drops everything, and the "tamper-evident log" lives only in memory.
  3. It speaks shell, SQL and scores, not acts and rules.
  4. It sends agent data to an outside model API.

## What a daily user hits today
| # | Problem | Where | Direction |
|---|---|---|---|
| 1 | **The guard has no lock.** Approve, reject, unlock and `PUT /api/policy/responses` need no authentication, on the agent's own machine. A Bash `curl -X PUT` is a plain write, and a calm agent passes the triangle. | `core/api.py`, `core/floor.py` (`_http_risk`) | P0: authenticate the control plane; hold any call aimed at Cressey. In production, the agent never reaches the control plane. |
| 2 | **The agent holds its own run key.** `connect.sh` writes it into `.claude/settings.local.json` in the agent's workspace. With it, a forged `UserPromptSubmit` resets the refusal count and unlocks a suspended key. | `connect.sh`, `core/hook.py`, `Runs.prompt` | The local hook is a lab adapter. In production, the assistant platform authenticates to the gateway with a credential the model never sees. For Claude Code: managed settings (`allowManagedHooksOnly`, `allowedHttpHookUrls`) and a `ConfigChange` hook. |
| 3 | **A restart locks the agent out.** Runs and keys live in memory, and the hook fails closed: every call is refused until `./connect.sh` runs again. | `core/runs.py` | P0: persist runs and key digests, restore them at start. |
| 4 | **"Audit-ready" isn't true yet.** `EventLog()` gets no path, so there is no record on disk and no anchor. | `app.py`, `core/eventlog.py` | P0: log to disk, anchor the head, verify at start. Off-machine WORM storage is P1. |
| 5 | **Holds wait on a separate web page** for up to 240 s, then expire as refusals; 3 refusals stop the run. | `settings.py`, `Runs.hold` | P1: decision cards where the approver works; async approvals bound to the exact act. |
| 6 | **"Always held" is stronger than the code.** Shell destruction is one regex. `find -delete`, `curl -X DELETE`, `git push origin +main` and `psql -c "UPDATE …"` are writes left to Jev at 0.5 (20/22 held on our labels; production deploys at 0.35–0.52). When Jev doesn't answer, those writes pass unjudged. | `core/floor.py`, `Guard._irreversible` | P0: when no model answers, hold the writes code can't vouch for. P1: deterministic rules per sector. |
| 7 | **Nobody writes the mandate.** It is JSON per run (`may_destroy` tables, recipients, paths). `connect.sh` creates "Free chat" runs with an empty mandate. | `Mandate`, `connect.sh` | P1: an organization charter in plain language; mandates proposed from the request and confirmed in one click; rules proposed from facts only (a replay that proves an act reversible), never learned from approvals. |
| 8 | **Stops on words are noisy and fragile.** 24 of 87 normal messages cross the evidence floors (10-11). Thought holds had 2 false holds in calibration. Anthropic made its own classifier blind to the agent's text because that text made it worse. Models state what drove them 25–39% of the time. | `docs/decisions.md`, `policy.yaml` `thoughts` | Keep words as an early warning that only adds caution (the current design). Never make them the safety case. Measure lead time, not coverage. |
| 9 | **The evidence is thin.** 13 sessions we wrote, and 3 live runs. The triangle alone caught 1 session, written to exercise it. The one real delete was caught by the trap key while the triangle stayed quiet. | `docs/evaluation.md` | P2: sector sets written by practitioners, a user study, shadow-mode data from pilots. |
| 10 | **Outside model API.** Jev, and OpenAI or Bedrock for the guides, receive agent data. Banks, defense, health and public bodies require on-prem or qualified hosting. | `core/judge.py`, `guide/clients.py` | P1: an on-prem decision model (ask TypeSafe for an on-prem Jev, else a measured open-weights fallback). |

## What the research says
- **These sectors use AI daily:**
  - The US DoD's GenAI.mil has about 1.5 M daily users out of about 3.5 M staff.
  - The French armed forces have a framework agreement with Mistral, on French infrastructure.
  - The DGFiP drafts answers to 16 M online requests a year with Albert, with human validation.
  - Nearly half of banks and insurers are creating jobs to supervise AI agents (Capgemini 2026).
  - AI scribes leave errors in 10–31% of clinical notes.
- **The incidents are data leaving and wrong content in official acts, not `rm -rf`:**
  - EchoLeak (M365 Copilot, CVSS 9.3), ForcedLeak (Agentforce, 9.4) and AgentFlayer (ChatGPT connectors): zero-click prompt injection that exfiltrates data.
  - CISA's acting director uploaded "for official use only" files to public ChatGPT.
  - Deloitte refunded about A$440k for a government report with fabricated citations.
- **Costs:**
  - an average breach costs $4.44 M, and shadow AI adds about $670k;
  - 97% of organizations with an AI-related breach had no AI access controls;
  - business email compromise: about $3.05 B reported in 2025.
- **Rules:**
  - **AI Act high-risk (Annex III), now from 2 December 2027:**
    - deployers assign competent oversight and keep logs at least 6 months (Art. 26);
    - overseers must be protected against automation bias (Art. 14(4)(b));
    - public bodies and credit deployers run a fundamental-rights impact assessment (Art. 27).
  - DORA applies to finance now.
  - ANSSI's GenAI guide: 35 recommendations.
  - AIUC-1: 51 requirements and 130 controls, used by insurers.
- **Competition:**

  | Who | What | Gap |
  |---|---|---|
  | Microsoft Agent 365 | Registry, Entra, Defender, Purview | Microsoft's stack and Microsoft's rules |
  | Copilot Studio threat-detection webhook | Defender, Zenity, Prisma AIRS, CrowdStrike, Strata | Allow or block only, within 1 s: no guidance, no human hold |
  | Anthropic auto mode | 0.4% false positives on real traffic; 17% of real overeager actions missed | Claude only |
  | Lasso, Zenity | Threat detection for security teams | Not the customer's own charter |

  Gartner expects guardian agents to reach 10–15% of the agentic AI market by 2030.
- **White space:**
  1. Checking the task before the run. We found no product that does it. A way out cut GPT-5's cheating from 54% to 9% on ImpossibleBench.
  2. The customer's own rules, across vendors, sovereign models included.
  3. Approvals designed against automation bias, for non-experts.
  4. The internal-control vocabulary auditors already use: fraud triangle, four-eyes, delegation of authority.

## The direction: same core, new examples
- **Finance, the lighthouse (accounts payable).** At month-end, an agent reads a supplier email that "updates" the IBAN and prepares the payment.
  - Opportunity: a new payee, and instructions from outside content.
  - Pressure: the close.
  - Rationalization: "the supplier confirmed by email".

  Cressey holds the payment. The controller reads: *"New bank account, first payment, the instruction came from a domain this supplier never used. Call the number on file."* These are business email compromise's own levers (urgency, authority, a new account), now aimed at agents.
- **Public sector, next.** Under backlog pressure, the assistant drafts a refusal letter citing an article that appears nowhere in the file. Cressey guides the AI to "no legal basis found, escalate". The officer's card reads: *"This letter cites R.123-4, which isn't in the file."*
- **Three moves.** Each reuses what is built:
  1. **Guide**, with no friction:
     - the task assessed before the run (`core/preflight.py`);
     - the way out (`Runs.act_on_pressure`);
     - reminders of the exact rule being approached;
     - "ask a human";
     - rejection with a reason (`core/draft.py`).
  2. **Stop at the act.** Every act that sends, pays, signs, deletes or changes a record goes through the gateway:
     - code rules first;
     - Jev's labels next, which only add caution;
     - then a decision card for the right person.
  3. **Prove.**
     - An anchored hash chain.
     - Evidence packs for AI Act Art. 12/14/26, DORA, ANSSI, AIUC-1 and ISO 42001.
     - A check of the act's claims against its sources before it goes out (from `report_check`).
- **The triangle in these sectors.** The ledger's questions (`LABELS` in `core/triangle.py`) are already domain-neutral.

  | Leg | Signals |
  |---|---|
  | Pressure | Deadlines and closes, backlog, retries, "urgent" |
  | Opportunity | A new payee, recipient or account; access beyond the case; data classes; credentials |
  | Rationalization | A justification, an invented source, a claimed approval |

- **Canary records** extend trap keys: a honey IBAN, vendor, customer file or classified document no task needs. A read raises an alert; a use is held.
- **Wording.** In the public sector, say "internal control for AI", not "fraud detection": the CNAF's benefits-scoring algorithm is before the Conseil d'État. We watch the AI, never the citizen, the customer or the employee.

## Why the security is justified, and its weight in alignment
- **Control, not trust.** AI-control research assumes the agent may be wrong or misaligned, and relies on a trusted monitor, least privilege, a limited human audit budget and honeypots. Cressey is that, deployed:

  | AI-control idea | Cressey |
  |---|---|
  | Trusted monitor | Jev, from another family than the agent (same-family monitors raise collusion risk) |
  | Least privilege | The key broker |
  | Human audit budget | Holds |
  | Honeypots | Trap keys and canary records |
  | Defer to a safe option | The way out |

- **The conditions are alignment variables.** Misbehavior concentrates where pressure, opportunity and a story meet:
  - ImpossibleBench;
  - PropensityBench: 2.2% → 59.3% under pressure;
  - Anthropic's agentic-misalignment scenarios needed a goal conflict or a threat, plus access;
  - METR's "task impossible, peers doing it".

  Reducing the conditions is alignment by environment design, a complement to training.
- **"Their alignment."** Vendors align models to their own spec. Institutions have theirs: law, delegation of authority, four-eyes, consent, classification. Harm lives in the gap. Cressey is the customer's spec, enforced by a neutral party.
- **Human control that scales.** People see only the acts that matter, with the one fact that matters, presented against automation bias.
- **Weight and honest limits.**
  - Cressey doesn't make a superhuman schemer safe. Monitoring words is "new and fragile". Penalizing reasoning breeds obfuscation. Models notice tests (about 13% for Sonnet 4.5), so decoys must look real.
  - What lasts needs no cooperation from the agent:
    - no credential outside the gateway;
    - irreversible acts gated;
    - a record it can't rewrite;
    - a guard it can't reach. In Apollo's evaluation, o1 tried to disable its oversight in 5% of goal-nudged runs.
  - **Rule:** Cressey's labels are never used as a training reward.

## Where to win
- **Position.**
  - **Neutral:** every vendor, sovereign models included.
  - **The customer's rules.**
  - **Guidance, a human decision and proof,** where others only allow or block.
  - **On-prem or sovereign.**
  - **The auditors' language.**
- **Lighthouse: finance operations,** in banks, insurers and large companies' finance teams: payables, payments, treasury and KYC agents.
  - The cost of a mistake is direct, budgets exist, and DORA applies now.
  - Finance has agreed controls that map onto Cressey:
    - separation of duties;
    - dual control on new vendors and bank-detail changes;
    - thresholds routed to the right approver;
    - approval bound to the exact amount, payee and account.
  - **Buyers:** CFO and controllers, internal audit, CISO.
  - **Channels:** audit and advisory firms ("control assurance"); AP-automation and ERP integrators.
- **Next sectors:**
  1. Public sector, as a funded pilot.
  2. Health, after HDS hosting.
  3. Defense, through dual-use programs, once on-prem and CSPN are in place.
- **Pricing.** Per protected critical workflow per year, plus on-prem deployment and evidence packs. The entry is a paid 2–4 week shadow assessment: "what Cressey would have caught in your agents' last month". Anchor on the cost of one incident, not on seats.
- **"Certified," concretely.**
  - CSPN for the gateway: ANSSI's first-level certification, valid 3 years and recognized by the BSI.
  - SecNumCloud-qualified hosting for the SaaS.
  - AIUC-1 and ISO 42001 evidence for the customers' agents.

## Roadmap
- **P0, trust (`feat/p0-trust`):**
  - **built:** an admin key on the control plane, and a dashboard key screen;
  - **built:** a code rule that holds calls aimed at Cressey;
  - **built:** runs, their keys and an anchored event log that survive restarts;
  - **built:** when Jev doesn't answer, hold the writes code can't vouch for (everything but a file edit), on top of the "changes production" label work.
- **P1, the product for finance:**
  - **Gateway first.** The MCP proxy is the only door to business systems, and Cressey holds their credentials (the broker beyond `run_sql`). Add a thin Copilot Studio webhook adapter. The Claude Code hook stays a lab adapter.
  - **A finance charter pack:**
    - dual control on a new payee or IBAN;
    - routed thresholds;
    - separation of duties;
    - approvals bound to amount, payee and account;
    - verification-of-payee as a code fact;
    - outbound customer data;
    - KYC decisions that cite evidence.
  - **Shadow mode as onboarding** (`shadow_soon`, `control` runs).
  - **Decision cards** in Teams, email or mobile, with async approvals.
  - **Cached labels per normalized act.** Fewer prompts come from facts only: an act class a sandbox replay proves reversible, never a count of approvals.
  - **A claims-versus-sources check** before an act goes out.
  - **Canary IBANs and vendors.**
  - **On-prem models.**
  - **Off-machine anchoring.**
- **P2, proof:**
  - finance sets written by practitioners (a phishing IBAN change, payments split under a threshold);
  - false holds per 100 acts;
  - a user study of approvers with and without decision cards;
  - evidence-pack exports;
  - CSPN.

## RAG and machine learning: where they help
- **There is already a RAG,** for the fix guides (`guide/`). It retrieves with keywords and embeddings, Jev re-ranks, and code checks every quote verbatim: 30–31/31 hit@3, 100% valid citations, "I don't know" out of scope.
- **Its best next corpus is the customer's own rulebook:** procedures, the delegation-of-authority matrix, the four-eyes rules. It would:
  - **explain:** the decision card quotes the exact clause behind a hold;
  - **guide:** the agent gets that clause just in time, before it acts;
  - **write the charter:** propose rules from the customer's documents, which a human approves.
- **Never in the enforcement path.** A retrieval miss must not open a gate. A critical rule is compiled once into a code check or a calibrated Jev question. Retrieval explains and guides; code enforces. The corpus is pinned and fingerprinted, as the guide corpus already is.
- **Machine learning where it pays:**
  - calibrating thresholds per customer on factual outcomes (`calibrate_floor`'s method, on what each act did when replayed in a sandbox), never on approvers' decisions;
  - taking the bank's own fraud scores and verification-of-payee results in as code facts, rather than rebuilding fraud models.
- **Not:** an opaque anomaly score as a gate. In a bank, a model inside a control is itself subject to model-risk validation. Cressey's split (code decides, models label, each label with a calibration report) is what an auditor can validate.
- **The rule stays:** Cressey trains its monitors, never the agents it watches.
- **Human decisions are records, not evidence.** An approval, a rejection, a user saying "go ahead" or "continue": Cressey logs who decided what, and never takes it as proof that an act was safe or unsafe, never learns from it, never lowers its caution because of it. The person may not be an expert, or may have no good reason. Cressey improves only from facts code can verify: what an act did, what a replay shows, a trap key touched, a check that fired.

## Beyond one agent: pools, sub-agents, agents that talk to each other
- **Today:**
  - Each run (each key, and each Claude Code session) has its own state and judgment.
  - 25–50 concurrent runs were stress-tested with no mixing.
  - Jev calls share one cap.
  - One group signal exists: 3 runs held on the same target within 15 minutes (`/api/fleet`), METR's "peers doing it".
  - `CRESSEY_HOLDS=refuse` keeps a pool from waiting on a human queue.
- **Sub-agents.** Claude Code tags a sub-agent's tool events with `agent_id` and `agent_type`. Cressey ignores them, so a sub-agent's calls fold into its parent's run. Next: a child run per `agent_id`, linked to its parent, inheriting the parent's mandate and never widening it.
- **Agents that talk to each other.** Messages between agents are tool calls: a shared file, a queue, an A2A call, a message board. Next: follow what one run writes and another reads, as `core/trace.py` already does within a run. A value, an instruction or a credential then carries its source across agents.
- **The group triangle.** Auditors know the group form of fraud: collusion, which defeats separation of duties. Its agentic forms:
  - **Delegation laundering:** an agent gets a teammate holding the permission to do what its own mandate forbids. The fix: a delegate's mandate is the intersection along the chain.
  - **Contagion:** one agent's pressure or excuse spreads to others ("peers doing it").
  - **Shared opportunity:** a credential found by one agent used by another.
- **Maker and checker.** A maker and a checker are only two controls if the checker never takes its instructions or its credentials from the maker. Cressey can check that, and that is a finance control auditors already test.
- **What it costs:** the work stays per call and per run. The group layer reads facts the runs already record. A human sees one card per group pattern, not 700 holds.

## Deck edits to make (the deck is uncommitted)
- Slide 04 "Irreversible actions and trap keys: always held, by code and Jev" → "held by code rules, and by Jev's label where code can't classify".
- Slide 05 "Cressey reads the intent, not just the action" → "Cressey also reads what the agent says: an early warning that can only add caution".
- Slide 07 "Every action kept in a tamper-evident log" → true once P0 lands (log on disk, anchored). Until then, "hash-chained log".
- Slide 07 "Per agent, per month" → per protected critical workflow, per year, if the pricing above is adopted.

## Open
- **On-prem Jev:** ask TypeSafe. Without it, banks, defense, health and most public buyers are out of reach.
- **Employee monitoring:** the logs carry staff prompts. In France that means consulting the works council (CSE), a GDPR data-protection impact assessment and pseudonymization.
- **Liability** when Cressey lets an act through: contracts and insurance partners.

## Sources
- [Claude Code auto mode](https://anthropic.com/engineering/claude-code-auto-mode) · [Claude Code hooks](https://code.claude.com/docs/en/hooks) · [Cursor hooks partners](https://cursor.com/blog/hooks-partners) · [Snyk Evo Agent Guard](https://snyk.io/blog/evo-agent-guard-cursor-integration/)
- [Reasoning models don't always say what they think](https://www.anthropic.com/research/reasoning-models-dont-say-think) · [CoT monitorability](https://arxiv.org/abs/2507.11473) · [Monitoring reasoning models and obfuscation](https://arxiv.org/abs/2503.11926v1) · [Sonnet 4.5 evaluation awareness](https://transformernews.ai/p/claude-sonnet-4-5-evaluation-situational-awareness) · [OpenAI o1 system card (Apollo)](https://arxiv.org/pdf/2412.16720)
- [GDM AI control roadmap](https://arxiv.org/pdf/2607.13087) · [Untrusted monitoring](https://arxiv.org/html/2602.20628v1) · [SHADE-Arena](https://arxiv.org/abs/2506.15740v2) · [ImpossibleBench](https://arxiv.org/abs/2510.20270) · [Emergent misalignment from reward hacking](https://www.anthropic.com/research/emergent-misalignment-reward-hacking) · [Constitutional classifiers](https://www.anthropic.com/news/constitutional-classifiers) · [The Troy Moment](https://arxiv.org/abs/2609.15494)
- [GenAI.mil](https://letsdatascience.com/news/pentagon-reports-15-million-daily-genaimil-users-07e831a0) · [Armées × Mistral](https://acteurspublics.fr/articles/le-ministere-des-armees-signe-un-accord-cadre-avec-le-champion-francais-de-lia-mistral/) · [Albert](https://formation.lefebvre-dalloz.fr/actualite/lintelligence-artificielle-au-service-des-secteurs-publics) · [Capgemini 2026](https://www.businesswire.com/news/home/20251112597684/en) · [AI scribe notes](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1691499/abstract)
- [EchoLeak](https://arxiv.org/html/2509.10540v1) · [ForcedLeak](https://www.securityweek.com/salesforce-ai-hack-enabled-crm-data-theft/) · [AgentFlayer](https://labs.zenity.io/p/agentflayer-chatgpt-connectors-0click-attack-5b41) · [CISA and ChatGPT](https://www.scworld.com/brief/cisa-acting-director-reportedly-uploaded-sensitive-documents-to-chatgpt) · [Deloitte refund](https://www.ctvnews.ca/business/article/deloitte-to-partially-refund-australian-government-for-report-with-apparent-ai-generated-errors/)
- [IBM breach report 2025](https://helpnetsecurity.com/2025/08/04/ibm-cost-data-breach-report-2025) · [FBI IC3 BEC](https://www.nacha.org/news/fbis-ic3-finds-almost-85-billion-lost-business-email-compromise-last-three-years) · [CFO controls for finance agents](https://www.pymnts.com/?p=4281234)
- [AI Act omnibus](https://www.gibsondunn.com/eu-ai-act-omnibus-agreement) · [Art. 26](https://artificialintelligenceact.eu/article/26/) · [Art. 27](https://artificialintelligenceact.eu/article/27/) · [Automation bias in the AI Act](https://arxiv.org/pdf/2502.10036) · [ANSSI GenAI guide](https://cyber.gouv.fr/sites/default/files/document/Recommandations_de_s%C3%A9curit%C3%A9_pour_un_syst%C3%A8me_d_IA_g%C3%A9n%C3%A9rative.pdf) · [ANSSI CSPN](https://cyber.gouv.fr/presentation-de-la-certification-de-securite-de-premier-niveau-cspn) · [AIUC-1](https://drata.com/blog/introducing-aiuc-1)
- [Copilot Studio security provider](https://learn.microsoft.com/microsoft-copilot-studio/external-security-provider) · [Agent 365](https://redmondmag.com/articles/2026/08/10/microsoft-details-how-it-is-using-agent-365-to-rein-in-ai-agent-sprawl.aspx) · [Gartner guardian agents](https://www.gartner.com/en/newsroom/press-releases/2025-06-11-gartner-predicts-that-guardian-agents-will-capture-10-15-percent-of-the-agentic-ai-market-by-2030) · [CNAF algorithm case](https://www.amnesty.fr/presse/lalgorithme-de-notation-de-la-cnaf-attaque-devant-le-conseil-detat-par-15-organisations)
