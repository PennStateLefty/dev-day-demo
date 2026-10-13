@description('Deployment environment name used to create a deterministic resource name.')
param environmentName string = 'demo'

@description('Azure region for the Container Apps environment.')
param location string = resourceGroup().location

var resourceToken = take(uniqueString(resourceGroup().id, environmentName), 13)
var containerAppsEnvironmentName = 'cae-${resourceToken}'

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: containerAppsEnvironmentName
  location: location
  tags: {
    application: 'synthetic-claims-demo'
    environment: environmentName
  }
  properties: {
    appLogsConfiguration: {
      destination: 'azure-monitor'
    }
  }
}

output containerAppsEnvironmentId string = containerAppsEnvironment.id
output containerAppsEnvironmentName string = containerAppsEnvironment.name
