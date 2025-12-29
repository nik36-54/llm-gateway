#!/bin/bash
# Test script for cost analytics API endpoints

API_KEY="${1:-your-api-key-here}"
BASE_URL="${2:-http://localhost:8000}"

echo "=== Testing Cost Analytics API ==="
echo "Using API Key: ${API_KEY:0:10}..."
echo "Base URL: $BASE_URL"
echo ""

echo "1. Getting Cost Summary (all time)"
curl -X GET "$BASE_URL/v1/costs" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" | jq '.'

echo -e "\n\n2. Getting Cost Summary (OpenAI only)"
curl -X GET "$BASE_URL/v1/costs?provider=openai" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" | jq '{total_cost_usd, total_requests, by_provider}'

echo -e "\n\n3. Getting Recent Cost Records (last 10)"
curl -X GET "$BASE_URL/v1/costs/records?limit=10" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" | jq '.[] | {request_id, provider, model, cost_usd, tokens_in, tokens_out}'

echo -e "\n\n4. Getting Cost Records for DeepSeek"
curl -X GET "$BASE_URL/v1/costs/records?provider=deepseek&limit=5" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" | jq '.'

echo -e "\n\n=== Test Complete ==="

