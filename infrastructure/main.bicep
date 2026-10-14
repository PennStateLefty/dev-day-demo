targetScope = 'subscription'

@minLength(1)
@maxLength(32)
param environmentName string

param location string = 'centralus'

@description('public-demo permits authenticated public data-plane access for portal demonstrations.')
@allowed([
  'enforced-perimeter'
  'public-demo'
])
param networkMode string = 'enforced-perimeter'

@description('Operator public IPv4 /32; required only in enforced-perimeter mode.')
param operatorIpv4Cidr string = ''

@description('Tenant-local Entra object ID for SQL administration and deployment data-plane setup.')
@minLength(36)
@maxLength(36)
param operatorPrincipalId string

@description('Entra SQL administrator display name; no SQL password is created.')
@minLength(1)
param sqlAdministratorName string

@allowed([
  'User'
  'Group'
  'Application'
])
param sqlAdministratorType string = 'User'

@minLength(1)
param publisherEmail string

@minLength(1)
param publisherName string

@description('Required operational deadline YYYY-MM-DD. The policy exception does not expire itself.')
@minLength(10)
@maxLength(10)
param securityExceptionExpiresOn string

@description('Owner responsible for removing the temporary exception or deleting this demo deployment.')
@minLength(1)
param securityExceptionOwner string

var token = uniqueString(subscription().id, environmentName, location)
var tags = {
  'azd-env-name': environmentName
  application: 'synthetic-claims-demo'
  environment: environmentName
}

resource demoGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-claims-${environmentName}-${take(token, 6)}'
  location: location
  tags: {
    'azd-env-name': environmentName
    application: 'synthetic-claims-demo'
    environment: environmentName
    SecurityControl: 'Ignore'
    'security-exception-expires-on': securityExceptionExpiresOn
    'security-exception-owner': securityExceptionOwner
  }
}

module platform './modules/platform.bicep' = {
  name: 'platform'
  scope: demoGroup
  params: {
    name: token
    location: location
    tags: tags
  }
}

module data './modules/data.bicep' = {
  name: 'data'
  scope: demoGroup
  params: {
    name: token
    location: location
    tags: tags
    operatorPrincipalId: operatorPrincipalId
    sqlAdministratorName: sqlAdministratorName
    sqlAdministratorType: sqlAdministratorType
    networkMode: networkMode
  }
}

module ai './modules/ai.bicep' = {
  name: 'ai'
  scope: demoGroup
  params: {
    name: token
    location: location
    tags: tags
    networkMode: networkMode
  }
}

module gateway './modules/gateway.bicep' = {
  name: 'gateway'
  scope: demoGroup
  params: {
    name: token
    location: location
    tags: tags
    publisherName: publisherName
    publisherEmail: publisherEmail
  }
}

module perimeter './modules/perimeter.bicep' = if (networkMode == 'enforced-perimeter') {
  name: 'perimeter'
  scope: demoGroup
  params: {
    name: token
    location: location
    tags: tags
    operatorIpv4Cidr: operatorIpv4Cidr
    networkMode: networkMode
    storageResourceId: data.outputs.storageResourceId
    protectedResourceIds: [
      data.outputs.sqlResourceId
      data.outputs.storageResourceId
      ai.outputs.foundryResourceId
      ai.outputs.searchResourceId
    ]
  }
}

module access './modules/access.bicep' = {
  name: 'access'
  scope: demoGroup
  params: {
    registryName: platform.outputs.registryName
    runtimePrincipalId: platform.outputs.runtimePrincipalId
    storageName: data.outputs.storageName
    searchName: ai.outputs.searchName
    foundryName: ai.outputs.foundryName
    projectName: ai.outputs.projectName
    projectPrincipalId: ai.outputs.projectPrincipalId
    searchPrincipalId: ai.outputs.searchPrincipalId
    gatewayPrincipalId: gateway.outputs.gatewayPrincipalId
    operatorPrincipalId: operatorPrincipalId
    operatorPrincipalType: sqlAdministratorType == 'Group' ? 'Group' : (sqlAdministratorType == 'Application' ? 'ServicePrincipal' : 'User')
  }
}

output AZURE_RESOURCE_GROUP string = demoGroup.name
output AZURE_CONTAINER_APPS_ENVIRONMENT_ID string = platform.outputs.environmentResourceId
output AZURE_CONTAINER_APPS_ENVIRONMENT_NAME string = platform.outputs.environmentName
output AZURE_CLAIMS_API_NAME string = 'ca-claims-${token}'
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = platform.outputs.registryEndpoint
output AZURE_CONTAINER_REGISTRY_NAME string = platform.outputs.registryName
output AZURE_RUNTIME_IDENTITY_ID string = platform.outputs.runtimeIdentityId
output AZURE_RUNTIME_CLIENT_ID string = platform.outputs.runtimeClientId
output AZURE_RUNTIME_PRINCIPAL_ID string = platform.outputs.runtimePrincipalId
output AZURE_LOG_ANALYTICS_WORKSPACE_ID string = platform.outputs.workspaceResourceId
output AZURE_APPLICATION_INSIGHTS_NAME string = platform.outputs.insightsName
output AZURE_SQL_SERVER string = data.outputs.sqlServer
output AZURE_SQL_DATABASE string = data.outputs.databaseName
output AZURE_STORAGE_ACCOUNT_NAME string = data.outputs.storageName
output AZURE_AI_ACCOUNT_NAME string = ai.outputs.foundryName
output AZURE_AI_PROJECT_NAME string = ai.outputs.projectName
output AZURE_AI_PROJECT_ENDPOINT string = ai.outputs.projectEndpoint
output AZURE_SEARCH_SERVICE_NAME string = ai.outputs.searchName
output AZURE_SEARCH_ENDPOINT string = ai.outputs.searchEndpoint
output AZURE_SEARCH_INDEX string = 'synthetic-policies'
output AZURE_APIM_NAME string = gateway.outputs.gatewayName
output AZURE_APIM_GATEWAY_URL string = gateway.outputs.gatewayUrl
output AZURE_API_CENTER_NAME string = gateway.outputs.apiCenterName
output AZURE_NETWORK_SECURITY_PERIMETER_NAME string = 'nsp-claims-${token}'
output AZURE_DEPLOYED_NETWORK_MODE string = networkMode
