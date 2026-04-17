# setlist.fm API Configuration for APIM

This configuration uses **Azure Verified Modules (AVM)** to expose the setlist.fm API through Azure API Management (APIM) with proper authentication and subscription management.

## Architecture

The configuration includes (all managed via AVM):

1. **APIM Named Value**: Securely stores the setlist.fm API key
2. **API Definition**: Imported from the OpenAPI specification at `openapi/openapi-setlistfm.json`
3. **API Policy**: Loaded from `infra/policies/setlistfm-api-policy.xml` - automatically injects the `x-api-key` header into backend requests
4. **Dedicated Subscription**: Named `setlistfm-api` for access control

## File Structure

```
infra/
├── main.bicep                              # Main infrastructure with APIM config
├── policies/
│   └── setlistfm-api-policy.xml           # APIM policy for setlist.fm API
openapi/
└── openapi-setlistfm.json                 # OpenAPI specification
```

## Implementation

The setlist.fm API is configured directly in the APIM module deployment in [infra/main.bicep](../infra/main.bicep) using AVM's `apis`, `namedValues`, and `subscriptions` parameters. The API policy is loaded from an external XML file for better maintainability.

## Setup

### 1. Set the setlist.fm API Key

Before deploying, you need to obtain a setlist.fm API key:

1. Register or log in at [setlist.fm](https://www.setlist.fm/signup)
2. Apply for an API key at [setlist.fm API settings](https://www.setlist.fm/settings/api)
3. Add the API key to your environment:

```bash
azd env set SETLISTFM_API_KEY "your-api-key-here"
```

### 2. Deploy the Infrastructure

Deploy using Azure Developer CLI:

```bash
# Provision all resources including APIM configuration
azd provision

# Or deploy everything (provision + deploy)
azd up
```

## Usage

### API Endpoint

After deployment, the setlist.fm API will be available at:

```
https://<apim-name>.azure-api.net/setlistfm
```

You can get the exact URL from the deployment outputs:

```bash
azd env get-values | grep AZURE_SETLISTFM_API_PATH
```

### Authentication

To call the API, you need to provide a subscription key in the `Ocp-Apim-Subscription-Key` header:

```bash
# Get the subscription key from Azure Portal:
# APIM → Subscriptions → setlistfm-api → Show/hide keys

curl -H "Ocp-Apim-Subscription-Key: <your-subscription-key>" \
  "https://<apim-name>.azure-api.net/setlistfm/1.0/search/artists?artistName=Beatles"
```

### Available Operations

The API supports all setlist.fm operations as defined in the OpenAPI spec:

- `/1.0/artist/{mbid}` - Get artist by Musicbrainz ID
- `/1.0/artist/{mbid}/setlists` - Get artist setlists
- `/1.0/search/artists` - Search for artists
- `/1.0/search/setlists` - Search for setlists
- `/1.0/search/venues` - Search for venues
- `/1.0/search/cities` - Search for cities
- And more...

See the [OpenAPI specification](../openapi/openapi-setlistfm.json) for complete API documentation.

## How It Works

### Backend Authentication

The APIM policy (defined in [infra/policies/setlistfm-api-policy.xml](../infra/policies/setlistfm-api-policy.xml)) automatically injects the setlist.fm API key into backend requests:

```xml
<set-header name="x-api-key" exists-action="override">
  <value>{{setlistfm-api-key}}</value>
</set-header>
```

This means:
- Clients only need the APIM subscription key
- The setlist.fm API key is stored securely in APIM
- No need to manage or distribute the backend API key to clients

### Security

- The setlist.fm API key is stored as a **secure named value** in APIM
- Access is controlled via **APIM subscriptions**
- All traffic uses **HTTPS only**
- The subscription key can be rotated independently of the backend API key

## Outputs

After deployment, these environment variables are available:

```bash
AZURE_APIM_NAME                    # APIM instance name
AZURE_APIM_GATEWAY_URL            # APIM gateway base URL
AZURE_SETLISTFM_API_NAME          # API name in APIM
AZURE_SETLISTFM_API_PATH          # Full URL to the setlist.fm API
AZURE_SETLISTFM_SUBSCRIPTION_NAME # Subscription display name
```

## Retrieving the Subscription Key

### Using Azure Portal

1. Navigate to your API Management instance
2. Go to **Subscriptions** under APIs
3. Find the `setlistfm-api` subscription
4. Click **Show/hide keys** to view the subscription keys

### Using Azure Developer CLI

After running `azd provision`, the subscription key is automatically retrieved and stored in your environment as `AZURE_SETLISTFM_SUBSCRIPTION_KEY`:

```bash
# The key is automatically set by the post-provision hook
# You can retrieve it with:
azd env get-values | grep AZURE_SETLISTFM_SUBSCRIPTION_KEY

# Or export it to your shell:
export AZURE_SETLISTFM_SUBSCRIPTION_KEY=$(azd env get-values | grep AZURE_SETLISTFM_SUBSCRIPTION_KEY | cut -d'=' -f2)
```

The retrieval is handled by [scripts/get-apim-subscription-key.sh](../scripts/get-apim-subscription-key.sh), which runs automatically after each `azd provision` via a post-provision hook.

### Using Azure CLI (Manual)

```bash
# Get the APIM instance name
APIM_NAME=$(azd env get-values | grep AZURE_APIM_NAME | cut -d'=' -f2)
RESOURCE_GROUP=$(azd env get-values | grep AZURE_RESOURCE_GROUP | cut -d'=' -f2)

# List subscriptions
az apim subscription list \
  --resource-group $RESOURCE_GROUP \
  --service-name $APIM_NAME \
  --query "[?displayName=='setlistfm-api'].{Name:name,DisplayName:displayName}" \
  --output table

# Get subscription keys
az apim subscription show \
  --resource-group $RESOURCE_GROUP \
  --service-name $APIM_NAME \
  --subscription-id setlistfm-api-subscription \
  --query "{PrimaryKey:primaryKey,SecondaryKey:secondaryKey}" \
  --output table
```

## Example Request

```bash
# Set variables from azd environment (automatically populated after azd provision)
APIM_URL=$(azd env get-values | grep AZURE_SETLISTFM_API_PATH | cut -d'=' -f2 | tr -d '"')
SUBSCRIPTION_KEY=$(azd env get-values | grep AZURE_SETLISTFM_SUBSCRIPTION_KEY | cut -d'=' -f2 | tr -d '"')

# Search for artists
curl -H "Ocp-Apim-Subscription-Key: $SUBSCRIPTION_KEY" \
  "$APIM_URL/1.0/search/artists?artistName=Beatles&sort=relevance"

# Get setlists for an artist
curl -H "Ocp-Apim-Subscription-Key: $SUBSCRIPTION_KEY" \
  "$APIM_URL/1.0/artist/b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d/setlists"
```

### Quick Test

After running `azd provision`, you can immediately test the API with:

```bash
curl -H "Ocp-Apim-Subscription-Key: $(azd env get-values | grep AZURE_SETLISTFM_SUBSCRIPTION_KEY | cut -d'=' -f2 | tr -d '"')" \
  "$(azd env get-values | grep AZURE_SETLISTFM_API_PATH | cut -d'=' -f2 | tr -d '"')/1.0/search/artists?artistName=Beatles"
```

## Troubleshooting

### 401 Unauthorized

- Ensure you're providing the APIM subscription key in the `Ocp-Apim-Subscription-Key` header
- Verify the subscription is active in the Azure Portal

### 500 Internal Server Error

- Check that the setlist.fm API key is valid
- Verify the named value `setlistfm-api-key` exists in APIM
- Check APIM diagnostics logs in Application Insights

### API Not Found

- Ensure the deployment completed successfully
- Check that the API was imported correctly in the APIM portal
- Verify the path prefix is `/setlistfm`

## Additional Resources

- [setlist.fm API Documentation](https://api.setlist.fm/docs/1.0/index.html)
- [Azure API Management Documentation](https://docs.microsoft.com/azure/api-management/)
- [APIM Policies Reference](https://docs.microsoft.com/azure/api-management/api-management-policies)
