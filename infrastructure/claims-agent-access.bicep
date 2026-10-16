targetScope = 'resourceGroup'

param foundryAccountName string
param projectName string = 'claims'
param runtimePrincipalId string

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' existing = {
  parent: foundry
  name: projectName
}

resource consumer 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(project.id, runtimePrincipalId, 'foundry-agent-consumer')
  scope: project
  properties: {
    principalId: runtimePrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'eed3b665-ab3a-47b6-8f48-c9382fb1dad6')
  }
}
