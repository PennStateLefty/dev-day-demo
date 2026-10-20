targetScope = 'resourceGroup'

param gatewayName string
@description('Existing DAB HTTPS origin, without /mcp.')
param backendUrl string
@description('Existing Entra API application ID requested by APIM for backend authentication.')
param apiAudience string

resource gateway 'Microsoft.ApiManagement/service@2024-05-01' existing = {
  name: gatewayName
}

resource backend 'Microsoft.ApiManagement/service/backends@2024-05-01' = {
  parent: gateway
  name: 'claims-risk-data'
  properties: {
    protocol: 'http'
    url: backendUrl
    tls: { validateCertificateChain: true, validateCertificateName: true }
  }
}

resource mcp 'Microsoft.ApiManagement/service/apis@2025-09-01-preview' = {
  parent: gateway
  name: 'claims-risk-tools'
  properties: any({
    displayName: 'Synthetic claim history facts'
    description: 'Read-only DAB stored-procedure tools for human supervisor review.'
    type: 'mcp'
    path: 'claims-risk-tools'
    protocols: ['https']
    subscriptionRequired: true
    subscriptionKeyParameterNames: {
      header: 'Ocp-Apim-Subscription-Key'
      query: 'subscription-key'
    }
    backendId: backend.name
    mcpProperties: {
      transportType: 'streamable'
      endpoints: { mcp: { uriTemplate: '/mcp' } }
    }
  })
}

resource policy 'Microsoft.ApiManagement/service/apis/policies@2024-05-01' = {
  parent: mcp
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: replace(loadTextContent('./policies/claims-risk-subscription.xml'), '__API_AUDIENCE__', apiAudience)
  }
}

resource studioProduct 'Microsoft.ApiManagement/service/products@2024-05-01' = {
  parent: gateway
  name: 'copilot-studio-risk-tools'
  properties: {
    displayName: 'Copilot Studio Risk Tools'
    description: 'Synthetic read-only claim history for the supervisor demo.'
    subscriptionRequired: true
    approvalRequired: true
    state: 'published'
  }
}

resource studioProductApi 'Microsoft.ApiManagement/service/products/apis@2024-05-01' = {
  parent: studioProduct
  name: mcp.name
}

resource studioSubscription 'Microsoft.ApiManagement/service/subscriptions@2024-05-01' = {
  parent: gateway
  name: 'copilot-studio-risk-tools'
  properties: {
    displayName: 'Copilot Studio Risk Tools Demo'
    scope: studioProduct.id
    state: 'active'
    allowTracing: false
  }
  dependsOn: [studioProductApi]
}

output riskMcpUrl string = '${gateway.properties.gatewayUrl}/claims-risk-tools/mcp'
output studioSubscriptionId string = studioSubscription.id
