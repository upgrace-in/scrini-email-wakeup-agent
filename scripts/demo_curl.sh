#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

echo "Kick outreach..."
CONV_JSON="$(curl -sS -X POST "${BASE_URL}/v1/agent/outreach" \
  -H 'content-type: application/json' \
  -d '{"prospect_email":"you+scrini_demo@yourdomain.dev","preset_key":"default_demo","idempotency_key":"scrini_demo_v1"}')"

CONV_ID="$(python -c 'import json,sys; print(json.loads(sys.argv[1])["conversation_id"])' "${CONV_JSON}")"

echo "Conversation: ${CONV_ID}"

echo "Inbound: negotiation prompt..."
curl -sS -X POST "${BASE_URL}/internal/simulations/${CONV_ID}/inbound" \
  -H 'content-type: application/json' \
  -d "{\"text_body\":\"Hi — love the tooling angle.What's the rate envelope? Flexible if remote async work is kosher.\",\"provider_message_id\":\"demo-inbound-$(date +%s)\"}"

echo ""
echo "Inbound: choose stub slot..."
curl -sS -X POST "${BASE_URL}/internal/simulations/${CONV_ID}/inbound" \
  -H 'content-type: application/json' \
  -d "{\"text_body\":\"Let us book 2026-05-13T16:30:00+00:00\",\"provider_message_id\":\"demo-slot-$(date +%s)\"}"

echo ""
echo "Inbound: cancellation / reschedule cue..."
curl -sS -X POST "${BASE_URL}/internal/simulations/${CONV_ID}/inbound" \
  -H 'content-type: application/json' \
  -d "{\"text_body\":\"So sorry — an exec review moved. Can't make May 13. Can we do May 14 10 UTC instead?\",\"provider_message_id\":\"demo-cancel-$(date +%s)\"}"

echo ""
echo "Inbound: reaffirm fallback slot..."
curl -sS -X POST "${BASE_URL}/internal/simulations/${CONV_ID}/inbound" \
  -H 'content-type: application/json' \
  -d "{\"text_body\":\"Yes lock 2026-05-14T10:00:00+00:00\",\"provider_message_id\":\"demo-rebook-$(date +%s)\"}"

echo ""
echo "Snapshot transcript..."
curl -sS "${BASE_URL}/internal/conversations/${CONV_ID}" | python -m json.tool
