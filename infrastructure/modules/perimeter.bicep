param name string
param location string
param tags object
param operatorIpv4Cidr string
param storageResourceId string
param protectedResourceIds array
@allowed([
  'enforced-perimeter'
  'public-demo'
])
param networkMode string

resource perimeter 'Microsoft.Network/networkSecurityPerimeters@2024-07-01' = {
  name: 'nsp-claims-${name}'
  location: location
  tags: tags
}

resource profile 'Microsoft.Network/networkSecurityPerimeters/profiles@2024-07-01' = {
  parent: perimeter
  name: 'demo'
  properties: {}
}

resource operatorRule 'Microsoft.Network/networkSecurityPerimeters/profiles/accessRules@2024-07-01' = if (networkMode == 'enforced-perimeter') {
  parent: profile
  name: 'operator-ip'
  properties: {
    direction: 'Inbound'
    addressPrefixes: [
      operatorIpv4Cidr
    ]
  }
}

// Container Apps and APIM cannot join an NSP. RBAC still restricts each caller.
resource runtimeRule 'Microsoft.Network/networkSecurityPerimeters/profiles/accessRules@2024-07-01' = {
  parent: profile
  name: 'managed-identities'
  properties: {
    direction: 'Inbound'
    subscriptions: [
      {
        id: subscription().id
      }
    ]
  }
}

resource storageAssociation 'Microsoft.Network/networkSecurityPerimeters/resourceAssociations@2024-07-01' = if (networkMode == 'enforced-perimeter') {
  parent: perimeter
  name: 'resource-${indexOf(protectedResourceIds, storageResourceId)}'
  properties: {
    accessMode: 'Enforced'
    privateLinkResource: {
      id: storageResourceId
    }
    profile: {
      id: profile.id
    }
  }
}

resource associations 'Microsoft.Network/networkSecurityPerimeters/resourceAssociations@2024-07-01' = [for (resourceId, index) in protectedResourceIds: if (networkMode == 'enforced-perimeter' && resourceId != storageResourceId) {
  parent: perimeter
  name: 'resource-${index}${contains(resourceId, '/Microsoft.Search/') ? '-basic' : ''}'
  properties: {
    accessMode: 'Enforced'
    privateLinkResource: {
      id: resourceId
    }
    profile: {
      id: profile.id
    }
  }
}]

resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'perimeter-access'
  scope: perimeter
  properties: {
    storageAccountId: storageResourceId
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
  }
  dependsOn: [
    storageAssociation
  ]
}

output perimeterName string = perimeter.name
