// Identity for GitHub Actions deployments via workload identity federation (no secrets).
// It can push images and release revisions of the named apps, but cannot create resources or grant roles.

param name string
param location string
param tags object

@description('OIDC subject prefix GitHub reports for the repository (actions/oidc/customization/sub), e.g. repo:owner@123/name@456 when immutable subjects are enabled.')
param githubSubjectPrefix string

@description('GitHub environment whose jobs may use this identity.')
param githubEnvironment string

param registryName string

@description('Container apps this identity may release new revisions to.')
param containerAppNames string[]

@description('Runtime identity attached to those apps; updating an app re-asserts its identity assignment.')
param appIdentityName string

@description('Container Apps environment hosting those apps; updating an app re-asserts that it joins it.')
param managedEnvironmentName string

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
    subject: '${githubSubjectPrefix}:environment:${githubEnvironment}'
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
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '8311e382-0749-4cb8-b61a-304f252e45ec'
    )
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource containerApps 'Microsoft.App/containerApps@2025-07-01' existing = [
  for appName in containerAppNames: {
    name: appName
  }
]

// Scoped to each app, not the resource group. The environment gets the same role below, which there
// amounts to read and join (its write actions have nothing to act on at that scope).
resource containerAppsContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for (appName, i) in containerAppNames: {
    name: guid(containerApps[i].id, identity.id, '358470bc-b998-42bd-ab17-a7e34c199c0f')
    scope: containerApps[i]
    properties: {
      // Container Apps Contributor
      roleDefinitionId: subscriptionResourceId(
        'Microsoft.Authorization/roleDefinitions',
        '358470bc-b998-42bd-ab17-a7e34c199c0f'
      )
      principalId: identity.properties.principalId
      principalType: 'ServicePrincipal'
    }
  }
]

resource managedEnvironment 'Microsoft.App/managedEnvironments@2025-07-01' existing = {
  name: managedEnvironmentName
}

resource environmentJoin 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(managedEnvironment.id, identity.id, '358470bc-b998-42bd-ab17-a7e34c199c0f')
  scope: managedEnvironment
  properties: {
    // Container Apps Contributor on the environment amounts to read and
    // managedEnvironments/join/action there (its write actions do not apply at that scope);
    // ARM checks join on every revision update.
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '358470bc-b998-42bd-ab17-a7e34c199c0f'
    )
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource appIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' existing = {
  name: appIdentityName
}

resource managedIdentityOperator 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(appIdentity.id, identity.id, 'f1a07417-d97a-45cb-824c-7a7467783830')
  scope: appIdentity
  properties: {
    // Managed Identity Operator, on the apps' runtime identity only: ARM checks
    // userAssignedIdentities/assign/action whenever a revision update carries the identity.
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'f1a07417-d97a-45cb-824c-7a7467783830'
    )
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource reader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, identity.id, 'acdd72a7-3385-48ef-bd42-f606fba81ae7')
  properties: {
    // Reader: lets azd find the apps by tag in the resource group.
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'acdd72a7-3385-48ef-bd42-f606fba81ae7'
    )
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

output clientId string = identity.properties.clientId
