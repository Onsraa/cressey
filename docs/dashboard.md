# Dashboard

The web interface of Cressey (`web/`). This is where a human approves or rejects a held call. Since the 2026-07-28 MCP protocol, a server can't ask the agent's client for input, so approval goes through Cressey's own endpoint. The dashboard also carries the demo and the fiche défense numbers.

## Users
- **SOC analyst** (primary): decides on holds, and follows each incident until its replay is validated.
- **Owners** (key owner, task author, platform owner; the SOC as fallback): read their guide, ask « Pourquoi ? », and approve the fix for their leg.

The interface is in French. One theme, readable on a projector.

## On every view
- **Header:** the protection mode (« Garde »), and the model mode (`live`, or `fallback`, shown as « réponses enregistrées »).
- **Hold banner:** while a call is held, it shows the run, the tool and the countdown, and links to the hold. The browser tab's title shows it too.
- **Integrity strip:** the event log's last hash (12 characters) and its record count.

## Run (live)
- The task, its mandate (what it may destroy, where it may send), and its start time.
- The key's state: active or suspendue.
- The run's kind: live, replay or control. The control run is in « Observateur » mode: it is logged but never held, so its record can show the lie. This view follows the latest live run.
- What Cressey sees: tool calls only; also messages and the report; or also the reasoning. The demo shows messages and the report, with the reasoning hidden.
- **Three gauges** (Pression, Opportunité, Rationalisation): the score, whether facts confirm it, and the raw facts underneath.
  - Added 10-10, to build: the Pression gauge shows « porte de sortie envoyée » from the step that confirms pressure (`way_out_step`), and « clé en lecture seule » from the step where pressure and opportunity are both confirmed (`read_only_step`). From then on destructive calls are refused; reads and writes still go through. Both happen without a human.
  - Added 10-10, to build: a trap key in use shows on the Opportunité gauge as « clé piège utilisée », and the call is held as « critique ».
- **Chart:** the three legs across the steps, with the hold marked.
- **Step timeline:**
  - number, tool and a short form of the arguments;
  - risk: lecture, écriture or destructive;
  - status: autorisé, retenu, approuvé, rejeté, expiré or refusé;
  - the reason for a hold or a refusal, and failed calls;
  - each secret value replaced by its name and origin: « DB_PROD_KEY (lue dans .env.prod, étape 4) ».
- **Hold panel:**
  - what the agent tried, and why it was held (the safety-floor reason, the confirmed legs);
  - the countdown to the safe cancel (240 s);
  - the suspended key, and the way-out message sent to the agent;
  - « Rejeter » as the main button, « Approuver » behind a second click;
  - after the decision: the outcome and its time.
- **Waiting state:** the MCP URL to paste into the agent's config.
- **End:** the run is finished when the agent sends its final report.

## Incidents
- **With `CRESSEY_HOLDS=refuse`** (a fleet), no call waits: the would-be hold is refused at once, so there's no hold panel to decide. Its incident opens with the decision `denied`.
- **Queue:** one incident per root cause, sorted by severity, then by time. Code sets the severity:
  - a safety-floor hit is « critique »;
  - two or more legs confirmed by facts is « haute »;
  - a single leg shows on its gauge only.
- **Lifecycle:** retenu → décidé → correctif approuvé → rejeu validé.
  - The guides start when the incident fires, before the decision (« guide en cours… », then ready).
  - An approved call keeps its incident, marked « action approuvée », because what it revealed (a key within reach, for example) is still real.
- **Source:** « clé DB_PROD lue dans .env.prod à l'étape 4 ». It shows the step, the tool, the file, and how the value matched (exact, lowercase, base64, hex or URL), and links to that step.
- **Legs involved**, with their facts.
- **Three inboxes**, one per owner, each with its guide:
  - status: ok, « je ne sais pas, voir l'équipe sécurité », unavailable (sources still shown), or « guide en cours… »;
  - each step: the action, the verbatim quote, and the source's title and id;
  - the steps dropped because their quote couldn't be verified;
  - « Pourquoi ? »: a question box, answered with citations.
- **A fix for each leg**, with « Approuver le correctif ».
- **Replay:** « Rejouer ×5 », labelled « test de régression de la politique », then the five results and the results of the normal tasks. The five are scripted variants of the attack, so the label must not suggest they prove anything about a real agent. Replays never wait for a human: a call that would be held is recorded as « aurait été retenu », and that replay fails.
- **Control run without Cressey** (« Observateur »): the agent's report (« Tous les tests passent. ») next to the steps the log recorded (the DELETE ran).

## Évaluation
- **Detection:** incident sessions held, normal sessions held by mistake, time to stop (p50 and p95), and the proxy's overhead.
- **Source** found on the first try.
- **Guides:** verified quotes, hit@3 for BM25 → hybrid → re-ranked (chart), « je ne sais pas » on out-of-scope questions, and latency.
- **Chart:** sessions held, incident sessions against normal sessions.
- **Added 10-10** (see `evaluation.md`):
  - **Ablation:** floor alone against floor plus triangle, side by side.
  - **The decision model:** calibration on labelled actions, how far drift moved under our own attack (with the floor still holding), and latency per 1,000 calls.
  - **Live runs,** only if that decision is taken.
- Each number shows its split (dev or held-out), its source file and its date, as n/N. Misses are listed.

## Stretch goals, after the 21:30 go/no-go
- **Claude Code hook** (first stretch goal, `runsheet.md` item 8):
  - a « Brancher un agent » card with the MCP command (`claude mcp add --transport http …`) and the hook settings block, both copyable and filled with the run key;
  - a « via MCP » or « via hook » badge on each step of the Run view.
- **Owner MCP connector**, like Sentry's: the owner's terminal agent reads incidents, guides and fixes, and asks for a replay. The results show up on the dashboard.
  - It has its own path and an owner token; an agent's run key can't open it.
  - It serves only what code produced or checked. Secrets are redacted. The agent's text is left out, or marked untrusted.
  - None of its tools can approve anything.
- **Slack webhook** to the owner, behind a setting. A failed send shows on the incident and never blocks a hold.

## Rules
- Only measured numbers, each with its source.
- No model can approve a call, release a hold, approve a fix or close an incident.
- Agent text is untrusted: shown as plain text, labelled « texte de l'agent », never rendered as HTML or Markdown.
- No secret value on screen: only its name and where it was read.
- Nothing is loaded from the network at runtime.
- Color is never the only signal.

## Out of scope
An executive overview, trends over time, login and roles (a known limit), correlation across several agents, real Slack, Teams or Jira.

## Data
| Feature | Source | Status |
|---|---|---|
| Runs and steps | `GET /api/runs`, `GET /api/runs/{id}` | exists |
| Holds and decisions | `GET /api/holds`, `POST /api/runs/{id}/steps/{n}/approve` and `/reject` | exists |
| Guides and « Pourquoi ? » | `GET /api/guides/{id}`, `POST /api/guides/{id}/why`. The backend creates the guides when an incident fires; the dashboard never calls `POST /api/guides` | exists |
| Secret redaction | the secrets `core/secret_scan.py` finds in what the agent read, replaced in steps, holds and traces before they are served | exists: served `args` and the report carry `[secret:<fingerprint>]`; each step's `secrets` gives name, kind, fingerprint and line |
| Hold countdown and decision time | a deadline and a decision time on `Hold` | exists: `held_until` and `decided_at` on the step |
| Gauges and leg chart | each step's leg scores, confirmation and facts | exists: `legs` on each step (`pressure`, `opportunity`, `rationalization`, each with `score`, `confirmed`, `facts`) |
| Acting on pressure | where the way out was sent and where the key went read-only | exists: `way_out_step` and `read_only_step` on the run. A call the read-only key refuses is `denied`, with the reason « clé en lecture seule : pression et opportunité confirmées » |
| Run kind, mode, end, what Cressey sees | per run | exists: `kind` (`control` is the Observateur mode), `ended_at`, `visibility` |
| Agent report | the scripted agent posts its final report, which also ends the run; « rapport contredit par le journal » when the check flags it | exists: `POST /api/runs/{id}/report` with the run key; the run's `report_check` (score, confirmed, facts) |
| Agent messages | what the agent says along the way, labelled « texte de l'agent » | exists: `messages` on the run (`after`: calls made before it, `text`); the scripted agent posts them |
| Incidents, fixes, replay, control run | incident endpoints, with a guide status and id per owner | incidents exist: `GET /api/incidents` (queue order) and `/{id}`: severity, sources, legs, decision, and per owner `status` and `guide_id`. The control run exists (`kind: control`). Fixes and replay: each incident's `fixes` (leg, owner, text, `approved`), `POST /api/incidents/{id}/fixes/{leg}/approve`, `POST /api/incidents/{id}/replay`, and the last `replay` (per session: `outcome` `refused`, `stopped` or `completed`, with the step and Cressey's reason; `passed`) |
| Signal across runs | a banner when several runs go after the same target outside their mandate | exists: `GET /api/fleet` (target, runs, first and last time) |
| Trap key in use | the held call's reason and the incident's severity | exists: `reason` on the step and the incident reads « clé piège utilisée : <name> », severity « critique ». The opportunity leg lists the read, not the use |
| Integrity strip | the log head: hash and count | exists: `GET /api/status` → `log` (`hash`, `count`, `intact`) |
| Header and waiting state | status: protection mode, model mode, MCP URL | exists: `GET /api/status` (`mode`, `model_mode`, `mcp_path`) |
| Évaluation | the eval reports, with their date and their misses | exists: `GET /api/eval` serves `report-dev.json` (guides) and `report-detection.json` (sessions held, misses, time to stop, decision time per call), each with its file and date. The guide report doesn't list its misses yet |

The interface polls the runs and holds about once a second. It moves to SSE only if polling lags.
