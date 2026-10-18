targetScope = 'resourceGroup'

param applicationInsightsName string
param workspaceName string
param gatewayName string
param foundryName string
param searchName string
param sqlServerName string
param sqlDatabaseName string
param storageName string
param registryName string
param applicationName string

resource insights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: applicationInsightsName
}
resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: workspaceName
}
resource gateway 'Microsoft.ApiManagement/service@2024-05-01' existing = {
  name: gatewayName
}
resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryName
}
resource search 'Microsoft.Search/searchServices@2025-05-01' existing = {
  name: searchName
}
resource sql 'Microsoft.Sql/servers@2023-08-01' existing = {
  name: sqlServerName
}
resource database 'Microsoft.Sql/servers/databases@2023-08-01' existing = {
  parent: sql
  name: sqlDatabaseName
}
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageName
}
resource blobs 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' existing = {
  parent: storage
  name: 'default'
}
resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}
resource application 'Microsoft.App/containerApps@2025-01-01' existing = {
  name: applicationName
}

resource logger 'Microsoft.ApiManagement/service/loggers@2024-05-01' = {
  parent: gateway
  name: 'claims-application-insights'
  properties: {
    loggerType: 'applicationInsights'
    description: 'Shared demo Application Insights; no HTTP content capture.'
    resourceId: insights.id
    credentials: {
      instrumentationKey: insights.properties.InstrumentationKey
    }
    isBuffered: true
  }
}

var messageDiagnostic = {
  headers: []
  body: { bytes: 0 }
  dataMasking: {
    queryParams: [{ value: '*', mode: 'Hide' }]
  }
}
resource apiDiagnostics 'Microsoft.ApiManagement/service/diagnostics@2024-05-01' = {
  parent: gateway
  name: 'applicationinsights'
  properties: {
    loggerId: logger.id
    alwaysLog: 'allErrors'
    httpCorrelationProtocol: 'W3C'
    logClientIp: false
    operationNameFormat: 'Name'
    verbosity: 'information'
    sampling: {
      samplingType: 'fixed'
      percentage: 100
    }
    frontend: { request: messageDiagnostic, response: messageDiagnostic }
    backend: { request: messageDiagnostic, response: messageDiagnostic }
  }
}

var allMetrics = [{ category: 'AllMetrics', enabled: true }]

resource gatewayLogs 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'claims-observability'
  scope: gateway
  properties: {
    workspaceId: workspace.id
    logAnalyticsDestinationType: 'Dedicated'
    logs: [{ category: 'GatewayLogs', enabled: true }]
    metrics: allMetrics
  }
}
resource foundryLogs 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'claims-observability'
  scope: foundry
  properties: {
    workspaceId: workspace.id
    logAnalyticsDestinationType: 'Dedicated'
    // RequestResponse and Trace can contain model inputs/outputs.
    logs: [
      { category: 'Audit', enabled: true }
      { category: 'AzureOpenAIRequestUsage', enabled: true }
    ]
    metrics: allMetrics
  }
}
resource searchLogs 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'claims-observability'
  scope: search
  properties: {
    workspaceId: workspace.id
    logs: [{ category: 'OperationLogs', enabled: true }]
    metrics: allMetrics
  }
}
resource sqlLogs 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'claims-observability'
  scope: database
  properties: {
    workspaceId: workspace.id
    logs: [
      { category: 'Errors', enabled: true }
      { category: 'Timeouts', enabled: true }
    ]
    metrics: [{ category: 'Basic', enabled: true }]
  }
}
resource blobLogs 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'claims-observability'
  scope: blobs
  properties: {
    workspaceId: workspace.id
    logAnalyticsDestinationType: 'Dedicated'
    logs: [
      { category: 'StorageRead', enabled: true }
      { category: 'StorageWrite', enabled: true }
      { category: 'StorageDelete', enabled: true }
    ]
    metrics: [{ category: 'Transaction', enabled: true }]
  }
}
resource registryLogs 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'claims-observability'
  scope: registry
  properties: {
    workspaceId: workspace.id
    logAnalyticsDestinationType: 'Dedicated'
    logs: [
      { category: 'ContainerRegistryLoginEvents', enabled: true }
      { category: 'ContainerRegistryRepositoryEvents', enabled: true }
    ]
    metrics: allMetrics
  }
}
resource applicationMetrics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'claims-observability'
  scope: application
  properties: {
    workspaceId: workspace.id
    metrics: allMetrics
  }
}

output applicationInsightsResourceId string = insights.id
output logAnalyticsWorkspaceResourceId string = workspace.id
