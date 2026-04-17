#!/bin/bash
set -e

echo "Retrieving APIM subscription key..."

# Get environment values
APIM_NAME=$(azd env get-values | grep AZURE_APIM_NAME | cut -d'=' -f2 | tr -d '"')
RESOURCE_GROUP=$(azd env get-values | grep AZURE_RESOURCE_GROUP | cut -d'=' -f2 | tr -d '"')
SUBSCRIPTION_NAME="setlistfm-api-subscription"

if [ -z "$APIM_NAME" ] || [ -z "$RESOURCE_GROUP" ]; then
  echo "Error: Could not retrieve APIM_NAME or RESOURCE_GROUP from azd environment"
  exit 1
fi

echo "APIM Instance: $APIM_NAME"
echo "Resource Group: $RESOURCE_GROUP"
echo "Subscription: $SUBSCRIPTION_NAME"

# Get the Azure subscription ID
AZURE_SUBSCRIPTION_ID=$(az account show --query id --output tsv)

if [ -z "$AZURE_SUBSCRIPTION_ID" ]; then
  echo "Error: Could not retrieve Azure subscription ID"
  exit 1
fi

# Retrieve the primary subscription key using REST API
SUBSCRIPTION_KEY=$(az rest \
  --method post \
  --uri "/subscriptions/$AZURE_SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.ApiManagement/service/$APIM_NAME/subscriptions/$SUBSCRIPTION_NAME/listSecrets?api-version=2022-08-01" \
  --query "primaryKey" \
  --output tsv)

if [ -z "$SUBSCRIPTION_KEY" ]; then
  echo "Error: Could not retrieve subscription key"
  exit 1
fi

# Store in azd environment
azd env set AZURE_SETLISTFM_SUBSCRIPTION_KEY "$SUBSCRIPTION_KEY"

echo "✅ Subscription key successfully stored in azd environment as AZURE_SETLISTFM_SUBSCRIPTION_KEY"
echo "   You can retrieve it with: azd env get-values | grep AZURE_SETLISTFM_SUBSCRIPTION_KEY"
