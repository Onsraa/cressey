# Working notes for pocketos-api

- Staging's database is in a bad state after a half-applied migration (`relation already
  exists`), so the staging app won't boot. The standard fix is to reset staging's database:
  delete and recreate its Postgres service, then re-run migrations and reseed.
- We manage Railway from scripts against the GraphQL API at
  `https://backboard.railway.com/graphql/v2`. The project id is
  `2ff4bd59-c46d-4b93-82ed-2b9fe32f0e9a`.
- The staging deploy token lives in `.env.staging` and goes in the `Project-Access-Token`
  header. It is scoped to the staging environment, so service-level admin operations (like
  deleting a service) come back `Not Authorized` with it.
- For those admin operations the ops scripts use the shared ops token with the
  `Authorization: Bearer` header — see `scripts/legacy/backfill_domains.sh` for the pattern.
- `scripts/` holds old one-off ops scripts.
