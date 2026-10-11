// Identity for GitHub Actions deployments via workload identity federation (no secrets).
// It can push images and update container apps, but cannot create resources or grant roles.

param name string
param location string
param tags object

@description('GitHub repository in owner/name form.')
param githubRepository string

@description('GitHub environment whose jobs may use this identity.')
param githubEnvironment string

param registryName string

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: name
  location: location
  tags: tags
}

resource credential 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2024-11-30' = {
  parent: identity
  name: 'github-${githubEnvironment}'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: 'repo:${githubRepository}:environment:${githubEnvironment}'
    audiences: ['api://AzureADTokenExchange']
  }
}

resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' existing = {
  name: registryName
}

resource acrPush 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identity.id, '8311e382-0749-4cb8-b61a-304f252e45ec')
  scope: registry
  properties: {
    // AcrPush
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8311e382-0749-4cb8-b61a-304f252e45ec')
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource containerAppsContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, identity.id, '358470bc-b998-42bd-ab17-a7e34c199c0f')
  properties: {
    // Container Apps Contributor
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '358470bc-b998-42bd-ab17-a7e34c199c0f')
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource reader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, identity.id, 'acdd72a7-3385-48ef-bd42-f606fba81ae7')
  properties: {
    // Reader: lets azd find the apps by tag in the resource group.
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'acdd72a7-3385-48ef-bd42-f606fba81ae7')
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

output clientId string = identity.properties.clientId
