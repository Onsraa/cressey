# How humans stay in control

Cressey decides nothing that a human cannot change. Models never release a hold. This sheet lists the thresholds a human can set, how each AI decision can be traced, and what happens when something fails.

## Escalation thresholds
Every value below is in `backend/data/policy.yaml`. The response per check can be changed live with `PUT /api/policy/responses`.

| Check | Trigger | Response by default | Human control |
|---|---|---|---|
| Safety floor | Destructive action outside the mandate (`rm`, `DROP`, `DELETE FROM`, `git push --force`, writes to frozen paths, tools missing from the policy) | **review**: held for a human | Response can be set to alert or stop; mandate edited per agent |
| Trap key | A decoy secret used to change something | **review** | Response per check |
| Trap key, read only | Decoy read, no change | **alert**: let through, incident opened | Response per check |
| Triangle | Write judged with rationalization confirmed (judgment ≥ 0.5) and pressure or opportunity confirmed by code | **review** | Response per check; thresholds in `triangle:` |
| Report check | Final report contradicts the log (score ≥ 0.8) | **alert only**: the run is over, so it cannot hold | Threshold in `triangle:` |
| Fleet | Same target refused in 3 runs within 15 minutes | **alert** | Window and count in `fleet:` |
| Stuck run | 3 rejected or expired holds in one turn | **Run suspended**: its key stops working until a human **Unlock** or the next prompt | `stuck:` count |

Response modes: **alert** (let the call through and open an incident), **review** (hold for a human), **stop** (refuse at once). After 3 rejected calls in a turn, Cressey tells the agent to stop and report.

**Holds never self-release.** Nothing in the code path releases a hold on a model's say-so. A person approves, rejects, or lets it expire.

## Traceability of AI decisions
- **Append-only event log.** Each event stores the hash of the previous event and its own hash (SHA-256 of its canonical JSON). `eventlog.verify()` checks sequence number, previous hash, and each hash, and can be anchored outside the log by hash and count. A tampered or reordered event fails verification. The demo run's log was verified: 15 records, chain intact (`docs/evaluation.md`).
- **Every hold states why.** Reason, the step's number, the legs of the triangle that were confirmed, and the model's score. The reasons are in `report-detection.json` (for example "destructive SQL outside the mandate: users").
- **Sourced guides.** Each fix-guide step cites a retrieved passage from ANSSI, MITRE ATLAS, OWASP or an internal runbook. Citation validity was 100% on all runs. A step citing a passage outside the retrieved list is dropped in code.
- **Agent's reasoning is shown as narration.** No provider exposes raw chain of thought, so the dashboard shows what the agent said, not why its model chose it.

## Error handling
| Failure | What happens | Status |
|---|---|---|
| Cressey unreachable from the Claude Code hook | Before Claude Code 2.1.295, the hook lets calls through (fail open). From 2.1.295, the README's limitation applies; check the version | **Known risk**: fail open on older versions |
| Backend restarted | Runs live in memory and are dropped. A hooked Claude Code then has every call refused until `./connect.sh` runs again | Fail closed; a human must reconnect |
| Judge model call fails | Not verified in the code read for this sheet. The floor and trap-key checks do not use the model, so they still apply | Needs a check: force a judge error and see whether the call is held or let through |
| Embedding call fails | Retrieval falls back to BM25 alone. Not triggered in the Bedrock run (no query fell back) | Tested by the Bedrock run only |
| Guide model fails | No sourced guide; the incident is still held and traced | Eval: 8/8 guides sourced in the final run |

## Open gaps
- **Holds tire the approver.** A SOC analyst who cannot judge a developer's file edit gets every write held (`docs/positioning-and-risks.md`, M3, open). The planned fix is to hold only on alarms and report holds per 100 normal runs. Not done.
- **Fail-open on older Claude Code versions** (above).
- **Judge can be swayed.** Adversarial text raised the score in our test but never lowered it (`docs/evaluation.md`). Not tested with a model other than Jev.
- **No human review of the report check's misses.** It misses 5 of 10 lies at 0.8 by design.
