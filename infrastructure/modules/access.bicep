param registryName string
param runtimePrincipalId string
param storageName string
param searchName string
param foundryName string
param projectName string
param projectPrincipalId string
param searchPrincipalId string
param gatewayPrincipalId string
param operatorPrincipalId string
param operatorPrincipalType string

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}
resource storage 'Microsoft.Storage/storageAccounts@2025-01-01' existing = {
  name: storageName
}
resource search 'Microsoft.Search/searchServices@2025-05-01' existing = {
  name: searchName
}
resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryName
}
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' existing = {
  parent: foundry
  name: projectName
}

var blobReader = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')
var blobContributor = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
var searchReader = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '1407120a-92aa-4202-b7e9-c0e197c71c8f')
var searchContributor = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7ca78c08-252a-4471-8644-bb5ff32d4ba0')
var indexContributor = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
var modelUser = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')

resource pull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, runtimePrincipalId, 'acrpull')
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: runtimePrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource blobReaders 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for principalId in [
  runtimePrincipalId
  projectPrincipalId
  searchPrincipalId
]: {
  name: guid(storage.id, principalId, blobReader)
  scope: storage
  properties: {
    roleDefinitionId: blobReader
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}]

resource indexReaders 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for principalId in [
  runtimePrincipalId
  projectPrincipalId
]: {
  name: guid(search.id, principalId, searchReader)
  scope: search
  properties: {
    roleDefinitionId: searchReader
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}]

resource modelUsers 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for principalId in [
  runtimePrincipalId
  projectPrincipalId
  searchPrincipalId
  gatewayPrincipalId
]: {
  name: guid(foundry.id, principalId, modelUser)
  scope: foundry
  properties: {
    roleDefinitionId: modelUser
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}]

resource operatorBlob 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, operatorPrincipalId, blobContributor)
  scope: storage
  properties: {
    roleDefinitionId: blobContributor
    principalId: operatorPrincipalId
    principalType: operatorPrincipalType
  }
}

resource operatorSearch 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for roleId in [
  searchContributor
  indexContributor
]: {
  name: guid(search.id, operatorPrincipalId, roleId)
  scope: search
  properties: {
    roleDefinitionId: roleId
    principalId: operatorPrincipalId
    principalType: operatorPrincipalType
  }
}]

resource operatorProject 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(project.id, operatorPrincipalId, 'foundry-user')
  scope: project
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
    principalId: operatorPrincipalId
    principalType: operatorPrincipalType
  }
}
