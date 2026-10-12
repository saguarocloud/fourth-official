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

// No built-in role fits. Cognitive Services OpenAI User lacks the AIServices data actions the
// Foundry project endpoint checks (its responses API answers 403), and Azure AI User also lists keys
// and connection secrets and manages agents. This role can create and read responses, and chat.
resource inference 'Microsoft.Authorization/roleDefinitions@2022-04-01' = {
  name: guid(resourceGroup().id, 'fourth-official-model-inference')
  properties: {
    roleName: 'Fourth Official model inference (${resourceGroup().name})'
    description: 'Create and read model responses on the Foundry account. Nothing else.'
    type: 'CustomRole'
    assignableScopes: [resourceGroup().id]
    permissions: [
      {
        actions: []
        notActions: []
        dataActions: [
          // Resolving and invoking a model deployment through the project endpoint.
          'Microsoft.CognitiveServices/accounts/AIServices/deployments/read'
          'Microsoft.CognitiveServices/accounts/AIServices/endpoints/invoke/action'
          'Microsoft.CognitiveServices/accounts/AIServices/endpoints/interact/action'
          'Microsoft.CognitiveServices/accounts/AIServices/responses/read'
          'Microsoft.CognitiveServices/accounts/AIServices/responses/write'
          'Microsoft.CognitiveServices/accounts/OpenAI/responses/read'
          'Microsoft.CognitiveServices/accounts/OpenAI/responses/write'
          'Microsoft.CognitiveServices/accounts/OpenAI/deployments/chat/completions/action'
        ]
        notDataActions: []
      }
    ]
  }
}

resource canUseModels 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, identity.id, inference.id)
  scope: account
  properties: {
    roleDefinitionId: inference.id
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

output clientId string = identity.properties.clientId
