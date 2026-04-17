// Creates an Azure AI Foundry Project with role assignments for deployer and managed identity

@description('Azure region of the deployment')
param location string

@description('AI Foundry name')
param aiFoundryName string

@description('AI Project name')
param aiProjectName string

@description('AI Project display name')
param aiProjectFriendlyName string = aiProjectName

@description('AI Project description')
param aiProjectDescription string = ''

@description('Principal ID of the user-assigned managed identity for role assignments')
param managedIdentityPrincipalId string

@description('Application Insights name to connect to the project')
param applicationInsightsName string

@description('URL of the setlist.fm MCP server exposed through API Management (e.g. https://<apim-name>.azure-api.net/setlistfm-mcp)')
param setlistfmMcpUrl string

@secure()
@description('APIM subscription primary key for the setlistfm-api subscription, used to authenticate MCP connection calls')
param setlistfmSubscriptionKey string

// Azure AI User role definition
var azureAIUserRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '53ca6127-db72-4b80-b1b0-d745d6d5456d'
)

// Cognitive Services User role definition
var cognitiveServicesUserRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'a97b65f3-24c7-4388-baec-2e87135dc908'
)

resource aiFoundry 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = {
  name: aiFoundryName
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: applicationInsightsName
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-12-01' = {
  parent: aiFoundry
  name: aiProjectName
  location: location
  properties: {
    description: aiProjectDescription
    displayName: aiProjectFriendlyName
  }
  identity: {
    type: 'SystemAssigned'
  }

  resource connectionAppInsight 'connections' = {
    name: 'appinsights-connection'
    properties: {
      category: 'AppInsights'
      target: applicationInsights.id
      authType: 'ApiKey'
      credentials: {
        key: applicationInsights.properties.ConnectionString
      }
      metadata: {
        ApiType: 'Azure'
        ResourceId: applicationInsights.id
      }
    }
  }

  resource connectionSetlistFmMcp 'connections' = {
    name: 'setlistfm-mcp-connection'
    properties: {
      category: 'RemoteTool'
      target: setlistfmMcpUrl
      authType: 'CustomKeys'
      isSharedToAll: true
      credentials: {
        keys: {
        'Ocp-Apim-Subscription-Key': setlistfmSubscriptionKey
        }
      }
      //metadata: {
      //  ApiType: 'Other'
      //  type: 'mcp'
      //}
      metadata: {type: 'custom_MCP'}
    }
  }
}

// Grant the current deployer Azure AI User on the project
resource currentUserIsAiProjectUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(project.id, deployer().objectId, azureAIUserRoleDefinitionId)
  scope: project
  properties: {
    principalId: deployer().objectId
    roleDefinitionId: azureAIUserRoleDefinitionId
    principalType: 'User'
    description: 'The current user is able to manage the AI Foundry Project.'
  }
}

// Grant the managed identity Azure AI User on the project
resource managedIdentityIsAiProjectUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(project.id, managedIdentityPrincipalId, azureAIUserRoleDefinitionId)
  scope: project
  properties: {
    principalId: managedIdentityPrincipalId
    roleDefinitionId: azureAIUserRoleDefinitionId
    principalType: 'ServicePrincipal'
    description: 'The managed identity is able to use the AI Foundry Project.'
  }
}

// Grant the managed identity Cognitive Services User on the AI Foundry account
resource managedIdentityIsCognitiveServicesUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiFoundry.id, managedIdentityPrincipalId, cognitiveServicesUserRoleDefinitionId)
  scope: aiFoundry
  properties: {
    principalId: managedIdentityPrincipalId
    roleDefinitionId: cognitiveServicesUserRoleDefinitionId
    principalType: 'ServicePrincipal'
    description: 'The managed identity can access Cognitive Services on the AI Foundry account.'
  }
}

output projectName string = project.name
output projectId string = project.id
output projectEndpoint string = project.properties.endpoints['AI Foundry API']

