targetScope = 'resourceGroup'

@description('Name of the existing API Management instance.')
param apimName string

@description('setlist.fm API key to be stored as a named value.')
@secure()
param setlistfmApiKey string

@description('Path prefix for the API.')
param apiPath string = 'setlistfm'

// Reference to the existing APIM instance
resource apim 'Microsoft.ApiManagement/service@2024-05-01' existing = {
  name: apimName
}

// Named Value to store the setlist.fm API key securely
resource setlistfmApiKeyNamedValue 'Microsoft.ApiManagement/service/namedValues@2024-05-01' = {
  name: 'setlistfm-api-key'
  parent: apim
  properties: {
    displayName: 'setlistfm-api-key'
    secret: true
    value: setlistfmApiKey
    tags: [
      'setlistfm'
      'api-key'
    ]
  }
}

// API created from OpenAPI spec
resource setlistfmApi 'Microsoft.ApiManagement/service/apis@2024-05-01' = {
  name: 'setlistfm-api'
  parent: apim
  properties: {
    displayName: 'setlist.fm API'
    description: 'Access to setlist.fm API for concert setlist data'
    path: apiPath
    protocols: [
      'https'
    ]
    subscriptionRequired: true
    type: 'http'
    format: 'openapi+json'
    value: loadTextContent('../../openapi/openapi-setlistfm.json')
    serviceUrl: 'https://api.setlist.fm/rest'
  }
}

// Policy to inject the x-api-key header for backend requests
resource setlistfmApiPolicy 'Microsoft.ApiManagement/service/apis/policies@2024-05-01' = {
  name: 'policy'
  parent: setlistfmApi
  properties: {
    value: '''
<policies>
  <inbound>
    <base />
    <set-header name="x-api-key" exists-action="override">
      <value>{{setlistfm-api-key}}</value>
    </set-header>
  </inbound>
  <backend>
    <base />
  </backend>
  <outbound>
    <base />
  </outbound>
  <on-error>
    <base />
  </on-error>
</policies>
'''
    format: 'xml'
  }
}

// Dedicated subscription for the setlist.fm API
resource setlistfmSubscription 'Microsoft.ApiManagement/service/subscriptions@2024-05-01' = {
  name: 'setlistfm-api-subscription'
  parent: apim
  properties: {
    displayName: 'setlistfm-api'
    scope: '/apis/${setlistfmApi.id}'
    state: 'active'
    allowTracing: true
  }
}

@description('The resource ID of the setlist.fm API.')
output apiId string = setlistfmApi.id

@description('The name of the setlist.fm API.')
output apiName string = setlistfmApi.name

@description('The subscription ID for the setlist.fm API.')
output subscriptionId string = setlistfmSubscription.id

@description('The display name of the subscription.')
output subscriptionDisplayName string = setlistfmSubscription.properties.displayName
