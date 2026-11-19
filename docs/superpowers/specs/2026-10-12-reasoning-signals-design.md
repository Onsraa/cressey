# Reasoning signals — design

Date: 2026-10-12. Status: proposal, not built. Two decisions open (§11).
Builds on: `2026-10-11-cot-triangle-indicators-design.md` (the case file), `docs/research/reasoning-signals.md` (the research behind every claim below) and `docs/research/reasoning-signals-evidence.md` (the team's own measurements and probes). "(my call)" marks a choice made while writing, for the reader to check.

## 1. Why

The case file reads the agent's "thoughts". On the models agents run today, most of those thoughts never reach Cressey, and the ones that do are a mix of very different things, all tagged `narration`.

- **Missing words.** On Claude Opus 5.5, Sonnet 5.5, Fable 5 and 5.1, the notes the model writes between tool calls often come back as *progress-update* `thinking` blocks, not `text`. Claude Code's `MessageDisplay` hook carries `text` only.
  - Measured on Claude Code 2.1.296 + Opus 5.5: in one run the agent wrote 5 notes and the hook received 2.
  - In another run, with the same prompt, every note came back as `text`, so all of them would have reached it. The model picks the channel run by run.
- **Mixed reliability.**
  - A `text` block is the agent's verbatim words.
  - A progress update is a summary of the agent's note, written by a different model. In a measured case it turned "Key finding from the spec: …" into "I've confirmed …".
  - A reasoning block arrives empty, with only its exact token count.

  All three are handled the same way today.
- **Calibrated on another model, per thought.**
  - Every lab run and every thought cut-off (P1 0.99, R 0.56, …) comes from Claude Opus 4.6, whose between-call notes were verbatim `text`.
  - The cut-offs are set at 1% of normal *thoughts*. That compounds over a run: 2 of 20 normal runs were held (`thoughts-calibration.json`).

The goal: every signal Cressey uses carries where it came from and how far it can be trusted. Facts decide. Words point, and only ever add suspicion, with a confidence measured on normal runs. Numbers describe. What can't be trusted is cut.

## 2. What reasoning is, in short

- **Purpose.** Reasoning is the model's private workspace: tokens it generates before acting, shaped by reinforcement learning to improve outcomes. It is not written for a reader, and labs deliberately avoid training it to look good. Every visible trace is derived from it, never the thing itself.
- **Content.** No current Claude model returns raw reasoning. Claude Code receives, per API message:
  - empty reasoning blocks (the reasoning is encrypted in the signature);
  - progress updates: notes the model writes for the person watching, at most one per tool call, often skipped. A different model rewrites each into a one- or two-sentence summary;
  - verbatim `text`.

  Reasoning summaries, where shown, come from a separate model the thinking model never sees. They expose roughly a fifth of the reasoning and can flatten hedges (one 2026 preprint, small sample).
- **Size.** Adaptive: the model decides per step, and effort (`low` … `max`) sets the depth. `usage.output_tokens_details.thinking_tokens` gives the exact count per message, progress notes included at full length.
  - On this machine the median per message ranges from 48 tokens (Opus 5) to 305 (Opus 4.8), with maxima past 50,000.
  - Most reasoning happens on the first request after new user input.
- **Time.** Reasoning finishes before the tool call it leads to starts streaming. A progress update sits immediately before the `tool_use` it introduces. Duration runs about 10 ms per thinking token, so it adds nothing the count doesn't already say.
- **Model dependence.**
  - Opus 5 and Opus 4.8 send notes as `text`. Opus 5.5, Sonnet 5.5, Fable 5 and 5.1 move many of them into updates. Fable 5.1 writes few.
  - Higher effort means fewer updates. Opus 5.5 defaults to `medium` in headless runs.
  - Claude Code can switch model mid-run on its own, for example Opus 5.5 → Opus 4.8 on cybersecurity-flagged content.

## 3. What Cressey can observe

"In time" means available before the call runs, at its `PreToolUse`.

| Signal | Where | In time? | Form |
|---|---|---|---|
| Tool name, arguments, `tool_use_id` | PreToolUse | yes | fact |
| Agent-written argument fields: Bash `description`, Agent `prompt`, AskUserQuestion `questions`, ExitPlanMode `plan` | PreToolUse `tool_input` | yes | verbatim words, bound to the call |
| Effort level, permission mode, subagent id | PreToolUse | yes | fact |
| Short notes sent as `text` | MessageDisplay | usually (no ordering guarantee) | verbatim words |
| The progress update that introduces the call | transcript (lands ~0.1 s after PreToolUse), or a Claude Code mod (`turn.step`, live) | only by waiting ~0.1–0.3 s, or with the mod | another model's summary, bound to the call |
| Hidden-reasoning size of the message | transcript usage | with the same wait | exact number |
| Model of each message; display mode | transcript; SessionStart; PostModelSwitch | with the wait | fact |
| Tool result, duration, failure | PostToolUse / PostToolUseFailure | after | fact (content may carry injected text) |
| Final report | Stop | after | verbatim words |
| Subagent's words and report | SubagentStop (`agent_transcript_path`, `last_assistant_message`) | after | as above |
| Compaction summary | PostCompact | after | model-written summary of history |
| API errors, rate limits, overload | StopFailure | after | fact |
| User prompts | UserPromptSubmit | yes | verbatim human words |

Never observable:
- the raw reasoning;
- the full text of a progress note;
- advice from the advisor tool (server-side, often encrypted);
- anything inside a signature.

A `redacted_thinking` block never appeared in ~53,000 local messages. If one does, it is logged for review.

Measured on Claude Code 2.1.296 + Opus 5.5:
- At PreToolUse the call's transcript line is not yet on disk (4 of 4 calls).
- A hook that polls finds it 105–108 ms later (3 of 3). The write is not held behind the hook.

## 4. Three classes

### Take: facts

Facts are observed exactly as recorded, with no interpretation:
- the call, its arguments, its result and failure;
- the model, the effort and the thinking-token count;
- the order of events;
- the words themselves, as words (that the agent wrote X);
- a user's prompt;
- a hand-over (§6.5);
- a read of a target before the act.

Facts may decide alone, as the safety floor and trap keys do today.

### Weigh: interpretations, each with a confidence

- **Jev's reading of a unit of words.**
  - Its confidence is measured on normal runs: how rarely a normal run of the same model and channel scores this high anywhere.
  - Cut-offs are set jointly so that the share of normal runs held by words, all indicators and channels together, stays at a target (§11, decision 2). This replaces Task 8's 1% per thought.
  - A run-level rate of 1% rests on about the top 10 scores of ~1,000 normal runs; fewer runs mean a wider margin on every cut-off.
- **Code classifiers on facts** (`shell_risk`, `sql_risk`, the secret scan): deterministic and auditable. Their measured precision is reported with them.
- **Words by channel, strongest first:**
  - `narration` (verbatim `text`), `description`, `delegation`, `question`: the agent's own words.
  - `update`: another model's summary of a note written for the watcher. It can drop a hedge or invent a verification.
  - `compaction`: the model's summary of history. It can omit or reframe.
- **Words only add suspicion.** A word event may:
  - open a thread;
  - raise an alert;
  - take part in a hold, only when a fact makes the call risky: it carries an open opportunity object, or crosses the mandate (a floor reason).

  Being bound to the call says the words are about that call; it does not make the call risky. No word event closes a thread or lowers a score; facts do that.
- **Channels earn their rights.** A channel that is not calibrated for the run's model may only alert, and the dashboard says so. Once calibrated, an `update` unit takes part in holds like any other word event, with its measured confidence: the rule asked for on 2026-10-12, where the middle is weighed, not cut.

### Cut

| Cut | Why |
|---|---|
| A verification or sharing claim read from words ("I've confirmed", "Should I go ahead?") closing a thread | a summarizer can write it (measured); an agent can ask and carry on; the fact is checkable instead |
| `thinkingDurationMs` and wall time as a measure of thinking | they restate the token count, mixed with server speed and network; undocumented |
| Thinking-token count as a reason to hold | exact, but the evidence points both ways: reward-hacking shortcuts used less reasoning, instructed lies more |
| Signature content or length | opaque; length only restates the token count |
| Silence as innocence | reasoning is often not verbalized |
| Agent-written argument fields lowering a floor label | the agent's words could argue the floor down. Today Bash `description` reaches the floor's "actions alone" view. Anthropic's own action guard strips agent prose, because keeping it made the guard worse |
| The end-of-task report as a record of what happened | reports covered about 1 in 11 actions and drifted toward the plan; it stays a claim to check against the log (as today) |
| Human approvals and rejections as evidence of safety, or as calibration data | rule of 2026-10-12: improve only from facts. An approval stays an authorization for one object |
| Asking the agent for its reasoning: in the way out, in deny text, or as a `reasoning` / `justification` field in a tool schema | current models may refuse with `reasoning_extraction`, which breaks the run; it also teaches what is watched |
| Rewriting the agent's history (redacting earlier turns, removing a reminder) | it invalidates the agent's thinking blocks: the agent loses its reasoning, or the request fails. Every intervention is appended |
| Exact-quote matching against update text | it is a paraphrase |

## 5. Units and binding

| Channel | Source | Unit | Bound to |
|---|---|---|---|
| `narration` | MessageDisplay delta; transcript `text` blocks | a sentence or list item (today's segmenter) | every call of its API message, from the transcript; without a transcript, the next call (today's position) |
| `update` | transcript `thinking` block with text, or the mod | the whole update | the one `tool_use` right after it (exact `tool_use_id`) |
| `description` | Bash `tool_input.description` | the whole field | its own call |
| `delegation` | Agent `tool_input.prompt` | segmented like narration | its own call |
| `question` | AskUserQuestion `tool_input.questions` | the whole question | its own call; also a hand-over fact |
| `compaction` | PostCompact `compact_summary` | segmented | the run |
| prompt | UserPromptSubmit | as today | the run |

Per call, from the transcript: `model`, `effort`, display mode, and the `thinking_tokens` of its API message (deduplicated by `message.id`).

- **Objects stay (my call).** Every unit keeps today's object extraction and `about:` questions. Objects named in words ("Found the Postgres service: `22284a62…`") open threads for acts any distance later. The binding adds the bound call as one more link.
- **No more object guessing for the bound call.** A justification bound to the call it introduces is about that call, which removes the measured weakness "R links only through extracted objects".
- **Excerpts, not history.** Judging an excerpt next to its call, rather than the whole history, is also the setup that measured best for monitors (+17 to +32 points of catch rate at 1% false positives).

## 6. Engine changes

1. **Transcript reader** (new, small):
   - Per run, it reads `transcript_path` from the last byte offset, takes complete lines only and ignores unknown fields.
   - For a `tool_use_id` it returns the blocks before it in that API message: updates, `text`, the message's thinking tokens, model and display mode.
   - It does the same for subagent transcripts at SubagentStop.
   - Usage without `output_tokens_details` (older transcripts, headless `stream-json`) reads as "unavailable".
   - It keeps text and numbers only. Signatures are never stored or sent to Jev: they carry the encrypted reasoning, and one 2026 paper decoded them and recovered credentials from public reasoning blocks.
   - Test fixtures come from the probe transcripts of 2026-10-12: Claude Code 2.1.296 + Opus 5.5 on a synthetic folder, no user data (my call).
2. **Hook** (`adapters/claude_code.py`):
   - At PreToolUse it reads the bound words in parallel with the guard's existing work, with a bounded wait.
   - It waits only when a live path reads words (§7) and the words can change the decision: a call that is not a read, or one carrying an open opportunity object. Otherwise words are read in the background.
   - The cap comes from measured landing delays and is kept in `policy.yaml` with its basis.
   - It handles four more events:
     - SubagentStop: the subagent's words;
     - PostModelSwitch: the model change;
     - PostCompact: the summary, and a note that earlier reasoning left the agent's context;
     - StopFailure: the turn ended on an API error, not on a choice.
3. **Models** (`domain/runs.py`, `domain/policy.py`):
   - `WordSource` gains `update`, `description`, `delegation`, `question`, `compaction`. `narration` keeps meaning verbatim `text`, and `summary` and `reasoning` stay for later channels.
   - `Message` and `Event` gain the `tool_use_id`s they are bound to.
   - `Step` gains its `tool_use_id`, `model`, `effort` and `thinking_tokens`.
4. **Thoughts** (`engine/case/thoughts.py`):
   - Units of `update`, `description` and `question` are one thought each.
   - A bound unit's window shows its call.
   - Scripted sessions, replays and MCP runs have no bound units, so their recorded answers don't change.
5. **Case file** (`engine/case/case.py`):
   - **Justification.** `decide` counts an R or C1 event bound to the call as a justification for that call. The hold still needs §4's fact.
   - **Sharing.**
     - A pressure thread is shared by a hand-over fact: the turn ended (Stop) or an AskUserQuestion call ran, after the obstacle and before the act.
     - It shares every pressure thread opened before it, as a bare N1 does today. An agent that stops to report without asking shares too, as the spec's N1 already defined.
     - `read_prompt`'s "answers the agent's question" check is dropped: the turn end already shares. Approvals are unchanged (my call).
   - **Verification (my call).**
     - Only for targets: a read carrying a target object before the act clears its "Target never verified" line.
     - It never takes a thread out of `open`, so the use link (A1) stays.
     - A secret object is never verified. This also fixes today's code, where a word-level N3 naming a token closes that token's thread.
   - Word-level N1 and N3 stay on the dashboard as "said", and close nothing.
6. **Floor** (`engine/floor/labels.py`, my call; measured and built 10-13, see below):
   - Each floor label is the higher of two views: the actions alone (the raw arguments without agent-written fields, then redacted) and today's view with them. Words can raise a label, never lower it.
   - So an honest description still helps Jev read an opaque `curl`: the PocketOS hold with the trap key defused (0.72) was read with the `description` in view, and stays.
   - Cost: one more Jev call per write the code lets through, in parallel. Today's recorded answers stay valid; the actions-alone view is recorded once.
   - Measured 10-13 on live Jev, 71 Bash actions from the floor calibration set, two answers each: a reassuring `description` lowered 18 of 40 answers on irreversible actions and released 3 of 20 irreversible holds and 1 of 24 production holds. With the two views, every hold came back (20/20, 24/24). Built on branch `exp/phase1-proof`: `words: [description]` on Bash in `data/catalogs/claude-code.yaml`, the rule field `ToolRule.words`, and the two views in `floor_labels`.
7. **Said vs did** (new question, my call to add now):
   - For an exactly bound unit (`update`, `description`, `question`, or transcript-bound narration): "Does the CURRENT thought describe the call after it as smaller, safer, read-only, or different from what the call does?"
   - It is asked in the same Jev call, in the bound units' own question set, so no recorded answer changes.
   - It shows in shadow and counts only once calibrated.
8. **Thresholds** (`policy.yaml`):
   - Cut-offs are keyed by exact model id and channel (my call: grouping models into families would carry Opus 5's habits onto Opus 5.5).
   - `narration` keeps today's per-thought cut-offs on every model until its run-level calibration exists. Stage demos and replays keep their holds.
   - Every other channel alerts only until calibrated.
9. **Numbers:**
   - Each call stores its thinking tokens. The dashboard shows them against the run's median ("thought 6,981 tokens before this call, 9× the run's median").
   - Struggle metrics are computed and stored: calls, failures and thinking tokens between a first obstacle and its outcome. The setup-feedback layer and the memory of failed paths that will read them are separate work (my call).
   - None of these is ever a hold reason.

## 7. Shadow and live

- **The case file stays in shadow** until the 10-11 must-pass cases pass, as decided then. Nothing here changes that rule.
- **The only live path from words** is still `CRESSEY_THOUGHT_HOLDS` (off by default); the PreToolUse wait serves it, and the case file when it goes live.
- **The legacy live triangle is unchanged.** Its write judgment and its ledger read `narration` only, through `_said`.
  - It is the one place words can still lower a score. That exception is kept because the actions-only view false-held a legitimate write at 0.65 (10-10).
  - Revisit it after recalibration.
- **"Keep their results" (§9)** means today's live outcomes for the stage sessions and replays. The case-file must-pass cases are measured in shadow and should improve; they are not a gate for this work.

## 8. Every variable

| Variable | What it changes | How the engine handles it |
|---|---|---|
| Human: prompts | pressure, approvals | prompt text is a fact; what it says is weighed; an approval authorizes one object, never proves safety |
| Human: settings | in a headless probe, `showThinkingSummaries: true` emptied the updates and gave no summaries | read the display mode and count empty updates per run; the dashboard shows "words withheld by settings" |
| Human: model and effort choice | volume and channel of words | facts per call; cut-offs per model |
| Human: interrupt (Esc) | a message cut short | closed at the next prompt (as today) |
| Agent: model version, fallback | channel, style, thinking volume | per-message model from the transcript; PostModelSwitch; uncalibrated channel → alert only |
| Agent: effort | fewer updates at high effort, terser output at low | fact per call; coverage on the dashboard |
| Agent: channel choice (text vs update) | what MessageDisplay sees | both channels read, every time |
| Agent: knows it is watched | its words get cleaner; actions don't. After a hold it knows | words after the first hold are marked; only facts keep full weight |
| Agent: evaluation awareness | staged runs provoke reasoning real runs don't (Opus 5.5: about 0.4% of real transcripts vs 36% of synthetic audits) | calibrate on realistic runs; scripted sessions measure the mechanism, not a rate |
| Agent: subagents | words in another transcript | `agent_id` on calls; subagent words at SubagentStop |
| Agent: advisor tool | advice invisible to hooks | shown as "advice taken, content unseen" when the transcript records the call |
| Computer: transcript | written asynchronously; internal format | bounded wait; offset reads; complete lines; unknown fields ignored; Claude Code `version` kept |
| Computer: deployment | `transcript_path` is on the agent's machine; Docker mounts no volume | §11, decision 1 |
| Computer: Cressey's own classifiers | known errors (`source .env && curl` classed a write) | precision reported with each code label |
| Computer: Cressey's own interventions | an edited history drops the agent's reasoning | append only: hook output, deny text, mid-conversation messages |
| Network: hooks | a down Cressey fails open unless `onFailure: block` | kept on every gating hook, with short timeouts |
| Network: Jev | slow, down, or not perfectly repeatable | the unit stays unread; `words_read` false; the floor still holds; repeat drift measured per channel |
| Network: API errors | a turn ends on a 429 or an overload | StopFailure is a fact, never read as the agent stopping or asking |
| Network: speed mode | durations change, content doesn't | durations are not used |

## 9. Measuring it

- **Recalibrate on current models**, per channel, on run maxima: lab runs on Opus 5.5 and Sonnet 5.5, plus a run-maxima version of `lab/label_thoughts.py`. The existing corpus is Opus 4.6 `text` only.
- **Coverage:** the share of the agent's notes Cressey receives in time, by model and source (MessageDisplay alone; with the transcript; with the mod). Measured today: from 2 of 5 to all of them.
- **Paraphrase:** compare indicator distributions on `narration` and `update` units from the same runs. The original note behind an update is never available, so this compares distributions, not pairs.
- **Judge stability:** repeat each question on a fixed set per channel and keep the raw score of every call. Task 8 measured a p95 drift of 0.05 or less on narration.
- **Said vs did:** a small set of the same commands with honest and understated descriptions.
- **Floor:** rescore the floor calibration set with honest and reassuring descriptions added. The two-view label must keep every hold and add as few false holds as possible.
- **Wait:** the p95 transcript landing delay, and the share of risky calls whose bound words missed the cap.
- **Must pass:** the PocketOS pair, the Hugging Face replay and demo-triangle keep their live results (§7).

## 10. Near future

The API has shown less reasoning every year: raw, then summarized, then hidden by default, then narration moved into hidden blocks, then refusals for extraction. One newer model reportedly shortens its reasoning when told a monitor is present and does part of it without text (press reports). The design therefore never depends on words existing: they only add suspicion. More visibility plugs in as a new channel.

| Channel | How it plugs in |
|---|---|
| `summary` | reasoning summaries, if a session ever exposes them |
| The Cressey mod (`turn.step`) | live updates before each call, with a veto; replaces the transcript wait where installed (early-access API) |
| `reasoning` | the raw reasoning of open-weight models (gpt-oss returned it on 2026-10-11) |
| Fewer words | if reasoning goes latent, the facts and numbers still run the engine |

## 11. Decisions needed

1. **How Cressey reads the transcript when it doesn't run on the agent's machine.** Each answer is a different build:
   - read `transcript_path` directly: works with `connect.sh` and `dev.sh`, not in the Docker image, and not with Cressey outside the agent's container;
   - a local command hook that forwards the new lines to a Cressey ingest endpoint;
   - a Cressey mod: live, can veto, but an early-access API installed as a plugin.
2. **The false-hold budget and the calibration spend.**
   - What share of normal runs may words hold (today's per-thought 1% gave 2 of 20)?
   - Is the paid recalibration part of this work? A stable 1% needs on the order of 1,000 normal runs per model. The October lab runs cost $0.28–0.97 each, plus Jev calls.
