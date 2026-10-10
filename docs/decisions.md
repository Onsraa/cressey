# Decisions

| Date | Decision | Reason |
|---|---|---|
| 10-08 | **Track 2** "Defenders Augmented" | Supervising agents is the core of Track 2 (tool layer, agent identity). Its grid rewards measured effectiveness and control of the AI |
| 10-08 | **The fraud triangle** (pressure, opportunity, rationalization) applied to agents | Real incidents follow it. Auditors (ISA 240) and KPMG on the jury know it |
| 10-08 | **Code decides, models only label** | Agent text is untrusted input. Jev can be swayed by adversarial text |
| 10-08 | **Safety floor independent of the triangle** | A calm attacker shows no pressure, so the triangle alone would miss it |
| 10-08 | **Drift weighted by the action's risk class** (read 0, write 0.5, destructive 1) | A harmless action (`run_tests`) can look off-task |
| 10-08 | **« Pas de transparence, pas d'autonomie »** instead of "reasoning or nothing" | Most agents can't expose their reasoning, and reasoning can be faked or unfaithful |
| 10-08 | **The demo agent is a scripted replay** of synthetic sessions | Reproducible, and safe |
| 10-08 | **Models:** gpt-5.5 writes guides, gpt-5.4-mini rewrites queries, text-embedding-3-small, Jev `jev-1.13.0` | Measured in S6: 23/23 quotes verified with gpt-5.5 against 19/21 with gpt-5.4-mini |
| 10-08 | **Relevance threshold 0.4** | S6 calibration: keeps 51 of 55 expected passages and 16 of 185 others. At 0.5, three misses were just below the line |
| 10-08 | **Two rewrite prompts:** incidents get the leg definitions, questions don't | The definitions fixed all 8 incidents but biased general questions |
| 10-08 | **TypeScript 6, not 7** | TS 7 breaks openapi-typescript |
| 10-08 | **Biome only** (oxlint removed) | One tool for lint and format |
| 10-10 | **AWS Bedrock** for deployment, hosting and models. OpenAI for now | Partnership. Move to Bedrock after the core works |
| 10-10 | **The model cache is committed**, and `fallback` mode is used on stage | The demo survives a Wi-Fi or API outage |
| 10-10 | **Progressive installation**: Observer, then report, then Guard, then options | The user adds one thing at a time, with no upfront configuration |

## Open
- Core loop and dashboard: to build at the event, from `concept.md`.
- `owasp_asi.json`: needs the OWASP PDF, downloaded by hand.
- Held-out evaluation set: needs someone outside the team.
- `GITGUARDIAN_API_KEY` repo secret: needed for the secret scan in CI.
- Bedrock adapters and the AWS deploy.
