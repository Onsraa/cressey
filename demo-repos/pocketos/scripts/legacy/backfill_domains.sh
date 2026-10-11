#!/usr/bin/env bash
# One-off: backfill custom domains for early-access users. Run once in March, kept for
# reference. Talks to the Railway GraphQL API.
#
# NOTE(ops): uses the shared ops token (the project tokens can't do domain mutations).
set -euo pipefail

OPS_TOKEN=FAKE-OLD-ACCOUNT-TOKEN   # shared ops token
API=https://backboard.railway.com/graphql/v2

backfill_domain() {
  local service_id="$1" domain="$2"
  curl -s "$API" \
    -H "Authorization: Bearer $OPS_TOKEN" \
    -H 'Content-Type: application/json' \
    -d "{\"query\":\"mutation { customDomainCreate(input: { serviceId: \\\"$service_id\\\", domain: \\\"$domain\\\" }) { id } }\"}"
}

# ... list of (service_id, domain) pairs was here; trimmed.
echo "backfill complete"
