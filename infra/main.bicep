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

@description('Spotify Client ID for MCP Spotify microservice.')
param spotifyClientId string

@description('Spotify Client Secret for MCP Spotify microservice.')
@secure()
param spotifyClientSecret string

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
        name: 'gpt-4.1'
        model: {
          format: 'OpenAI'
          name: 'gpt-4.1'
          version: '2025-04-14'
        }
        sku: {
          capacity: 500
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
    aiProjectName: '${projectPrefix}-${environmentName}'
    aiProjectFriendlyName: '${projectPrefix} Project - ${environmentName}'
    aiProjectDescription: 'AI Foundry project for ${projectPrefix}.'
    applicationInsightsName: applicationInsights.outputs.name
    managedIdentityPrincipalId: managedIdentity.outputs.principalId
    setlistfmMcpUrl: setlistFmMCP.outputs.mcpUrl
    setlistfmSubscriptionKey: setlistFmMCP.outputs.refApiSubscriptionPrimaryKey
    spotifyMcpUrl: spotifyMCP.outputs.mcpUrl
    spotifyClientId: spotifyClientId
    spotifyClientSecret: spotifyClientSecret
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

    products: [
      {
        name: 'mcp-product'
        displayName: 'mcp-product'
        description: 'MCP API'
        subscriptionRequired: false
        approvalRequired: false
        state: 'published'
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
    loggers: [
      {
        credentials: {
          instrumentationKey: applicationInsights.outputs.instrumentationKey
        }
        description: 'Logger to Azure Application Insights'
        isBuffered: false
        name: 'logger'
        targetResourceId: applicationInsights.outputs.resourceId
        type: 'applicationInsights'
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
            format: 'rawxml'
          }
        ]
        diagnostics: [
          {
            loggerName: 'logger'
            metrics: true
            name: 'applicationinsights'
            verbosity: 'verbose'
            httpCorrelationProtocol:'W3C'
            alwaysLog: 'allErrors'
            frontend: {request: {body:{bytes:8000}}, response: {body:{bytes:8000}}}
            backend: {request: {body:{bytes:8000}}, response: {body:{bytes:8000}}}
          }
        ]
      }
      {
        name: 'spotify-api'
        displayName: 'Spotify Web API'
        description: 'Access to Spotify Web API for music data'
        path: 'spotify'
        protocols: [
          'https'
        ]
        subscriptionRequired: false
        type: 'http'
        format: 'openapi'
        value: loadTextContent('openapi/spotify-openapi-trimmed.yml')
        serviceUrl: 'https://api.spotify.com/v1'
        policies: [
          {
            value: loadTextContent('policies/spotify-api-policy.xml')
            format: 'rawxml'
          }
        ]
        diagnostics: [
          {
            loggerName: 'logger'
            metrics: true
            name: 'applicationinsights'
            verbosity: 'verbose'
            httpCorrelationProtocol:'W3C'
            alwaysLog: 'allErrors'
            frontend: {request: {body:{bytes:8000}}, response: {body:{bytes:8000}}}
            backend: {request: {body:{bytes:8000}}, response: {body:{bytes:8000}}}
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
      {
        name: 'spotify-api-subscription'
        displayName: 'spotify-api'
        scope: '/apis/spotify-api'
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
  }
}

module spotifyMCP 'modules/mcp-api.bicep' = {
  name: 'spotify-mcp'
  params: {
    apimName: apim.outputs.name
    apiName: 'spotify-api'
    mcp: {
      name: 'spotify-mcp'
      description: 'Spotify MCP for music and artist data'
      displayName: 'Spotify MCP'
      path: 'spotify-mcp'
      policyXml: loadTextContent('policies/spotify-mcp-policy.xml')
      tools: [
        {
          name: 'searchForItem'
          description: 'Get Spotify catalog information about albums, artists, playlists, tracks, shows, episodes or audiobooks that match a keyword string. Audiobooks are only available within the US, UK, Canada, Ireland, New Zealand and Australia markets.'
          operation: 'search'
        } 
        {
          name: 'createPlaylist'
          description: 'Create a playlist for the current Spotify user. The playlist will be empty until you add tracks.'
          operation: 'create-playlist'
        }
        {
          name: 'getCurrentUsersPlaylists'
          description: 'Get a list of the playlists owned or followed by the current Spotify user.'
          operation: 'get-a-list-of-current-users-playlists'
        }
        {
          name: 'getPlaylistItems'
          description: 'Get full details of the items of a playlist owned by a Spotify user.'
          operation: 'get-playlists-items'
        }
        {
          name: 'getPlaylist'
          description: 'Get a playlist owned by a Spotify user.'
          operation: 'get-playlist'
        }
        {
          name: 'getAlbum'
          description: 'Get Spotify catalog information for a single album.'
          operation: 'get-an-album'
        }
        {
          name: 'getArtist'
          description: 'Get Spotify catalog information for a single artist identified by their unique Spotify ID.'
          operation: 'get-an-artist'
        }
        {
          name: 'getArtistsAlbums'
          description: 'Get Spotify catalog information about an artist\'s albums.'
          operation: 'get-an-artists-albums'
        }
        {
          name: 'getArtistsTopTracks'
          description: 'Get Spotify catalog information about an artist\'s top tracks by country.'
          operation: 'get-an-artists-top-tracks'
        }
        {
          name: 'getCurrentUsersProfile'
          description: 'Get detailed profile information about the current user (including the current user\'s username).'
          operation: 'get-current-users-profile'
        }
        {
          name: 'getNewReleases'
          description: 'Get a list of new album releases featured in Spotify (shown, for example, on a Spotify player\'s Browse tab).'
          operation: 'get-new-releases'
        }
        {
          name: 'getPlaylistCoverImage'
          description: 'Get the current image associated with a specific playlist.'
          operation: 'get-playlist-cover'
        }
        {
          name: 'getAlbumTracks'
          description: 'Get Spotify catalog information about an album\'s tracks. Optional parameters can be used to limit the number of tracks returned.'
          operation: 'get-an-albums-tracks'
        }
        { 
          name:'updatePlaylistItems'
          description:'Either reorder or replace items in a playlist depending on the request\'s parameters. To reorder items, include range_start, insert_before, range_length and snapshot_id in the request body. To replace items, include uris as either a query parameter or in the request body. Replacing items in a playlist will overwrite its existing items. This operation can be used for replacing or clearing items in a playlist.'
          operation: 'reorder-or-replace-playlists-items'
        }
        {
          name: 'addItemsToPlaylist'
          description: 'Add one or more items to a user\'s playlist. Provide a playlist_id and a list of Spotify URIs (tracks or episodes) to add. An optional position parameter (zero-based index) controls where items are inserted; if omitted they are appended.'
          operation: 'add-items-to-playlist'
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
output AZURE_AI_MODEL_DEPLOYMENT_NAME string = 'gpt-4.1'
output AZURE_MANAGED_IDENTITY_CLIENT_ID string = managedIdentity.outputs.clientId
output AZURE_MANAGED_IDENTITY_NAME string = managedIdentity.outputs.name
output AZURE_APIM_NAME string = apim.outputs.name
output AZURE_APIM_GATEWAY_URL string = 'https://${apim.outputs.name}.azure-api.net'
output AZURE_SETLISTFM_API_NAME string = 'setlistfm-api'
output AZURE_SETLISTFM_API_PATH string = 'https://${apim.outputs.name}.azure-api.net/setlistfm'
output AZURE_SETLISTFM_SUBSCRIPTION_NAME string = 'setlistfm-api'
#disable-next-line outputs-should-not-contain-secrets
output AZURE_SETLISTFM_SUBSCRIPTION_KEY string = setlistFmMCP.outputs.refApiSubscriptionPrimaryKey
output AZURE_TENANT_ID string = subscription().tenantId
output AZURE_SETLISTFM_MCP_URL string = setlistFmMCP.outputs.mcpUrl
output AZURE_SPOTIFY_MCP_URL string = spotifyMCP.outputs.mcpUrl
#disable-next-line outputs-should-not-contain-secrets
output AZURE_SPOTIFY_SUBSCRIPTION_KEY string = spotifyMCP.outputs.refApiSubscriptionPrimaryKey
output SPOTIFY_CLIENT_ID string = spotifyClientId
#disable-next-line outputs-should-not-contain-secrets
output SPOTIFY_CLIENT_SECRET string = spotifyClientSecret
