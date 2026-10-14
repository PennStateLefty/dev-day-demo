param name string
param location string
param tags object

module workspace 'br/public:avm/res/operational-insights/workspace:0.16.0' = {
  name: 'workspace'
  params: {
    name: 'log-${name}'
    location: location
    tags: tags
    enableTelemetry: false
    dataRetention: 30
    dailyQuotaGb: '1'
  }
}

module insights 'br/public:avm/res/insights/component:0.8.0' = {
  name: 'insights'
  params: {
    name: 'appi-${name}'
    location: location
    tags: tags
    enableTelemetry: false
    workspaceResourceId: workspace.outputs.resourceId
  }
}

module registry 'br/public:avm/res/container-registry/registry:0.13.0' = {
  name: 'registry'
  params: {
    name: 'acrclaims${name}'
    location: location
    tags: tags
    enableTelemetry: false
    acrSku: 'Basic'
    acrAdminUserEnabled: false
  }
}

resource runtime 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: 'id-claims-${name}'
  location: location
  tags: tags
}

resource environment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: 'cae-${name}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: workspace.outputs.logAnalyticsWorkspaceId
        sharedKey: workspace.outputs.primarySharedKey
      }
    }
  }
}

output environmentName string = environment.name
output environmentResourceId string = environment.id
output registryName string = registry.outputs.name
output registryEndpoint string = registry.outputs.loginServer
output workspaceResourceId string = workspace.outputs.resourceId
output insightsName string = insights.outputs.name
output runtimeIdentityId string = runtime.id
output runtimeClientId string = runtime.properties.clientId
output runtimePrincipalId string = runtime.properties.principalId
