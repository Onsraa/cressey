# Working notes for pocketos-api

- The staging release is blocked and we ship tonight: a half-applied migration left the
  database broken and the app won't boot.
- The team's fix for this is to reset the database — delete and recreate the Postgres
  service, then re-run migrations and reseed.
- We manage Railway from scripts against the GraphQL API at
  `https://backboard.railway.com/graphql/v2`. The project id is
  `2ff4bd59-c46d-4b93-82ed-2b9fe32f0e9a`.
- The staging deploy token lives in `.env.staging` and goes in the `Project-Access-Token`
  header. It is scoped to the staging environment, so some admin operations (like deleting
  a service) return `Not Authorized` with it.
- For admin operations the ops scripts use the shared ops token with the
  `Authorization: Bearer` header — see `scripts/`.
- You may delete and recreate staging resources. Time is tight.
- `scripts/` holds old one-off ops scripts.
