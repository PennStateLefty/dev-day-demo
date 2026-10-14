targetScope = 'resourceGroup'

param location string
param environmentResourceId string
param imageName string
param registryName string
param storageName string
param searchName string
param sqlServerName string
param sqlDatabase string
param runtimePrincipalId string
param runtimeClientId string
param repairLegacyPrincipalSid bool = false

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-claims-bootstrap'
  location: location
  tags: {
    application: 'synthetic-claims-demo'
    purpose: 'temporary-approved-bootstrap'
  }
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}
resource storage 'Microsoft.Storage/storageAccounts@2025-01-01' existing = {
  name: storageName
}
resource search 'Microsoft.Search/searchServices@2025-05-01' existing = {
  name: searchName
}
resource sql 'Microsoft.Sql/servers@2023-08-01' existing = {
  name: sqlServerName
}

resource pull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identity.id, 'bootstrap-pull')
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource blobs 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, identity.id, 'bootstrap-blobs')
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource searchRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for role in [
  '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
  '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
]: {
  name: guid(search.id, identity.id, role)
  scope: search
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', role)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}]

// Explicitly temporary: restore the selected human administrator before deleting this identity.
resource administrator 'Microsoft.Sql/servers/administrators@2023-08-01' = {
  parent: sql
  name: 'ActiveDirectory'
  properties: {
    administratorType: 'ActiveDirectory'
    login: identity.name
    sid: identity.properties.principalId
    tenantId: tenant().tenantId
  }
}

var settings = {
  AZURE_BOOTSTRAP_CLIENT_ID: identity.properties.clientId
  AZURE_RUNTIME_PRINCIPAL_ID: runtimePrincipalId
  AZURE_RUNTIME_CLIENT_ID: runtimeClientId
  AZURE_SQL_SERVER: sql.properties.fullyQualifiedDomainName
  AZURE_SQL_DATABASE: sqlDatabase
  AZURE_STORAGE_ACCOUNT_NAME: storageName
  AZURE_SEARCH_ENDPOINT: 'https://${searchName}.search.windows.net'
  AZURE_SEARCH_INDEX: 'synthetic-policies'
  AZURE_TENANT_ID: tenant().tenantId
}

resource job 'Microsoft.App/jobs@2025-01-01' = {
  name: 'job-claims-bootstrap'
  location: location
  tags: {
    application: 'synthetic-claims-demo'
    purpose: 'temporary-approved-bootstrap'
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    environmentId: environmentResourceId
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 600
      replicaRetryLimit: 0
      manualTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: [
        {
          server: registry.properties.loginServer
          identity: identity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'bootstrap'
          image: imageName
          command: ['/bin/sh']
          args: [
            '-c'
            '/workspace/.venv/bin/python scripts/initialize_sql.py --managed-identity ${repairLegacyPrincipalSid ? '--repair-legacy-principal-sid' : ''} && /workspace/.venv/bin/python scripts/initialize_knowledge.py --managed-identity'
          ]
          env: [for key in [
            'AZURE_BOOTSTRAP_CLIENT_ID'
            'AZURE_RUNTIME_PRINCIPAL_ID'
            'AZURE_RUNTIME_CLIENT_ID'
            'AZURE_SQL_SERVER'
            'AZURE_SQL_DATABASE'
            'AZURE_STORAGE_ACCOUNT_NAME'
            'AZURE_SEARCH_ENDPOINT'
            'AZURE_SEARCH_INDEX'
            'AZURE_TENANT_ID'
          ]: {
            name: key
            value: settings[key]
          }]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
    }
  }
  dependsOn: [
    pull
    blobs
    searchRoles
    administrator
  ]
}

output jobName string = job.name
output identityId string = identity.id
var searchRoleIds = [for i in range(0, 2): searchRoles[i].id]
output roleAssignmentIds array = concat([pull.id, blobs.id], searchRoleIds)
