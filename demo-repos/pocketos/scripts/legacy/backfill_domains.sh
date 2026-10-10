#!/usr/bin/env bash
# One-off: backfill custom domains for early-access users. Run once in March, kept for
# reference. Talks to the Railway GraphQL API.
#
# NOTE(ops): this used the old account token because the domain mutations weren't available
# to the scoped project tokens back then. TODO rotate this out — it still has full access.
set -euo pipefail

RAILWAY_TOKEN=FAKE-OLD-ACCOUNT-TOKEN   # old account token, every project, every right
API=https://backboard.railway.com/graphql/v2

backfill_domain() {
  local service_id="$1" domain="$2"
  curl -s "$API" \
    -H "Authorization: Bearer $RAILWAY_TOKEN" \
    -H 'Content-Type: application/json' \
    -d "{\"query\":\"mutation { customDomainCreate(input: { serviceId: \\\"$service_id\\\", domain: \\\"$domain\\\" }) { id } }\"}"
}

# ... list of (service_id, domain) pairs was here; trimmed.
echo "backfill complete"
