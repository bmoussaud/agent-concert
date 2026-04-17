targetScope = 'resourceGroup'

@minLength(1)
@maxLength(64)
@description('Name of the environment which is used to generate a short unique hash used in all resources.')
param environmentName string

@minLength(1)
@description('Primary location for all resources.')
param location string

@description('Location for AI Foundry resources.')
param aiFoundryLocation string = location

@description('Publisher email address for API Management.')
param apimPublisherEmail string

@description('Publisher name for API Management.')
param apimPublisherName string

@description('setlist.fm API key for accessing the setlist.fm API.')
@secure()
param setlistfmApiKey string

var projectPrefix = 'agent-concert'

@description('Tags to apply to all resources.')
param tags object = {}

var resourceToken = toLower(uniqueString(resourceGroup().id, environmentName, projectPrefix, location))

var allTags = union(tags, {
  'azd-env-name': environmentName
})

// Deploy User-Assigned Managed Identity using Azure Verified Module
module managedIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.5.0' = {
  name: 'managedIdentityDeployment'
  params: {
    name: 'mi-${projectPrefix}${resourceToken}'
    location: location
    tags: allTags
  }
}

// Deploy Log Analytics Workspace using Azure Verified Module
module logAnalyticsWorkspace 'br/public:avm/res/operational-insights/workspace:0.15.0' = {
  name: 'logAnalyticsWorkspaceDeployment'
  params: {
    name: 'log-analytics-${resourceToken}'
    location: location
    tags: allTags
  }
}

// Deploy Application Insights using Azure Verified Module
module applicationInsights 'br/public:avm/res/insights/component:0.7.1' = {
  name: 'application-insights'
  params: {
    name: 'app-insights-${resourceToken}'
    location: location
    tags: tags
    workspaceResourceId: logAnalyticsWorkspace.outputs.resourceId
  }
}

// Deploy AI Foundry (Cognitive Services AIServices account) with model deployments using Azure Verified Module
module aiFoundry 'br/public:avm/res/cognitive-services/account:0.14.2' = {
  name: 'aiFoundryDeployment'
  params: {
    name: 'foundry-${projectPrefix}-${resourceToken}'
    kind: 'AIServices'
    location: aiFoundryLocation
    tags: allTags
    customSubDomainName: 'foundry-${projectPrefix}-${resourceToken}'
    allowProjectManagement: true
    publicNetworkAccess: 'Enabled'
    managedIdentities: {
      systemAssigned: true
      userAssignedResourceIds: [
        managedIdentity.outputs.resourceId
      ]
    }
    deployments: [
      {
        name: 'gpt-4.1-mini'
        model: {
          format: 'OpenAI'
          name: 'gpt-4.1-mini'
          version: '2025-04-14'
        }
        sku: {
          capacity: 1
          name: 'GlobalStandard'
        }
      }
    ]
  }
}

// Deploy AI Foundry Project
module aiFoundryProject 'modules/ai-foundry-project.bicep' = {
  name: 'aiFoundryProjectDeployment'
  params: {
    location: aiFoundryLocation
    aiFoundryName: aiFoundry.outputs.name
    aiProjectName: 'project-${environmentName}'
    aiProjectFriendlyName: '${projectPrefix} Project - ${environmentName}'
    aiProjectDescription: 'AI Foundry project for ${projectPrefix}.'
    applicationInsightsName: applicationInsights.outputs.name
    managedIdentityPrincipalId: managedIdentity.outputs.principalId
    setlistfmMcpUrl: 'https://${apim.outputs.name}.azure-api.net/setlistfm-mcp'
  }
}

// Deploy API Management using Azure Verified Module
module apim 'br/public:avm/res/api-management/service:0.14.1' = {
  name: 'apimDeployment'
  params: {
    name: 'apim-${projectPrefix}-${resourceToken}'
    location: location
    tags: allTags
    publisherEmail: apimPublisherEmail
    publisherName: apimPublisherName
    sku: 'BasicV2'
    diagnosticSettings: [
      {
        workspaceResourceId: logAnalyticsWorkspace.outputs.resourceId
        name: 'apimDiag'
      }
    ]
    
    // Named Values: Store the setlist.fm API key
    namedValues: [
      {
        name: 'setlistfm-api-key'
        displayName: 'setlistfm-api-key'
        secret: true
        value: setlistfmApiKey
        tags: [
          'setlistfm'
          'api-key'
        ]
      }
    ]
    
    // APIs: Import setlist.fm API from OpenAPI spec with policy
    apis: [
      {
        name: 'setlistfm-api'
        displayName: 'setlist.fm API'
        description: 'Access to setlist.fm API for concert setlist data'
        path: 'setlistfm'
        protocols: [
          'https'
        ]
        subscriptionRequired: true
        type: 'http'
        format: 'swagger-link-json'
        value: 'https://api.setlist.fm/docs/1.0/ui/swagger.json'
        serviceUrl: 'https://api.setlist.fm/rest'
        policies: [
          {
            value: loadTextContent('policies/setlistfm-api-policy.xml')
            format: 'xml'
          }
        ]
      }
    ]
    
    // Subscriptions: Create dedicated subscription for setlist.fm API
    subscriptions: [
      {
        name: 'setlistfm-api-subscription'
        displayName: 'setlistfm-api'
        scope: '/apis/setlistfm-api'
        allowTracing: true
      }
    ]
  }
}

module setlistFmMCP 'modules/mcp-api.bicep' =  {
  name: 'setlistfm-mcp'
  params: {
    apimName: apim.outputs.name
    apiName: 'setlistfm-api'
    mcp:  {
      name: 'setlistfm-mcp'
      description: 'Setlist.fm MCP for concert details'
      displayName: 'Setlist.fm MCP'
      path: 'setlistfm-mcp'
      policyXml: loadTextContent('policies/setlistfm-mcp-policy.xml')
      tools :[
          {
            name:'searchForArtists'
            operationName:'resource__1-0_search_artists_getArtists_GET'
          }
          {
            name:'searchForSetlists'
            operationName:'resource__1-0_search_setlists_getSetlists_GET'
          }
        ]
    }
  }
}

output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = resourceGroup().name
output APPLICATIONINSIGHTS_CONNECTION_STRING string = applicationInsights.outputs.connectionString
output AZURE_AI_FOUNDRY_ENDPOINT string = aiFoundry.outputs.endpoint
output AZURE_AI_PROJECT_ENDPOINT string = aiFoundryProject.outputs.projectEndpoint
output AZURE_AI_MODEL_DEPLOYMENT_NAME string = 'gpt-4.1-mini'
output AZURE_MANAGED_IDENTITY_CLIENT_ID string = managedIdentity.outputs.clientId
output AZURE_MANAGED_IDENTITY_NAME string = managedIdentity.outputs.name
output AZURE_APIM_NAME string = apim.outputs.name
output AZURE_APIM_GATEWAY_URL string = 'https://${apim.outputs.name}.azure-api.net'
output AZURE_SETLISTFM_API_NAME string = 'setlistfm-api'
output AZURE_SETLISTFM_API_PATH string = 'https://${apim.outputs.name}.azure-api.net/setlistfm'
output AZURE_SETLISTFM_SUBSCRIPTION_NAME string = 'setlistfm-api'
output AZURE_TENANT_ID string = subscription().tenantId
