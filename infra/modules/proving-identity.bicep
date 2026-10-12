// Identity for the Proving Ground's Release Gate in GitHub Actions (ADR-014), via workload identity
// federation (no secrets). It is trusted only for this repository's pull requests (GitHub issues no
// token to a fork's), and it can use the models through one Foundry project. It cannot deploy, read
// storage, sign anything, or touch the account itself.

param name string
param location string
param tags object

@description('OIDC subject prefix GitHub reports for the repository (actions/oidc/customization/sub).')
param githubSubjectPrefix string

@description('The Foundry (AI Services) account whose models the gate runs on.')
param foundryAccountName string

@description('The Foundry project the gate calls the models through.')
param foundryProjectName string

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

resource project 'Microsoft.CognitiveServices/accounts/projects@2026-09-01' existing = {
  parent: account
  name: foundryProjectName
}

// Azure AI User, as the Foundry project endpoint requires (narrower roles are refused: the
// Cognitive Services OpenAI User role and an inference-only custom role both got 403), on the one
// project only: not the account, so it cannot list the account's keys or reach another project.
resource canUseModels 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(project.id, identity.id, '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  scope: project
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

output clientId string = identity.properties.clientId
