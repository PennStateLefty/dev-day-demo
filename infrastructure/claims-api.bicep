targetScope = 'resourceGroup'

param environmentName string
param location string
param appName string
param environmentResourceId string
param runtimeIdentityId string
param runtimeClientId string
param registryEndpoint string
@description('Real image published by azd. There is no fixture or hello-world deployment fallback.')
@minLength(1)
param imageName string
param tenantId string
@minLength(36)
@maxLength(36)
param apiAudience string
@minLength(1)
param apiClientIds string
@minLength(36)
@maxLength(36)
param foundryProjectClientId string
@minLength(36)
@maxLength(36)
param uiClientId string
param sqlServer string
param sqlDatabase string
param searchEndpoint string
param searchIndex string
param storageAccountName string
param gatewayName string
@description('Optional API-owned gpt-6-luna endpoint; empty disables live image inference.')
param visionEndpoint string = ''
param visionDeployment string = ''
param visionModelVersion string = ''
@description('Optional pinned Claim Assessor; configure endpoint and version together.')
param foundryProjectEndpoint string = ''
param claimAssessorVersion string = ''

var authorizedClientIds = '${apiClientIds},${foundryProjectClientId}'
var runtimeSettings = {
  CLAIMS_MODE: 'azure'
  AZURE_TENANT_ID: tenantId
  CLAIMS_API_AUDIENCE: apiAudience
  CLAIMS_API_CLIENT_IDS: authorizedClientIds
  CLAIMS_UI_CLIENT_ID: uiClientId
  AZURE_RUNTIME_CLIENT_ID: runtimeClientId
  AZURE_SQL_SERVER: sqlServer
  AZURE_SQL_DATABASE: sqlDatabase
  AZURE_SEARCH_ENDPOINT: searchEndpoint
  AZURE_SEARCH_INDEX: searchIndex
  AZURE_STORAGE_ACCOUNT_NAME: storageAccountName
  CLAIMS_VISION_ENDPOINT: visionEndpoint
  CLAIMS_VISION_DEPLOYMENT: visionDeployment
  CLAIMS_VISION_MODEL_VERSION: visionModelVersion
  FOUNDRY_PROJECT_ENDPOINT: foundryProjectEndpoint
  CLAIM_ASSESSOR_AGENT_VERSION: claimAssessorVersion
}

resource application 'Microsoft.App/containerApps@2025-01-01' = {
  name: appName
  location: location
  tags: {
    'azd-env-name': environmentName
    'azd-service-name': 'claims-api'
    application: 'synthetic-claims-demo'
    environment: environmentName
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${runtimeIdentityId}': {}
    }
  }
  properties: {
    environmentId: environmentResourceId
    configuration: {
      activeRevisionsMode: 'Single'
      maxInactiveRevisions: 1
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 8000
        transport: 'http'
      }
      registries: [
        {
          server: registryEndpoint
          identity: runtimeIdentityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'claims-api'
          image: imageName
          env: [for entry in items(runtimeSettings): {
            name: entry.key
            value: entry.value
          }]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          // Dependency readiness requires an authorized /ready call, not these public probes.
          probes: [for probeType in ['Startup', 'Liveness', 'Readiness']: {
            type: probeType
            httpGet: {
              path: '/health'
              port: 8000
              scheme: 'HTTP'
            }
            initialDelaySeconds: 5
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 12
          }]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
        rules: [
          {
            name: 'http'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
}

module routes './modules/gateway-routes.bicep' = {
  name: 'claims-gateway-routes'
  params: {
    gatewayName: gatewayName
    applicationUrl: 'https://${application.properties.configuration.ingress.fqdn}'
    tenantId: tenantId
    apiAudience: apiAudience
    apiClientIds: authorizedClientIds
  }
}

output SERVICE_CLAIMS_API_NAME string = application.name
output SERVICE_CLAIMS_API_URI string = 'https://${application.properties.configuration.ingress.fqdn}'
output CLAIMS_GATEWAY_REST_URL string = routes.outputs.restUrl
output CLAIMS_GATEWAY_MCP_URL string = routes.outputs.mcpUrl
