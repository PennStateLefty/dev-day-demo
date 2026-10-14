param gatewayName string
param applicationUrl string
param tenantId string
param apiAudience string
param apiClientIds string

var clientClaims = join(map(split(apiClientIds, ','), client => '<value>${trim(client)}</value>'), '')
var authPolicy = replace(replace(replace(loadTextContent('../policies/claims-auth.xml'), '__TENANT__', tenantId), '__AUDIENCE__', apiAudience), '__CLIENTS__', clientClaims)

resource gateway 'Microsoft.ApiManagement/service@2024-05-01' existing = {
  name: gatewayName
}

resource rest 'Microsoft.ApiManagement/service/apis@2024-05-01' = {
  parent: gateway
  name: 'synthetic-claims-data'
  properties: {
    displayName: 'Synthetic claims data'
    description: 'Entra-protected bounded synthetic data tools; no coverage decisions or sends.'
    apiRevision: '1'
    type: 'http'
    path: 'claims'
    serviceUrl: applicationUrl
    protocols: ['https']
    subscriptionRequired: false
  }
}

resource operations 'Microsoft.ApiManagement/service/apis/operations@2024-05-01' = [for operation in [
  { name: 'get-claims', method: 'GET', path: '/api/*' }
  { name: 'post-claims', method: 'POST', path: '/api/*' }
  { name: 'dependency-readiness', method: 'GET', path: '/ready' }
]: {
  parent: rest
  name: operation.name
  properties: {
    displayName: operation.name
    method: operation.method
    urlTemplate: operation.path
  }
}]

resource restPolicy 'Microsoft.ApiManagement/service/apis/policies@2024-05-01' = {
  parent: rest
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: authPolicy
  }
}

resource mcpBackend 'Microsoft.ApiManagement/service/backends@2024-05-01' = {
  parent: gateway
  name: 'synthetic-claims-mcp'
  properties: {
    protocol: 'http'
    url: applicationUrl
    tls: {
      validateCertificateChain: true
      validateCertificateName: true
    }
  }
}

resource mcp 'Microsoft.ApiManagement/service/apis@2025-09-01-preview' = {
  parent: gateway
  name: 'synthetic-claims-tools'
  // The live API exposes backendId and dictionary endpoints, absent from its Bicep schema.
  properties: any({
    displayName: 'Synthetic claims MCP tools'
    description: 'Native streamable MCP proxy; the backend independently validates caller tokens.'
    type: 'mcp'
    path: 'claims-tools'
    protocols: ['https']
    subscriptionRequired: false
    backendId: mcpBackend.name
    mcpProperties: {
      transportType: 'streamable'
      endpoints: {
        mcp: {
          uriTemplate: '/mcp/'
        }
      }
    }
  })
}

resource mcpPolicy 'Microsoft.ApiManagement/service/apis/policies@2024-05-01' = {
  parent: mcp
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: authPolicy
  }
}

output restUrl string = '${gateway.properties.gatewayUrl}/claims'
output mcpUrl string = '${gateway.properties.gatewayUrl}/claims-tools/mcp/'
