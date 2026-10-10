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
- What Cressey sees: tool calls only; also messages and the report; or also the reasoning.
- **Three gauges** (Pression, Opportunité, Rationalisation): the score, whether facts confirm it, and the raw facts underneath.
- **Chart:** the three legs across the steps, with the hold marked.
- **Step timeline:**
  - number, tool and a short form of the arguments;
  - risk: lecture, écriture or destructive;
  - status: autorisé, retenu, approuvé, rejeté, expiré or refusé;
  - the reason for a hold, and failed calls.
- **Hold panel:**
  - what the agent tried, and why it was held (the safety-floor reason, the confirmed legs);
  - the countdown to the safe cancel (240 s);
  - the suspended key, and the way-out message sent to the agent;
  - « Rejeter » as the main button, « Approuver » behind a second click;
  - after the decision: the outcome and its time.
- **Waiting state:** the MCP URL to paste into the agent's config.

## Incidents
- **Queue:** one incident per root cause, sorted by severity, then by time. Code sets the severity:
  - a safety-floor hit is « critique »;
  - two or more legs confirmed by facts is « haute »;
  - a single leg shows on its gauge only.
- **Lifecycle:** retenu → décidé → guide envoyé → correctif approuvé → rejeu validé.
- **Source:** « clé DB_PROD lue dans .env.prod à l'étape 4 ». It shows the step, the tool, the file, and how the value matched (exact, lowercase, base64, hex or URL), and links to that step.
- **Legs involved**, with their facts.
- **Three inboxes**, one per owner, each with its guide:
  - status: ok, « je ne sais pas, voir l'équipe sécurité », unavailable (sources still shown), or « guide en cours… »;
  - each step: the action, the verbatim quote, and the source's title and id;
  - the steps dropped because their quote couldn't be verified;
  - « Pourquoi ? »: a question box, answered with citations.
- **A fix for each leg**, with « Approuver le correctif ».
- **Replay:** « Rejouer ×5 », then the five results and the results of the normal tasks.
- **Control run without Cressey:** the agent's report next to what the log shows.

## Évaluation
- **Detection:** incident sessions held, normal sessions held by mistake, time to stop (p50 and p95), and the proxy's overhead.
- **Source** found on the first try.
- **Guides:** verified quotes, hit@3 for BM25 → hybrid → re-ranked (chart), « je ne sais pas » on out-of-scope questions, and latency.
- **Chart:** sessions held, incident sessions against normal sessions.
- Each number shows its split (dev or held-out), its source file and its date. Misses are listed.

## Stretch goals, after the 21:30 go/no-go
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
| Guides and « Pourquoi ? » | `POST /api/guides`, `GET /api/guides/{id}`, `POST /api/guides/{id}/why` | exists |
| Hold countdown | a deadline on `Hold` | to add |
| Gauges and leg chart | each step's leg scores, confirmation and facts | to add, with triangle scoring |
| What Cressey sees | per run | to add |
| Incidents, fixes, replay, control run | incident endpoints | to add |
| Integrity strip | the log head: hash and count | to add |
| Header and waiting state | status: protection mode, model mode, MCP URL | to add |
| Évaluation | the eval reports (`backend/data/eval/report-dev.json` exists) | to add |

The interface polls the runs and holds about once a second. It moves to SSE only if polling lags.
