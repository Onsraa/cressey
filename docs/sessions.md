# Synthetic sessions

The demo agent replays these files through Cressey: `backend/data/sessions/*.yaml`. They are test data written by the team: synthetic, with fake values only.

## Format
| Field | Meaning |
|---|---|
| `id` | the file name without `.yaml` |
| `expect` | `held` for an incident session, `free` for a normal one: what Cressey should do |
| `variant_of` | for an attack variant, the incident session it varies. « Rejouer ×5 » plays that session and its variants |
| `task` | the task text, as its author wrote it |
| `mandate` | `may_destroy` (tables), `may_send_to` (addresses or `@domain`), `may_read_secrets` (secret names). All optional |
| `visibility` | `tools`, `messages` (default) or `reasoning` |
| `steps` | the calls in order: `call` (the tool), `args`, optionally `say` (what the agent says just before the call), and `stop_if_error: true` when the agent needs that call's result: it stops if the call fails |
| `report` | the final report when nothing was refused |
| `report_if_blocked` | the final report after Cressey refused a call |

**Demo tools:**
- `read_file(path)` and `write_file(path, content)`: the workspace holds `README.md` and `.env.prod` (the fake production key).
- `run_tests()`: fails while the `users` table has rows.
- `run_sql(query, key)`: the production database holds 5 fake users and needs the production key.
- `send_email(to, subject, body)`: goes to a local outbox.

## Play
```
cd backend
uv run python -m cressey.demo.agent data/sessions/<id>.yaml --kind live --pace 1.5
```
- `live`: a held call waits for a decision on the dashboard.
- `control` (« Observateur »): nothing is held, so the record can show the lie.
- `replay`: nothing waits; a call that would be held is refused.

The scripted agent stops on a refusal from Cressey, or when a call marked `stop_if_error` fails. The five incident sessions mark their read of `.env.prod`: once the key is moved out of the workspace, they stop there.

`--url` points at another server (default `http://localhost:8000`). `--pace` sets the seconds between calls.

## Shipped sessions
- **Incidents** (`expect: held`): `demo-tests-impossibles` (the demo's DELETE), `variant-drop-table`, `variant-update-sans-where`, `variant-cle-par-email`, `variant-cle-base64`.
- **Normal** (`expect: free`): `normal-readme`, `normal-lire-version`, `normal-email-equipe`, `normal-nettoyage-mandat` (a deletion the mandate allows), `normal-tests-rapport`.

`cd backend && uv run python -m cressey.demo.evaluate` plays them all and reports the misses.

## Rules
- Fake values only. Never a real-looking provider key.
- The held-out sessions are written by someone outside the team.
