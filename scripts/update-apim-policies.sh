#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POLICIES_DIR="$SCRIPT_DIR/../infra/policies"

echo "Updating APIM policies..."

# Get environment values
APIM_NAME=$(azd env get-values | grep AZURE_APIM_NAME | cut -d'=' -f2 | tr -d '"')
RESOURCE_GROUP=$(azd env get-values | grep AZURE_RESOURCE_GROUP | cut -d'=' -f2 | tr -d '"')

if [ -z "$APIM_NAME" ] || [ -z "$RESOURCE_GROUP" ]; then
  echo "Error: Could not retrieve AZURE_APIM_NAME or AZURE_RESOURCE_GROUP from azd environment"
  exit 1
fi

AZURE_SUBSCRIPTION_ID=$(az account show --query id --output tsv)
if [ -z "$AZURE_SUBSCRIPTION_ID" ]; then
  echo "Error: Could not retrieve Azure subscription ID"
  exit 1
fi

echo "APIM Instance:  $APIM_NAME"
echo "Resource Group: $RESOURCE_GROUP"
echo "Subscription:   $AZURE_SUBSCRIPTION_ID"
echo ""

# Helper: update one API's policy
# Usage: update_policy <api-id> <policy-file>
update_policy() {
  local API_ID="$1"
  local POLICY_FILE="$2"

  if [ ! -f "$POLICY_FILE" ]; then
    echo "  [SKIP] Policy file not found: $POLICY_FILE"
    return 1
  fi

  echo "  Updating policy for API '$API_ID' from $(basename "$POLICY_FILE") ..."

  local POLICY_XML
  POLICY_XML=$(cat "$POLICY_FILE")

  local JSON_BODY
  JSON_BODY=$(jq -n --arg val "$POLICY_XML" '{"properties":{"format":"rawxml","value":$val}}')

  az rest \
    --method put \
    --uri "/subscriptions/$AZURE_SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.ApiManagement/service/$APIM_NAME/apis/$API_ID/policies/policy?api-version=2022-08-01" \
    --body "$JSON_BODY" \
    --headers "Content-Type=application/json" \
    --output none

  echo "  [OK] $API_ID"
}

# Update all 4 policies
update_policy "setlistfm-api"  "$POLICIES_DIR/setlistfm-api-policy.xml"
update_policy "spotify-api"    "$POLICIES_DIR/spotify-api-policy.xml"
update_policy "setlistfm-mcp"  "$POLICIES_DIR/setlistfm-mcp-policy.xml"
update_policy "spotify-mcp"    "$POLICIES_DIR/spotify-mcp-policy.xml"

echo ""
echo "All 4 APIM policies updated successfully."
