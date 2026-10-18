targetScope = 'resourceGroup'

@minLength(2)
param gatewayName string
@minLength(2)
param foundryName string
@minLength(2)
param projectName string
@minLength(2)
param projectEndpoint string
@minLength(2)
param toolboxName string = 'policy-checker-toolbox'
@minLength(1)
param toolboxVersion string
@minLength(2)
param tenantId string
@minLength(2)
param apiAudience string
@minLength(2)
param apiClientIds string
@minLength(2)
param gatewayPrincipalId string
@minLength(2)
param policyCheckerAgentPrincipalId string
@minLength(2)
param policyCheckerAgentClientId string
@minLength(2)
param foundryProjectClientId string

var foundryUserRole = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '53ca6127-db72-4b80-b1b0-d745d6d5456d'
)
var clientClaims = join(map(split(apiClientIds, ','), client => '<value>${trim(client)}</value>'), '')
var claimsMcpClientIds = union(
  split(apiClientIds, ','),
  [policyCheckerAgentClientId],
  [foundryProjectClientId]
)
var claimsMcpClientClaims = join(
  map(claimsMcpClientIds, client => '<value>${trim(client)}</value>'),
  ''
)
var authPolicy = replace(
  replace(
    replace(
      loadTextContent('./policies/policy-checker-toolbox-auth.xml'),
      '__TENANT__',
      tenantId
    ),
    '__AUDIENCE__',
    apiAudience
  ),
  '__CLIENTS__',
  clientClaims
)
var claimsMcpAuthPolicy = replace(
  replace(
    replace(
      loadTextContent('./policies/claims-auth.xml'),
      '__TENANT__',
      tenantId
    ),
    '__AUDIENCE__',
    apiAudience
  ),
  '__CLIENTS__',
  claimsMcpClientClaims
)

resource gateway 'Microsoft.ApiManagement/service@2024-05-01' existing = {
  name: gatewayName
}

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryName
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' existing = {
  parent: foundry
  name: projectName
}

resource projectAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for principalId in [
  gatewayPrincipalId
  policyCheckerAgentPrincipalId
]: {
  name: guid(project.id, principalId, foundryUserRole)
  scope: project
  properties: {
    roleDefinitionId: foundryUserRole
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}]

resource claimsMcp 'Microsoft.ApiManagement/service/apis@2024-05-01' existing = {
  parent: gateway
  name: 'synthetic-claims-tools'
}

resource claimsMcpPolicy 'Microsoft.ApiManagement/service/apis/policies@2024-05-01' = {
  parent: claimsMcp
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: claimsMcpAuthPolicy
  }
}

resource toolboxBackend 'Microsoft.ApiManagement/service/backends@2024-05-01' = {
  parent: gateway
  name: 'policy-checker-toolbox'
  properties: {
    protocol: 'http'
    url: '${projectEndpoint}/toolboxes/${toolboxName}/versions/${toolboxVersion}'
    tls: {
      validateCertificateChain: true
      validateCertificateName: true
    }
  }
}

resource toolboxMcp 'Microsoft.ApiManagement/service/apis@2025-09-01-preview' = {
  parent: gateway
  name: 'policy-checker-toolbox'
  properties: any({
    displayName: 'Policy Checker Foundry Toolbox'
    description: 'Entra-protected MCP route to the version-pinned read-only Policy Checker Toolbox.'
    apiRevision: '1'
    type: 'mcp'
    path: 'policy-checker-tools'
    protocols: ['https']
    backendId: toolboxBackend.name
    subscriptionRequired: false
    mcpProperties: {
      transportType: 'streamable'
      endpoints: {
        mcp: {
          uriTemplate: '/mcp'
        }
      }
    }
  })
}

resource toolboxMcpPolicy 'Microsoft.ApiManagement/service/apis/policies@2024-05-01' = {
  parent: toolboxMcp
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: authPolicy
  }
}

output policyCheckerToolboxMcpUrl string = '${gateway.properties.gatewayUrl}/policy-checker-tools/mcp'
