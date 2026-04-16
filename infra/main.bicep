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

@description('Tags to apply to all resources.')
param tags object = {}

var resourceToken = toLower(uniqueString(resourceGroup().id, environmentName, location))

var allTags = union(tags, {
  'azd-env-name': environmentName
})

// Deploy User-Assigned Managed Identity using Azure Verified Module
module managedIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.5.0' = {
  name: 'managedIdentityDeployment'
  params: {
    name: 'mi-${resourceToken}'
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
module applicationInsights 'br/public:avm/res/insights/component:0.7.0' = {
  name: 'applicationInsightsDeployment'
  params: {
    name: 'app-insights-${resourceToken}'
    location: location
    tags: allTags
    workspaceResourceId: logAnalyticsWorkspace.outputs.resourceId
  }
}

// Deploy AI Foundry (Cognitive Services AIServices account) with model deployments using Azure Verified Module
module aiFoundry 'br/public:avm/res/cognitive-services/account:0.14.2' = {
  name: 'aiFoundryDeployment'
  params: {
    name: 'foundry-${resourceToken}'
    kind: 'AIServices'
    location: aiFoundryLocation
    tags: allTags
    customSubDomainName: 'foundry-${resourceToken}'
    allowProjectManagement: true
    publicNetworkAccess: 'Enabled'
    managedIdentities: {
      systemAssigned: true
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

// Connect Application Insights to the AI Foundry account
resource aiFoundryAccount 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = {
  name: aiFoundry.outputs.name
}

resource connectionAppInsight 'Microsoft.CognitiveServices/accounts/connections@2025-12-01' = {
  parent: aiFoundryAccount
  name: 'appinsights-connection'
  properties: {
    category: 'AppInsights'
    target: applicationInsights.outputs.resourceId
    authType: 'ApiKey'
    credentials: {
      key: applicationInsights.outputs.connectionString
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: applicationInsights.outputs.resourceId
    }
  }
}

// Deploy AI Foundry Project
module aiFoundryProject 'modules/ai-foundry-project.bicep' = {
  name: 'aiFoundryProjectDeployment'
  params: {
    location: aiFoundryLocation
    aiFoundryName: aiFoundry.outputs.name
    aiProjectName: 'project-${environmentName}'
    aiProjectFriendlyName: 'Content Understanding Project - ${environmentName}'
    aiProjectDescription: 'AI Foundry project for content understanding.'
    managedIdentityPrincipalId: managedIdentity.outputs.principalId
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
