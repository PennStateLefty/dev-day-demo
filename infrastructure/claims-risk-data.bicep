targetScope = 'resourceGroup'

param location string = resourceGroup().location
param appName string
param environmentName string
param registryName string
@description('Reviewed DAB image built from src/apps/claims-risk-data; no placeholder image.')
@minLength(1)
param imageName string
param sqlServer string
param sqlDatabase string
param gatewayName string
@description('Existing Entra API application ID; DAB validates this audience and APIM requests its token.')
@minLength(1)
param apiAudience string
@description('Must match the issuer of backend access tokens, including their v1/v2 token version.')
@minLength(1)
param tokenIssuer string
@description('First deploy false to create the SQL identity; grant SQL access before setting true.')
param provisionApplication bool = false

resource environment 'Microsoft.App/managedEnvironments@2025-01-01' existing = {
  name: environmentName
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}

resource gateway 'Microsoft.ApiManagement/service@2024-05-01' existing = {
  name: gatewayName
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${appName}-identity'
  location: location
}

var acrPullRole = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7f951dda-4ed3-4680-a7ca-43fe172d538d'
)

resource pullAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identity.id, acrPullRole)
  scope: registry
  properties: {
    roleDefinitionId: acrPullRole
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource application 'Microsoft.App/containerApps@2025-01-01' = if (provisionApplication) {
  name: appName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  properties: {
    environmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      maxInactiveRevisions: 1
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 5000
        transport: 'http'
      }
      registries: [{ server: registry.properties.loginServer, identity: identity.id }]
    }
    template: {
      containers: [{
        name: 'claims-risk-data'
        image: imageName
        env: [
          {
            name: 'DATABASE_CONNECTION_STRING'
            value: 'Server=tcp:${sqlServer},1433;Database=${sqlDatabase};Authentication=Active Directory Managed Identity;User Id=${identity.properties.clientId};Encrypt=True;TrustServerCertificate=False;'
          }
          { name: 'DAB_AUDIENCE', value: apiAudience }
          { name: 'DAB_ISSUER', value: tokenIssuer }
          { name: 'DAB_HOST', value: '${appName}.${environment.properties.defaultDomain}' }
          { name: 'APIM_HOST', value: replace(gateway.properties.gatewayUrl, 'https://', '') }
        ]
        resources: { cpu: json('0.5'), memory: '1Gi' }
        probes: [for probeType in ['Startup', 'Liveness', 'Readiness']: {
          type: probeType
          // DAB's root is public process health; /health is an authorized detailed report.
          httpGet: { path: '/', port: 5000, scheme: 'HTTP' }
          initialDelaySeconds: 5
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 30
        }]
      }]
      scale: { minReplicas: 0, maxReplicas: 1 }
    }
  }
  dependsOn: [pullAccess]
}

module studioGateway './claims-risk-apim.bicep' = if (provisionApplication) {
  name: 'claims-risk-apim'
  params: {
    gatewayName: gatewayName
    backendUrl: 'https://${application!.properties.configuration.ingress.fqdn}'
    apiAudience: apiAudience
  }
}

output riskClientId string = identity.properties.clientId
output riskIdentityId string = identity.id
output riskApplicationUrl string = provisionApplication ? 'https://${application!.properties.configuration.ingress.fqdn}' : ''
output riskMcpUrl string = provisionApplication ? '${gateway.properties.gatewayUrl}/claims-risk-tools/mcp' : ''
output studioSubscriptionId string = provisionApplication ? studioGateway!.outputs.studioSubscriptionId : ''
