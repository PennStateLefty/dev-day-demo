param name string
param location string
param tags object
param operatorPrincipalId string
param sqlAdministratorName string
param sqlAdministratorType string
@allowed([
  'enforced-perimeter'
  'public-demo'
])
param networkMode string

resource sql 'Microsoft.Sql/servers@2023-08-01' = {
  name: 'sql-claims-${name}'
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    version: '12.0'
    minimalTlsVersion: '1.2'
    publicNetworkAccess: networkMode == 'public-demo' ? 'Enabled' : 'SecuredByPerimeter'
    administrators: {
      administratorType: 'ActiveDirectory'
      azureADOnlyAuthentication: true
      login: sqlAdministratorName
      principalType: sqlAdministratorType
      sid: operatorPrincipalId
      tenantId: tenant().tenantId
    }
  }
}

resource demoFirewall 'Microsoft.Sql/servers/firewallRules@2023-08-01' = if (networkMode == 'public-demo') {
  parent: sql
  name: 'public-demo-entra-only'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '255.255.255.255'
  }
}

resource database 'Microsoft.Sql/servers/databases@2023-08-01' = {
  parent: sql
  name: 'claims'
  location: location
  tags: tags
  sku: {
    name: 'Basic'
    tier: 'Basic'
    capacity: 5
  }
  properties: {
    maxSizeBytes: 2147483648
    requestedBackupStorageRedundancy: 'Local'
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2025-01-01' = {
  name: 'stclaims${name}'
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: networkMode == 'public-demo' ? 'Enabled' : 'SecuredByPerimeter'
    networkAcls: {
      defaultAction: networkMode == 'public-demo' ? 'Allow' : 'Deny'
      bypass: 'None'
      ipRules: []
      virtualNetworkRules: []
    }
  }
}

resource blobs 'Microsoft.Storage/storageAccounts/blobServices@2025-01-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 7
    }
  }
}

resource containers 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-01-01' = [for container in [
  'policies'
  'evidence'
]: {
  parent: blobs
  name: container
  properties: {
    publicAccess: 'None'
  }
}]

output sqlResourceId string = sql.id
output sqlServer string = sql.properties.fullyQualifiedDomainName
output databaseName string = database.name
output storageResourceId string = storage.id
output storageName string = storage.name
