// Identity for the Proving Ground's Release Gate in GitHub Actions (ADR-014), via workload identity
// federation (no secrets). It is trusted only for this repository's pull requests (GitHub issues no
// token to a fork's), and it can do one thing: run inference on the Foundry account's models. Not
// the broader Azure AI User the agents hold, which also manages agents and deployments and lists
// keys and connection secrets. It cannot deploy, read storage or sign anything.

param name string
param location string
param tags object

@description('OIDC subject prefix GitHub reports for the repository (actions/oidc/customization/sub).')
param githubSubjectPrefix string

@description('The Foundry (AI Services) account whose models the gate runs on.')
param foundryAccountName string

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: name
  location: location
  tags: tags
}

resource credential 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2024-11-30' = {
  parent: identity
  name: 'github-pull-request'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: '${githubSubjectPrefix}:pull_request'
    audiences: ['api://AzureADTokenExchange']
  }
}

resource account 'Microsoft.CognitiveServices/accounts@2026-09-01' existing = {
  name: foundryAccountName
}

resource canUseModels 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, identity.id, '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  scope: account
  properties: {
    // Cognitive Services OpenAI User: chat, responses and completions on the deployments; no keys,
    // connection secrets, agents' management or deployments.
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

output clientId string = identity.properties.clientId
