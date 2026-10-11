# Defensive metrics: Cressey

What the defender gets, and what we can and cannot show. Numbers come from `docs/evaluation.md` and `backend/data/eval/`. Anything not measured is marked as such.

## Time saved for the analyst
**Not measured.** The repo has no baseline of how long an analyst takes to triage a hold or write an incident report without Cressey, so no time-saved figure is claimed.

What is measured is machine time, not analyst time:
- Time to stop a dangerous call: p50 1.97 ms, 236 ms at the stage's pace (one live run).
- Time to produce three sourced fix guides after a hold, in parallel: 9.1 to 13.6 s (three live runs).
- Each hold arrives with the step, the reason, the confirmed legs of the triangle, and the traced source of the misused secret, so the analyst starts from a finished case rather than a raw log. Whether that is faster is not yet timed.

To measure it: time the same triage task with and without Cressey on the same synthetic incidents, with an analyst who has not seen them before.

### Estimate (not measured)
These figures are our assumptions, not data. Each one needs the timed test above to confirm it.

| Step per held incident | Without Cressey (assumed) | With Cressey (assumed) | Saved (assumed) |
|---|---|---|---|
| Find out what the agent did and why | 15 to 30 min: read the transcript, find the call | 2 to 5 min: the hold shows the step, the reason and the legs of the triangle | 10 to 25 min |
| Find where the misused secret came from | 10 to 30 min: search the repo and the session for the key | under 1 min: traced by Cressey, exact match on the first try in 3 of 3 demo runs | 10 to 30 min |
| Write a fix guide per owner | 30 to 60 min | about 5 min to review the sourced guide (guide generated in 9 to 14 s) | 25 to 55 min |
| Decide the hold | 5 min | 2 min | about 3 min |
| **Total per held incident** | **about 1 to 2 hours** | **about 10 to 15 min** | **about 50 to 100 min** |

**Basis:** the "without" column is a guess at how long a careful manual triage takes. The "with" column uses measured machine times (guides in 9 to 14 s, secret trace exact on 3 of 3 demo runs) plus an assumed review time. The timed test on the synthetic incidents should replace both columns.

**What it does not count:**
- Holds that turn out to be false alarms still cost the review time. Every normal session was let through in our set (0 of 6 held), but real traffic is not tested.
- Time spent by the approver on writes that are held for no security reason (see M3 in `human-control.md`).
- Any incident Cressey does not see: the saving applies only to traffic through Cressey.

## Precision of detections and conclusions
| Check | Result | Limit |
|---|---|---|
| Holds on normal sessions | **0/6** held by mistake | 6 sessions, synthetic, written by the team |
| Incident sessions held | **7/7** | same set; the team wrote the incidents to match the rules |
| Write judgment at 0.5 | 30/30 on labelled writes (15 "yes", 15 "no") | labels are ours |
| Report check at 0.8 | **5/5** precision: no honest report flagged; 5/10 recall | 20 reports; misses listed in `evaluation.md` |
| Sourced guide steps | 100% citation validity on all runs | checks that each step cites a retrieved passage, not that the advice is good |
| Retrieval, hit@3 after re-ranking | 30 to 31 of 31 | 33 team-written questions |

**Reading these numbers:** precision on a set this small is weak evidence. The 0/6 and 7/7 results show the rules and the triangle work on our own sessions. They do not give a false-positive rate for real traffic. The held-out set from outside the team is not written.

## Coverage
| Framework | Covered | Coverage in the repo |
|---|---|---|
| **MITRE ATT&CK** | T1485 Data Destruction, T1552.001 Credentials in Files, T1078 Valid Accounts | Mapped in `docs/pitch.md`. The destructive-SQL and trap-key sessions exercise T1485 and T1552.001 |
| **MITRE ATLAS v5.6.0** | 8 techniques mapped: AML.T0053, T0101, T0055, T0083, T0051, T0080, T0110, T0086 | IDs checked against `backend/data/reference/ATLAS.yaml`. The corpus holds 35 ATLAS mitigations for guides |
| **OWASP Top 10 for Agentic Applications** | ASI01, ASI02, ASI03 | Mapped in the defense sheet. **The OWASP corpus file is not in the repo** (`docs/guide-pipeline.md`: "missing"; it must be downloaded by hand), so no OWASP guide is checked against it |

**Gaps:**
- ATLAS and ATT&CK are mapped by hand. Nothing in the repo tests the mapping beyond the sessions named above.
- Only ASI01 to ASI03 are claimed. ASI10 was dropped from the defense sheet.
- Coverage holds only for traffic through Cressey (Claude Code hook and MCP proxy). An agent with another route is outside it.

## Summary
Cressey has measured precision on its own synthetic set (0 false holds, 7/7 incidents held) and measured machine speed. It has no measured analyst time saving, and its framework coverage is a hand mapping plus a corpus that is not fully loaded.
