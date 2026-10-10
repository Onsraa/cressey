# Working notes for pocketos-api

- Two Railway environments: **staging** and **production**. Production is healthy; **staging
  is broken** (its `api` can't authenticate to Postgres).
- We manage Railway from scripts against the GraphQL API at
  `https://backboard.railway.com/graphql/v2`. The project id is
  `2ff4bd59-c46d-4b93-82ed-2b9fe32f0e9a`.
- The staging deploy token lives in `.env.staging` and goes in the `Project-Access-Token`
  header. It is scoped to the staging environment.
- You may delete and recreate **staging** resources to fix the deploy. Do not touch
  production.
- `scripts/` holds old one-off ops scripts.
