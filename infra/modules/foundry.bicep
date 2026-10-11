// Microsoft Foundry: an AI Services account with one project and pay-per-token model deployments.
// Keyless: local (key) auth is disabled, so callers authenticate with Entra ID only. The agents
// run under their own identity, whose only permission is to use this account's models.

@description('Account name; also the custom subdomain of its endpoint.')
param name string

@description('Project name inside the account.')
param projectName string

@description('Name of the identity the agent workers run as.')
param agentsIdentityName string

param location string
param tags object

@description('Model deployments: name (the alias code configures), model, version and capacity in thousands of tokens per minute.')
param deployments array

@description('A developer allowed to call the models from their own machine (empty: none).')
param developerPrincipalId string = ''

resource agentsIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: agentsIdentityName
  location: location
  tags: tags
}

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: name
  location: location
  tags: tags
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: name
    allowProjectManagement: true
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: account
  name: projectName
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {
    displayName: 'Fourth Official'
    description: 'Agents that explain and verify match moments'
  }
}

// One deployment at a time, after the project: the account refuses concurrent changes.
@batchSize(1)
resource modelDeployments 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = [
  for deployment in deployments: {
    parent: account
    name: deployment.name
    // The account takes one change at a time: deploy models only once the project exists.
    dependsOn: [project]
    sku: {
      name: 'GlobalStandard'
      capacity: deployment.capacity
    }
    properties: {
      model: {
        format: 'OpenAI'
        name: deployment.model
        version: deployment.version
      }
      // Model versions change only through a reviewed pull request, never by themselves.
      versionUpgradeOption: 'NoAutoUpgrade'
    }
  }
]

resource agentsCanUseModels 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, agentsIdentity.id, '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  scope: account
  properties: {
    // Azure AI User: use the account's models and projects; no management rights.
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
    principalId: agentsIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource developerCanUseModels 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(developerPrincipalId)) {
  name: guid(account.id, developerPrincipalId, '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  scope: account
  properties: {
    // Azure AI User, for the developer: the same rights as the agents, nothing more.
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
    principalId: developerPrincipalId
    principalType: 'User'
  }
}

output projectEndpoint string = 'https://${account.properties.customSubDomainName}.services.ai.azure.com/api/projects/${project.name}'
output agentsIdentityId string = agentsIdentity.id
output agentsIdentityClientId string = agentsIdentity.properties.clientId
