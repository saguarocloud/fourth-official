// Azure Container Registry. Pull and push happen only with Entra ID identities.

@description('Registry name: 5-50 alphanumeric characters, globally unique.')
@minLength(5)
@maxLength(50)
param name string

param location string
param tags object

resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' = {
  name: name
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

output name string = registry.name
output loginServer string = registry.properties.loginServer
