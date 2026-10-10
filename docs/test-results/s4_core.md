# S4: core algorithms and SDKs (2026-10-08)

The spike code was throwaway and has been deleted; only these results are kept. It ran on Python 3.12.13 in a local virtualenv.

## Versions verified (installed and introspected)
| Package | Version | What was checked |
|---|---|---|
| sqlglot | 30.21.0 | `sqlglot.parse(sql, read=...)`; `exp.Delete`, `Drop`, `Update`, `Insert`, `Alter`, `TruncateTable`, `Command` exist |
| detect-secrets | 1.5.0 | `SecretsCollection().scan_file(path)` inside `default_settings()` |
| openai | 3.26.1 | `OpenAI(base_url=...)` is supported, which allows routing to OpenAI, Bedrock or a local endpoint |
| typesafe-sdk (Jev) | 0.7.2 | see below |

**Jev SDK (`typesafe-sdk` 0.7.2, module `typesafe_sdk`):**
- **Client:** `TypeSafeClient(api_key=None, model=None, retry=None, timeout=None, base_url=None, …)`, or the async form `AsyncTypeSafeClient`.
- **Environment variables:** `TYPESAFE_API_KEY`, `TYPESAFE_BASE_URL`, `TYPESAFE_DEFAULT_MODEL`. The key is `TYPESAFE_API_KEY`, not `JEV_API_KEY`.
- **Call:** `client.system_one(state, questions={id: Noul(...) | Choice(criteria={...}) | Score(criteria=[...])}, model=..., timeout=...)`. It returns `SystemOneResponse(model, usage, answers)`.
- **Answers:**
  - `NoulAnswer.noul` is a float;
  - `ChoiceAnswer` has `choice`, `confidence` and `probabilities`;
  - `ScoreAnswer` has `score`, `confidence`, `legend` and `probabilities`.
- **Retries:** `RetryPolicy` defaults to 2 retries, backoff and a 30 s timeout.
- **Not verified (no key):** a live call, latency, French quality, and rate limits. The sources disagree on the limit: 1,200 requests per minute ([opentweet.io/jev/limits](https://opentweet.io/jev/limits)) against "40 requests per second" in `../../../docs/ideas.md`. They also disagree on the endpoint, `api.typesafe.ai` versus `api.llmgateway.io`. Read `TYPESAFE_BASE_URL` from the official docs on day one.

## a) Classifying SQL actions (read / write / destructive / unknown)
- **Result:** 23 of 24 cases came out as expected.
- **What works:**
  - several statements in one string;
  - comments that hide a second statement;
  - `BEGIN; DELETE…; ROLLBACK;`;
  - `UPDATE` without `WHERE` counted as destructive;
  - `ALTER … DROP COLUMN`;
  - `DROP … IF EXISTS`;
  - `TRUNCATE`;
  - `ON CONFLICT DO UPDATE`;
  - text that isn't SQL returns "unknown".
- **The one miss:** sqlglot parses `REPLACE INTO …` as a generic `Command` in both SQLite and MySQL, so it returned "unknown". **Fix:** a keyword rule ahead of the parser (`^\s*REPLACE\s+INTO` means write).
- **Policy:** "unknown" is treated as destructive (fail closed). That makes `VACUUM`, `PRAGMA` and `ATTACH` holds, which is the safe side.
- **Edge cases to keep in the test set:**
  - comments;
  - several statements;
  - CTEs that contain writes;
  - transactions;
  - SQLite-only commands (`PRAGMA`, `ATTACH`).

## b) Secrets within reach in a workspace (fake values only)
- **detect-secrets found:**
  - the password inside a database URL ("Basic Auth Credentials");
  - `password: …` in YAML ("Secret Keyword").
- **detect-secrets missed:**
  - `API_KEY=sk_test_<32 hex>` in `.env.prod`;
  - the same key base64-encoded in a text file.
- **Fix:** add a naming rule for `.env` and config files: any `*KEY*`, `*TOKEN*`, `*SECRET*` or `*PASSWORD*` name assigned a value of 8 characters or more. It caught the missed line.
- **Option:** GitGuardian's `ggshield` (needs a GitGuardian API key). It would show the sponsor's tool and is likely stronger, but wasn't tested.

## c) Exact-match tracing (dangerous call → the first input that contained the same value)
**Plain matching:**
- **Found the source:**
  - the same value;
  - a quoted value;
  - a value split in two (each half of 8 characters or more is still a substring of what the agent read).
- **Missed:**
  - an upper-cased value;
  - a base64-encoded value.

**With normalization** (compare in lower case, and also try base64, hex and URL decoding of each token in the call):
- the upper-cased, base64, hex and URL-encoded values all traced to the right step;
- a reversed value correctly found no match.

**Limits:**
- Transformations beyond these (encryption, rebuilding a value character by character, or a value computed from several reads) aren't traced by exact match. Jev's ranking of influences, with a confidence score, covers that, and is marked uncertain.
- Tokens shorter than 8 characters are ignored, to avoid false matches.

## d) Hash-chained event log
- **Speed:** chaining 10,000 events takes 16.8 ms, and checking them takes 15.5 ms.
- **What it detects:** an edited record (it points to the first bad record, #4321) and a deleted record (#5000).
- **Gap:** truncating the end of the log was **not detected**, because the chain is still consistent. **Fix:** anchor the head hash and record count somewhere else at each incident. Options:
  - a copy in S3 with Object Lock, which doesn't let anyone delete or overwrite it;
  - signing the head;
  - showing the head hash on the dashboard.

## What this changes in the plan
- **SQL:** add the `REPLACE INTO` keyword rule, and keep "unknown" as destructive.
- **Secret scan:** detect-secrets plus the naming rule (with ggshield as an option).
- **Tracing:** normalize case, base64, hex and URL encoding before exact matching.
- **Log:** anchor the head hash and record count outside the log (S3 Object Lock if AWS is used).
- **Jev:** the environment variable is `TYPESAFE_API_KEY`. Check the base URL and the rate limit live on day one.
