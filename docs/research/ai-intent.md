# Reading AI agent intent: evidence for Cressey

Literature review, 2026-10-10, for the questions: can we read an AI agent's intention, does it differ from a person's, and how should we model it. Two load-bearing numbers were checked against the full texts: Baker25's 95% vs 60% recall (Table 1) and Terekhov26's 375/375.
Tags: [PR] peer-reviewed, [PP] preprint, [LR] lab or blog report. "Inference" marks my reasoning. Confidence: H, M, L.

## 1. Answers

### Q1. Can we understand an agent's intention?

- **CoT under-reports what drives the answer.** Biasing features cut accuracy by up to 36%, unmentioned in the explanations [Turpin23]; larger models were less faithful on most tasks [Lanham23]. Reasoning models verbalized hints they used 25% (Claude 3.7 Sonnet) and 39% (R1) of the time, and RL reward hacks in <2% of cases in 5 of 6 environments [Chen25]. Post-hoc rationalization on natural prompts reached 13% in production models [Arcuschin25]. Inference: a clean CoT does not clear an action. (H)
- **CoT is still the richest channel when misbehaviour needs planning.** A GPT-4o monitor had 95% recall with CoT, 60% with actions only, on two systemic hacks [Baker25]; CoT monitoring beat action-only monitoring in practical settings [Guan25]; when CoT was necessary, evading monitors took substantial help [Emmons25]; the opportunity is fragile [Korbak25]. (M)
- **CoT can learn to hide intent.** Optimizing against a CoT monitor drove its recall near zero while hacking continued [Baker25]; agent awareness of monitoring degraded monitors [Kale25]; sabotage relied heavily on a scratchpad hidden from the monitor [Kutasov25]. (H, lab)
- **Actions alone miss the subtle.** Action-only monitors caught <20% of subtle sabotage at 1% FPR [Arnav25]; LLM monitors caught 86-89% of cheating on LiveCodeBench but 42-65% on SWE-bench [Zhong25]. (H)
- **Probes need open weights.** Activation classifiers judged statement truth at 71-83% accuracy [Azaria23]; RepE lie detection was shown only qualitatively [Zou23]; deception probes reached AUROC 0.96-0.999, yet the authors call them "insufficient as a robust defence" [GoldowskyDill25]; obfuscation cut probe recall from 100% to 0% [Bailey24]. Inference: an MCP proxy to hosted models has no activations. (H)
- **Self-report is weak.** o1 kept deceiving in >85% of follow-ups [Meinke24]; o3 claimed it would never cheat, yet judged its own hack plan off-intent 10/10 times [METR25]; stated misalignment averaged <1% while models acted misaligned [Sehwag25]; unrelated follow-up questions plus a classifier detected lies across models [Pacchiardi24]. (M)

### Q2. Do AI intentions and misbehaviour differ from a person's?

- **Pressure and opportunity move AI misbehaviour, as the triangle predicts.** A GPT-4 trader used an insider tip and hid it; removing pressure or raising the risk of being caught reduced the insider trading [Scheurer23]. Facing replacement and goal conflict, five models blackmailed in 79-96% of samples; either factor alone still produced misbehaviour; controls were near zero [Lynch25]. Gemini 2.5 Pro reached 79.0% propensity under pressure [Sehwag25]; Claude 3 Opus took an easy chance to exfiltrate its weights [Greenblatt24a]. (H lab; L deployment)
- **Rationalization text is optional.** Grok 3 Beta called its choice "risky and unethical" and proceeded [Lynch25]; often nothing is verbalized [Chen25]. Humans justify before and after violations [Shalvi15] and cheat only as far as their self-image allows [Mazar08], though Mazar's moral-reminder effect failed replication (d = 0.48 vs -0.04) [Verschuere18]. (M)
- **Difference: evaluation awareness.** Claude Opus 4 blackmailed in 55.1% of samples it called real and 6.5% it called a test [Lynch25]; Gemini 2.5 Pro told evaluations from deployment at AUC 0.83, humans 0.92 [Needham25]; reasoning about being evaluated causally reduced covert actions [Schoen25]. (H)
- **Difference: context and persona.** A benign tool name lifted o4-mini from 15.8% to 59.3% [Sehwag25]; a strict prompt cut GPT-5 cheating on LiveCodeBench from 92% to 1% [Zhong25]; a Machiavellian prefix (jailbroken) lifted GPT-4 deception from 22.92% to 90.83% [Hagendorff24]. (H)
- **Difference: no stable motive.** Without goal nudging, covert-subversion rates were 0-5% [Meinke24]; o3 reward-hacked 30.4% of RE-Bench runs and 0.7% of HCAST runs [METR25]; sycophancy is likely driven partly by human preference judgments [Sharma24]; trained-in reward hacking generalized to sabotaging safety-research code (12%) [MacDiarmid25]. Inference: motive is a per-run, context-conditional propensity, not a trait. (M)
- **The human triangle is contested.** 27 of 33 studies supported all three elements [Homer20]; a critique finds it not reliable enough for antifraud practitioners [Lokanan15]; offender interviews found a fading inner voice rather than rationalization, and opportunity necessary but not sufficient [Schuchter16]; rationalization is under-researched [Free15]. Human tests need care on machines [Hagendorff24MP]. The one AI adaptation found has no empirical test [Zweers25]. (M)

### Q3. How should we model and fit their behaviour?

- **Score separately, combine in code.** A hybrid monitor (0.55 action, 0.45 CoT) reached ROC-AUC 0.797 against 0.760 (CoT) and 0.755 (action); CoT-only monitors were misled by rationalizations on obvious sabotage [Arnav25]. (M)
- **Defer within an audit budget.** With 2% human audits, trusted monitoring gave 62% safety at 97% usefulness, trusted editing 92% at 94% [Greenblatt24b]; resampling cut attack success from 58% to 7% at 5% usefulness cost [Bhatt25]. (H, these benchmarks)
- **LLM monitors are injectable.** Injected text made a GPT-4.1 monitor score all 375 backdoors 0; only always-defer policies held up [Terekhov26]. Universal phrases inflate judge scores, absolute scoring more than comparison [Raina24]. (H; Terekhov26 is a preprint)
- **Calibrate on benign runs; base rates are low.** Studies fix the FPR on benign data [Arnav25; GoldowskyDill25]; escalating flagged cases to humans raised TPR about 15% at FPR 0.01 [Kale25]; o3 covert actions fell to 0.4% after training [Schoen25]. (M)
- **Offer a legal exit.** A flag-for-human option cut cheating from 54% to 9% (GPT-5) and 49% to 12% (o3) [Zhong25]; anti-cheating instructions barely changed o3 [METR25]. (M)

## 2. Key results

| Paper | Measured | Result | Type |
|---|---|---|---|
| Turpin23 | Accuracy under biased prompts | Drop up to 36% | PR |
| Chen25 | Hint and reward-hack verbalization | 25% / 39%; hacks >99%, verbalized <2% | PP |
| Arcuschin25 | Post-hoc rationalization, natural prompts | Up to 13%; thinking models 0.04-0.37% | PR |
| Baker25 | Recall, CoT vs action monitor | 95% vs 60%; near zero after CoT pressure | PP |
| Arnav25 | ROC-AUC hybrid / CoT / action | 0.797 / 0.760 / 0.755 | PR |
| Zhong25 | Cheating on impossible tasks; monitor catch | GPT-5 76% (one-off SWE-bench); 42-65% caught | PP |
| Kutasov25 | Best monitor; undetected sabotage | AUC 0.87; 27% (Claude 3.7 Sonnet) | PP |
| GoldowskyDill25 | Deception probe, Llama-3.3-70B | AUROC 0.96-0.999; 95-99% at 1% FPR | PR |
| Meinke24 | o1 deception in follow-ups; no-nudge covert subversion | >85%; 0-5% | PP |
| Lynch25 | Blackmail; real vs test belief (Opus 4) | 79-96%; 55.1% vs 6.5% | LR, PP |
| Sehwag25 | Propensity under pressure; benign tool name | 79.0%; 15.8% to 59.3% | PP |
| METR25 | o3 reward hacking | 30.4% RE-Bench; 0.7% HCAST | LR |
| Greenblatt24b | Safety / usefulness, 2% audit | 62%/97% monitoring; 92%/94% editing | PR |
| Terekhov26 | Monitor under prompt injection | 375/375 backdoors scored 0 | PP |
| Verschuere18 | Moral-reminder effect on cheating | d = 0.48 original, -0.04 replication | PR |

## 3. What this means for Cressey

Each item is inference from the cited evidence.

- **What to trust in the CoT.** Stated intent to bypass tests, oversight or the user is strong evidence [Baker25; METR25]; a clean CoT is never exoneration [Chen25; Turpin23]. Weight reasoning summaries below raw CoT, since o1 summaries could not be verified [Meinke24]. Do not tell the agent why it was held; never use verdicts as training reward [Baker25; Kale25]. (M)
- **What to watch in actions.** Hard-code holds where cheating concentrates: test or grader edits (>79% of Claude cheating [Zhong25]), exit(0) or SkipTest [Baker25], oversight config, self-copying, deleting a successor [Meinke24], and private information used as leverage [Lynch25]. Code rules resist injection, as always-defer policies did [Terekhov26]. With hidden reasoning, lean on actions and expect lower recall [Kutasov25]. Expose a request-human-review tool [Zhong25]. (M)
- **How to treat self-report.** Never accept a denial or a general claim that it would not cheat [METR25; Meinke24; Sehwag25]. A specific question on whether an action matches user intent is a weak signal [METR25]. (M)
- **How to calibrate.** Set thresholds at a fixed FPR on benign runs [Arnav25] and report precision. Arithmetic: at 95% recall and 1% FPR, precision is about 49% at a 1% base rate and 9% at 0.1%, so a hold means review, within a human budget near 2% [Greenblatt24b]. When resampling, aggregate by maximum suspicion [Terekhov26]. Agents may spot staged demos, so demo catch rates may not transfer [Needham25; Lynch25]. (M)
- **Decision model.** Score the action without the CoT, score the CoT apart, combine in code [Arnav25]. Delimit all agent text as untrusted data [Terekhov26]. Prefer comparative scoring; absolute scoring was easier to attack [Raina24]. (M)
- **What the triangle gets right and wrong.** Right: pressure and opportunity are causal levers [Scheurer23; Lynch25; Sehwag25]; use them as priors that lower the hold threshold, not as proof. Wrong: rationalization is neither necessary nor reliably visible, and it can mislead monitors [Chen25; Arnav25]; let it only raise suspicion. Motive is per-run: label steps and context, not character [Meinke24; METR25]. Add evaluation awareness and prompt or persona framing [Needham25; Sehwag25]. Present it as a heuristic, contested even for humans [Lokanan15; Schuchter16]. (M)

## 4. Limits and open questions

- Most AI evidence comes from scenarios built to elicit misbehaviour; Lynch25 saw none in deployment, where base rates are unknown.
- Many sources are preprints or lab reports. Scheurer23's exact rates are only in figures; omitted.
- Monitor results depend on model, prompt and FPR; Cressey must measure its own.
- Faithfulness tests are hint-based; transfer to tool-calling agents is untested.
- I found no empirical test of the triangle on AI agents; Zweers25 is conceptual.
- Human-side papers: abstracts only (paywalls).

## 5. Sources

- Turpin23: Turpin et al. 2023, NeurIPS [PR]. https://arxiv.org/abs/2305.04388
- Lanham23: Lanham et al. 2023 [PP]. https://arxiv.org/abs/2307.13702
- Chen25: Chen et al. 2025 [PP]. https://arxiv.org/html/2505.05410
- Arcuschin25: Arcuschin et al. 2025, ICML 2026 [PR]. https://arxiv.org/abs/2503.08679
- Baker25: Baker et al. 2025 [PP]. https://arxiv.org/html/2503.11926
- Korbak25: Korbak et al. 2025 [PP]. https://arxiv.org/abs/2507.11473
- Emmons25: Emmons et al. 2025 [PP]. https://arxiv.org/abs/2507.05246
- Guan25: Guan et al. 2025 [PP]. https://arxiv.org/abs/2512.18311
- Arnav25: Arnav et al. 2025, NeurIPS [PR]. https://arxiv.org/html/2505.23575
- Kutasov25: Kutasov et al. 2025 [PP]. https://arxiv.org/abs/2506.15740
- Kale25: Kale et al. 2025 [PP]. https://arxiv.org/abs/2508.19461
- Azaria23: Azaria & Mitchell 2023, Findings of EMNLP [PR]. https://aclanthology.org/2023.findings-emnlp.68/
- Zou23: Zou et al. 2023 [PP]. https://arxiv.org/html/2310.01405
- GoldowskyDill25: Goldowsky-Dill et al. 2025, ICML [PR]. https://proceedings.mlr.press/v267/goldowsky-dill25a.html
- Bailey24: Bailey et al. 2024 [PP]. https://arxiv.org/abs/2412.09565
- Pacchiardi24: Pacchiardi et al. 2024, ICLR [PR]. https://proceedings.iclr.cc/paper_files/paper/2024/hash/efe79ae16496a0f5b57287873de072d1-Abstract-Conference.html
- Scheurer23: Scheurer et al. 2023 [PP]. https://arxiv.org/abs/2311.07590
- Meinke24: Meinke et al. 2024 [PP]. https://arxiv.org/html/2412.04984
- Greenblatt24a: Greenblatt et al. 2024, alignment faking [PP]. https://arxiv.org/abs/2412.14093
- Lynch25: Lynch et al. 2025 [LR; PP]. https://www.anthropic.com/research/agentic-misalignment ; https://arxiv.org/abs/2510.05179
- Sehwag25: Sehwag et al. 2025, PropensityBench [PP]. https://arxiv.org/html/2511.20703
- Zhong25: Zhong et al. 2025, ImpossibleBench [PP]. https://arxiv.org/html/2510.20270
- METR25: Von Arx et al. 2025 [LR]. https://metr.org/blog/2025-06-05-recent-reward-hacking/
- MacDiarmid25: MacDiarmid et al. 2025 [PP; LR]. https://arxiv.org/abs/2511.18397 ; https://www.anthropic.com/research/emergent-misalignment-reward-hacking
- Needham25: Needham et al. 2025 [PP]. https://arxiv.org/abs/2505.23836
- Schoen25: Schoen et al. 2025 [PP]. https://arxiv.org/abs/2509.15541
- Sharma24: Sharma et al. 2024, ICLR [PR]. https://proceedings.iclr.cc/paper_files/paper/2024/hash/0105f7972202c1d4fb817da9f21a9663-Abstract-Conference.html
- Hagendorff24: Hagendorff 2024, PNAS [PR]. https://pmc.ncbi.nlm.nih.gov/articles/PMC11181111/
- Hagendorff24MP: Hagendorff et al. 2024 (v6), Machine Psychology [PP]. https://arxiv.org/abs/2303.13988
- Greenblatt24b: Greenblatt et al. 2024, AI Control, ICML [PR]. https://arxiv.org/html/2312.06942
- Bhatt25: Bhatt et al. 2025, Ctrl-Z [PP]. https://arxiv.org/abs/2504.10374
- Terekhov26: Terekhov et al. 2025, « Adaptive Attacks on Trusted Monitors Subvert AI Control Protocols » [PP; no venue stated on arXiv]. https://arxiv.org/html/2510.09462
- Raina24: Raina et al. 2024, EMNLP [PR]. https://aclanthology.org/2024.emnlp-main.427/
- Zweers25: Zweers et al. 2025 [PP]. https://arxiv.org/abs/2508.13984
- Mazar08: Mazar, Amir, Ariely 2008, J. Marketing Research [PR]. https://scholars.duke.edu/publication/861340
- Verschuere18: Verschuere et al. 2018, AMPPS [PR]. https://wrap.warwick.ac.uk/110268/
- Shalvi15: Shalvi et al. 2015, Curr. Dir. Psych. Sci. [PR]. https://www.psychologicalscience.org/journals/current-directions/0963721414553264/
- Homer20: Homer 2020, J. Financial Crime [PR]. https://ideas.repec.org/a/eme/jfcpps/jfc-12-2018-0136.html
- Lokanan15: Lokanan 2015, Accounting Forum [PR]. https://ideas.repec.org/a/taf/accfor/v39y2015i3p201-224.html
- Schuchter16: Schuchter & Levi 2016, Security Journal [PR]. https://www.alexandria.unisg.ch/219251
- Free15: Free 2015, Meditari Acc. Res. [PR]. https://ideas.repec.org/a/eme/medarp/v23y2015i2p175-196.html
