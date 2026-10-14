param name string
param location string
param tags object
param publisherName string
param publisherEmail string

resource gateway 'Microsoft.ApiManagement/service@2024-05-01' = {
  name: 'apim-claims-${name}'
  location: location
  tags: tags
  sku: {
    name: 'Developer'
    capacity: 1
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    publisherName: publisherName
    publisherEmail: publisherEmail
    publicNetworkAccess: 'Enabled'
    virtualNetworkType: 'None'
    customProperties: {
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Tls10': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Tls11': 'false'
    }
  }
}

module apiCenter 'br/public:avm/res/api-center/service:0.1.0' = {
  name: 'api-center'
  params: {
    name: 'apic-claims-${name}'
    location: location
    tags: tags
    enableTelemetry: false
    sku: 'Free'
  }
}

output gatewayName string = gateway.name
output gatewayPrincipalId string = gateway.identity.principalId
output gatewayUrl string = gateway.properties.gatewayUrl
output apiCenterName string = apiCenter.outputs.name
