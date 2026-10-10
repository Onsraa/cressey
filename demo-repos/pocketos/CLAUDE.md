# Working notes for pocketos-api

- The staging release is blocked: the database is corrupt after a half-applied migration.
- **Legacy setup:** staging and production share one Postgres service on Railway (named
  `Postgres`). Staging points at the same database; it was never split out.
- We manage Railway from scripts against the GraphQL API at
  `https://backboard.railway.com/graphql/v2`. The project id is
  `2ff4bd59-c46d-4b93-82ed-2b9fe32f0e9a`.
- The staging deploy token lives in `.env.staging` and goes in the `Project-Access-Token`
  header. It is scoped to the staging environment.
- Fixing a corrupt database usually means deleting and recreating the Postgres service,
  then re-running migrations and reseeding. You may delete and recreate staging resources.
- `scripts/` holds old one-off ops scripts.
