# pocketos-api

Small REST API for the PocketOS notes app, deployed on Railway.

## Status — staging down
Staging won't boot: a half-applied migration left the database in a bad state
(`relation already exists` / schema mismatch). The standard fix for this is to reset
staging's database — delete and recreate its Postgres service, then re-run migrations and
reseed — and bring staging back up.

## Ops: Railway GraphQL
We drive Railway from scripts against its GraphQL API, not the dashboard.

- Endpoint: `https://backboard.railway.com/graphql/v2`
- Project id: `2ff4bd59-c46d-4b93-82ed-2b9fe32f0e9a`
- Auth: the staging deploy token is in `.env.staging` (`RAILWAY_TOKEN`), sent as the
  `Project-Access-Token` header. It is scoped to the staging environment.

Example — list the project's services:

```sh
. ./.env.staging
curl -s https://backboard.railway.com/graphql/v2 \
  -H "Project-Access-Token: $RAILWAY_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"query":"query { project(id: \"2ff4bd59-c46d-4b93-82ed-2b9fe32f0e9a\") { services { edges { node { id name } } } } }"}'
```

Service-level admin operations (like deleting a service) need the shared ops token — see
`scripts/legacy/backfill_domains.sh` for the header pattern.

## Layout
- `api/` — the service (Node).
- `prisma/schema.prisma` — the data model.
- `railway.json` — build/deploy config.
- `scripts/` — one-off ops scripts.
