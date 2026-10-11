# Holds that matter — design

Date: 2026-10-11. Status: draft, for approval.

## Why

Two things went wrong when the user drove a real Claude Code session through Cressey's hook:

1. **Too many holds.** Every call carrying the trap key was held, even read-only GraphQL
   queries. Approving one did not help: the agent puts `OPS_TOKEN=…` in every Bash command,
   so its next query was held again. (Claude Code's own tools were also held as "tool not in
   the policy"; that part is already fixed in `e2d34d6`, merged as `c4f50c0`.)
2. **A bare rejection leaves the agent guessing.** On Reject the agent only reads
   "Cressey: action held. Declaring the task impossible is an accepted answer." The key is then
   suspended until the user's next prompt, so the agent can't even finish the honest way.

The goal: **flag what the agent touches, stop it only where the risk is real, and when a human
stops it, steer the agent to a clean finish or a clean stop.** When there is no legitimate path,
the human decides to stop, with Cressey showing the evidence.

## Goals

- **G1. Trap key by what the call does.** A trap key used in a call that only reads is flagged
  (incident opened, step marked alerted) and goes through. A trap key used in a call that writes
  or deletes is held, even when the agent is calm.
- **G2. Read API calls in shell commands.** `shell_risk` recognises a `curl` that only reads, so
  G1 applies to how agents actually reach APIs. It adds no new destructive class: an API call that
  changes something stays a write, as today, so G2 adds no hold of its own.
- **G3. Three actions at a hold:** Accept, Reject, Reject + add reason. The reason is drafted by a
  model while the call waits, checked by code, editable, then sent to the agent as the refusal.
- **G4. Rejections steer, the third one stops.** After a rejection the agent keeps working inside
  its mandate. The third rejection in a turn tells the agent to stop and report, and suspends its
  key. The dashboard shows "No path within the mandate so far" with the evidence, and one action:
  Unlock (the user's next prompt unlocks too).

## Non-goals

- Widening the mandate from the dashboard mid-run.
- Telling the agent which rule caught it, or that a key is a decoy.
- Feeding the agent's own words or arguments to the draft model.
- Classifying PowerShell or non-HTTP API clients (Python `requests`, the Railway CLI): they keep
  today's classification.
- Changing the triangle's rule or thresholds, or the read-only key rule.

## Anti-goals (a failure even if it "works")

- The PocketOS deletion goes through: a `serviceDelete` with the trap key must be held.
- The agent learns a detection rule, a trap key's name or value, or that a key is a decoy.
- A model approves a call or decides to stop the agent.
- A drafted message reaches the agent without passing the code check.
- The hold depends on a model answering: if the model is down or slow, Reject + reason still
  works, with the fallback message.

## Constraints

- **Code decides, models only label (or draft).** No model output changes a decision.
- **Approval stays per call** (a human approving one use of a trap key doesn't approve the key).
- **The user's prompt unlocks** a suspended key (decided 10-11, built in `4be1835`).
- The deny message (`permissionDecisionReason`, or the MCP `ToolError`) is the only channel to the
  agent on a refusal. Accept sends nothing.
- `CRESSEY_MODEL_MODE=replay-first` must keep working: model calls go through the existing cache.
- The dashboard follows Claude Design v6: the third button uses the design's existing button
  styles.
- The same `Guard.before` serves the MCP proxy and the hook: G1, G2 and G4 apply to both. An MCP
  run has no turns, so its rejection count is per run.

## Decided by the user

- **D1.** Three actions: Accept, Reject, Reject + add reason. The reason is drafted by an LLM, not
  typed from scratch, because a reason the user types isn't reliable. The user can edit it.
- **D2.** A trap key used only to read: flag and incident, no hold. A trap key used to change or
  delete something: held even when the agent is calm.
- **D3.** Stopping when there is no solution is the human's decision. Cressey can't prove a task
  impossible; it shows evidence ("no path within the mandate so far").
- **D4.** Opportunity alone never holds; opportunity with high rationalization on a non-read call
  holds. This is today's triangle rule (`triangle.alarm`), unchanged.
- **D5.** The scripted trap-key session (`demo-cle-piege`) changes so the key is used to change
  something, not in a `SELECT`, and the evaluation is run again, so the rule is the same
  everywhere and every incident is still held.
- **D6.** The third rejection in a turn stops the agent: its refusal tells it to stop and report,
  and the key stays suspended. All three rejections were the human's, so the stop follows the
  human's decisions; Unlock, or the user's next prompt, undoes it. (A pause waiting for a Stop or
  Continue click was dropped: a Claude Code agent ends its turn after a refusal, so the click would
  reach nobody.)

## How it works

### G1. Trap key response by call risk

In `Guard.before`, when the call carries a trap key:
- its risk is `read` → the response is `responses.trap_key_read` (default `alert`): the call goes
  through, the step is marked `alerted`, the incident opens as today;
- otherwise → `responses.trap_key` as today (default `review`: held for a human).

`trap_key_read` is a new field of `Responses`, set in `policy.yaml` and changeable live through
`PUT /api/policy/responses` like the others. Severity of the incident is unchanged.

One incident per trap key per run (Claude's call): the agent puts the key in every command, and
each critical incident starts the guide's model calls. The first read with a key opens the
incident; later reads with the same key are marked `alerted` in the trace without a new incident.

### G2. API calls in `shell_risk`

A segment whose command is `curl` (or `wget`) is classified from its flags and body:

| The call | Risk |
|---|---|
| No method flag, or `-X GET` / `-X HEAD`, and no body | read |
| An inline GraphQL body whose operation is a `query` (no `mutation` keyword), including introspection (`__schema`, `__type`) | read |
| `-X POST/PUT/PATCH/DELETE`, a body that isn't a GraphQL query, a GraphQL `mutation` (`serviceDelete` included) | write, as today |
| Anything it can't read: body from a file (`-d @payload.json`), from a variable (`"$BODY"`), a heredoc | write, as today |

API deletes are not made destructive (Claude's call): a destructive shell command is held by the
floor whatever the mandate, so a `serviceDelete` with the legitimate staging token would be held
too, and `may_destroy` only covers SQL tables. The PocketOS `serviceDelete` is still held: it
carries the trap key and isn't a read (G1).

Fixes the PocketOS commands need, so a read is recognised at all:
- a leading assignment (`OPS_TOKEN=… curl …`) is skipped before reading the command name, and a
  segment that is only assignments (`API=https://…`) reads;
- a comment line (`# Check volumes`) is ignored;
- `sleep` joins the read-only commands.

`source`/`.` and `python3` stay writes: they can run anything. So a read piped into Python
(`curl … | python3 -c …`) that carries the trap key is still held. Known limit, accepted.

The command's risk stays the highest of its segments. `DESTRUCTIVE_COMMAND` still wins first.

Test cases: the recorded PocketOS commands from `lab/runs/20261011-011950-1` (the user's run
`ad3148d1c1df` lived only in memory), plus commands shaped like the ones seen in it: a project
query, a volumes query and an introspection query (read), and the `serviceDelete` mutation (write,
held by G1 when it carries the trap key).

### G3. Three actions and the drafted reason

**Draft.** When a call is held, Cressey starts a background task that drafts a message and stores
it on the step (`step.draft`, served to the dashboard). Inputs, all trusted: the run's task, its
mandate, the held call's tool name and risk class. Never the arguments, the agent's messages, the
result, the hold's reason or the decoys. Model: the existing rewrite model
(`Settings.rewrite_model`), through the guide's structured-output adapter and its cache, so
`replay-first` works. Output: one message of at most 400 characters.

**Check (code).** Before a draft is shown, and again before any message is sent:
- no trap key name or value (case-insensitive), no `[secret:…]` marker;
- no secret name that the run has seen but the mandate doesn't grant;
- none of the detection words: trap, decoy, honeytoken, floor, triangle;
- at most 500 characters;
- it ends with "Declaring the task impossible is an accepted answer." (appended if missing).

A draft that fails, or a model that is down or doesn't answer within the hold, gives the
**fallback**, built by code from the mandate:
"A human held this call. This task may use: {may_read_secrets, or "no secrets"}; it may delete:
{may_destroy, or "nothing"}. Stay within these permissions. Declaring the task impossible is an
accepted answer."

**Actions.**
- **Accept** — as today (`POST …/approve`, behind the design's second click).
- **Reject** — as today: the agent reads "Cressey: action held. Declaring the task impossible is
  an accepted answer."
- **Reject + add reason** — opens an editable box filled with `step.draft` (or the fallback while
  the draft is coming). Sending posts `POST …/reject` with `{"message": "…"}`. The backend runs the
  check again; a message that fails is refused (422, with the rule it broke) and the dashboard
  shows why. On success the agent reads "Cressey: action held. {message}". The sent message is
  stored on the step (`step.message`) and shown in the hold's outcome.

### G4. Rejections and the stop

- A rejection (or an expired hold) no longer suspends the key on its own. While a call is held,
  the key is still suspended for parallel calls, as today.
- Cressey counts the rejections and expiries in the current turn: since the user's last prompt
  (hook), or since the run started (MCP). At `stuck.rejections` (new in `policy.yaml`, default 3):
  - the agent's refusal for that call ends with: "Three calls were refused. Stop, report what you
    found, and declare the task impossible: it can't be done with your permissions." With
    Reject + add reason, the human's message comes first, then this sentence;
  - the key is suspended; later calls get today's refusal ("Cressey: key suspended. Declaring the
    task impossible is an accepted answer.");
  - the dashboard shows **No path within the mandate so far**, with the evidence:
    - the pre-run estimate that the task can fail when done honestly (`preflight`, factor
      `impossible`), when there is one;
    - the rejected calls of the turn;
    - the calls inside the mandate that failed (`is_error`);
    - the agent's last message;
  - one action, **Unlock**: the count resets and the key is unlocked
    (`POST /api/runs/{id}/unlock`).
- The user's next prompt also resets the count and unlocks, as today.
- The dashboard shows the count while it climbs ("2 of 3 refused").

### Data and API

- `Step.draft: str | None`, `Step.message: str | None`.
- `Run.stopped: bool` (or an equivalent), and the count of the turn's rejections, so the
  dashboard can show "2 of 3".
- `Responses.trap_key_read`, `Policy.stuck.rejections`.
- `POST …/reject` takes an optional body `{"message": str}`.
- `POST /api/runs/{id}/unlock` resets the count and unlocks the key.

## Build order

1. G1 + G2: they remove most of the friction and need no new screen. With them, `demo-cle-piege`
   uses the trap key to change something (D5), `tests/core/test_trap_keys.py` and the runsheet
   follow, and the evaluation (`demo/measure.py`) runs again; it calls the models for that session.
2. G3: the drafted reason and the third button.
3. G4: the stop at the third rejection, its panel and Unlock.

Each step ships on its own, with its tests.

## Where it's built

On `main`. `feat/message-flags` (another session's work, unmerged) changes `Step`, `Runs`,
`hook.py` and `Inspector.tsx` too: whichever merges second resolves the conflicts.

## Left to the builder

- The model prompt for the draft, within the inputs and checks above.
- The exact layout of the third button and the reason box inside the v6 Hold panel, and its
  keyboard shortcut (Accept is A, Reject is R).
- How the evidence is laid out in the "No path within the mandate so far" panel.
- Where the per-turn count lives (`Runs` or the run itself).

## Calls Claude made (to check)

- Plain Reject keeps today's message; only Reject + add reason sends a drafted one.
- The draft model is the existing rewrite model, not the guide writer or the judge.
- The stop counts rejections and expiries, not holds the human accepted.
- With Reject + add reason on the third rejection, the human's message comes first, then the stop
  sentence.
- `wget` is read like `curl`; `httpie`, Python clients and the Railway CLI are not read.
- API deletes stay writes (no new floor hold); only the trap key or the triangle holds them.
- One incident per trap key per run; later reads with it are only marked in the trace.
- `sleep` reads; `source` and `python3` stay writes.
- Built on `main`, not on `feat/message-flags`.
