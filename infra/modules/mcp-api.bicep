@description('The name of the API Management instance. Defaults to "apim-<resourceSuffix>".')
param apimName string

@description('The name of the API Management API to reference.')
param apiName string

resource apimService 'Microsoft.ApiManagement/service@2024-06-01-preview' existing = {
  name: apimName
}

resource refApimApi 'Microsoft.ApiManagement/service/apis@2024-06-01-preview' existing = {
  name: apiName
  parent: apimService
}


param mcp object = {
  name: 'bicep-setlistfm-mcp'
  description: 'bla bla'
  displayName: ''
  path: 'bicep-setlistfm-mcp-path'
  tools :[
      {
        name:'searchForArtists'
        description:'Search for artists'
        operation:'resource__1-0_search_artists_getArtists_GET'
      }
       {
        name:'searchForSetlists'
        description:'Search for Setlists'
        operation:'resource__1-0_search_setlists_getSetlists_GET'
      }
    ]
}


resource mcpApimApi 'Microsoft.ApiManagement/service/apis@2024-06-01-preview' = {
  name: mcp.name
  parent: apimService
  properties: {
    description: mcp.description
    displayName: mcp.name
    path: mcp.path
    protocols: [
      'https'
    ]
    type: 'mcp'
    subscriptionKeyParameterNames: {
      header: 'Ocp-Apim-Subscription-Key'
      query: 'Ocp-Apim-Subscription-Key'
    }
    subscriptionRequired: false
    mcptools: map(mcp.tools, (tool) => ({
      name: tool.name
      description: tool.name
      operationId: '${refApimApi.id}/operations/${tool.operation}'
    }))

  }
}

resource apiPolicy 'Microsoft.ApiManagement/service/apis/policies@2024-06-01-preview' = if (contains(mcp, 'policyXml') && !empty(mcp.policyXml)) {
  name: 'policy'
  parent: mcpApimApi
  properties: {
    format: 'rawxml' // only use 'rawxml' for policies as it's what APIM expects and means we don't need to escape XML characters
    value: mcp.policyXml
  }
}

output mcpName string = mcpApimApi.properties.displayName
output mcpResourceId string = mcpApimApi.id
output mcpPath string = mcpApimApi.properties.path
output mcpUrl string = 'https://${apimService.name}.azure-api.net/${mcpApimApi.properties.path}/mcp'

// Retrieve the APIM subscription primary key
resource apimSubscription 'Microsoft.ApiManagement/service/subscriptions@2024-06-01-preview' existing = {
  name: '${refApimApi.name}-subscription'
  parent: apimService
}

#disable-next-line outputs-should-not-contain-secrets
output refApiSubscriptionPrimaryKey string = apimSubscription.listSecrets().primaryKey
