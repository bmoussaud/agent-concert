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
  }
}

// Deploy API Management using Azure Verified Module
module apim 'br/public:avm/res/api-management/service:0.14.1' = {
  name: 'apimDeployment'
  params: {
    name: 'apim-${resourceToken}'
    location: location
    tags: allTags
    publisherEmail: apimPublisherEmail
    publisherName: apimPublisherName
    sku: 'Consumption'
    diagnosticSettings: [
      {
        workspaceResourceId: logAnalyticsWorkspace.outputs.resourceId
        name: 'apimDiag'
      }
    ]
  }
}

// Configure setlist.fm API in APIM
module setlistfmApi 'modules/apim-setlistfm-api.bicep' = {
  name: 'setlistfmApiDeployment'
  params: {
    apimName: apim.outputs.name
    setlistfmApiKey: setlistfmApiKey
    apiPath: 'setlistfm'
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
output AZURE_SETLISTFM_API_NAME string = setlistfmApi.outputs.apiName
output AZURE_SETLISTFM_API_PATH string = 'https://${apim.outputs.name}.azure-api.net/setlistfm'
output AZURE_SETLISTFM_SUBSCRIPTION_NAME string = setlistfmApi.outputs.subscriptionDisplayName
