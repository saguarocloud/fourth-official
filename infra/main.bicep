// Fourth Official: subscription-scope entry point for `azd provision`.

targetScope = 'subscription'

@minLength(1)
@maxLength(32)
@description('azd environment name; used in resource names and the azd-env-name tag.')
param environmentName string

@description('Region for every resource.')
param location string

@description('GitHub repository (owner/name) allowed to deploy from the GitHub environment of the same name. Empty skips the deploy identity, for example when a judge runs `azd up`.')
param githubRepository string = ''

@description('OIDC subject prefix GitHub reports for that repository; set by the preprovision hook.')
param githubSubjectPrefix string = ''

@description('Email for budget alerts. Empty skips the budget.')
param budgetContactEmail string = ''

@minValue(1)
@description('Monthly budget in the billing currency.')
param budgetAmount int = 100

@description('Budget start date (first of a month). Kept fixed: a budget start date cannot move later.')
param budgetStartDate string = '2026-10-01'

@description('Set by azd: true once the api app exists, so provisioning keeps its deployed image.')
param apiExists bool = false

@description('Set by azd: true once the web app exists, so provisioning keeps its deployed image.')
param webExists bool = false

@description('Object ID of the person running azd (azd sets AZURE_PRINCIPAL_ID); may call the models locally.')
param developerPrincipalId string = ''

@description('Principal type of AZURE_PRINCIPAL_ID: User for a person, ServicePrincipal if provisioning runs as one.')
@allowed(['User', 'ServicePrincipal'])
param developerPrincipalType string = 'User'

var tags = {
  'azd-env-name': environmentName
  project: 'fourth-official'
}
var token = toLower(uniqueString(subscription().id, environmentName, location))

resource resourceGroup 'Microsoft.Resources/resourceGroups@2024-11-01' = {
  name: 'rg-fourth-official-${environmentName}'
  location: location
  tags: tags
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  scope: resourceGroup
  params: {
    logAnalyticsName: 'log-${token}'
    applicationInsightsName: 'appi-${token}'
    location: location
    tags: tags
  }
}

module registry 'modules/registry.bicep' = {
  name: 'registry'
  scope: resourceGroup
  params: {
    name: 'crfo${token}'
    location: location
    tags: tags
  }
}

module appIdentity 'modules/app-identity.bicep' = {
  name: 'app-identity'
  scope: resourceGroup
  params: {
    name: 'id-apps-${token}'
    location: location
    tags: tags
    registryName: registry.outputs.name
  }
}

module containerAppsEnvironment 'modules/container-apps-environment.bicep' = {
  name: 'container-apps-environment'
  scope: resourceGroup
  params: {
    name: 'cae-${token}'
    location: location
    tags: tags
    logAnalyticsName: monitoring.outputs.logAnalyticsName
  }
}

module api 'modules/container-app.bicep' = {
  name: 'api'
  scope: resourceGroup
  params: {
    name: 'ca-api-${token}'
    location: location
    tags: tags
    serviceName: 'api'
    environmentId: containerAppsEnvironment.outputs.id
    // Using the module output also orders the app after the AcrPull assignment in that module.
    identityId: appIdentity.outputs.id
    registryServer: registry.outputs.loginServer
    targetPort: 8000
    exists: apiExists
    // One replica: the matchday's run guards (one run at a time, cooldown, daily budget) live in
    // the process, so a single replica is what bounds model spend for the whole deployment.
    maxReplicas: 1
  }
}

module web 'modules/container-app.bicep' = {
  name: 'web'
  scope: resourceGroup
  params: {
    name: 'ca-web-${token}'
    location: location
    tags: tags
    serviceName: 'web'
    environmentId: containerAppsEnvironment.outputs.id
    identityId: appIdentity.outputs.id
    registryServer: registry.outputs.loginServer
    targetPort: 3000
    exists: webExists
  }
}

module foundry 'modules/foundry.bicep' = {
  name: 'foundry'
  scope: resourceGroup
  params: {
    name: 'ais-${token}'
    projectName: 'proj-fourth-official'
    agentsIdentityName: 'id-agents-${token}'
    location: location
    tags: tags
    developerPrincipalId: developerPrincipalId
    developerPrincipalType: developerPrincipalType
    // Code refers to models by alias (fast, fallback); the deployment name is the alias.
    deployments: [
      { name: 'fast', model: 'gpt-5-mini', version: '2025-08-07', capacity: 100 }
      { name: 'fallback', model: 'gpt-4.1-mini', version: '2025-04-14', capacity: 50 }
    ]
  }
}

module deployIdentity 'modules/deploy-identity.bicep' = if (!empty(githubRepository) && !empty(githubSubjectPrefix)) {
  name: 'deploy-identity'
  scope: resourceGroup
  params: {
    name: 'id-gha-${token}'
    location: location
    tags: tags
    githubSubjectPrefix: githubSubjectPrefix
    githubEnvironment: environmentName
    registryName: registry.outputs.name
    containerAppNames: [api.outputs.name, web.outputs.name]
    appIdentityName: appIdentity.outputs.name
    managedEnvironmentName: containerAppsEnvironment.outputs.name
  }
}

// One budget for the whole subscription (the credit is subscription-wide), shared by all environments.
module budget 'modules/budget.bicep' = if (!empty(budgetContactEmail)) {
  name: 'budget'
  params: {
    name: 'budget-fourth-official'
    amount: budgetAmount
    startDate: budgetStartDate
    contactEmails: [budgetContactEmail]
  }
}

// Outputs become azd environment values (and GitHub environment variables via the postprovision hook).
output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_RESOURCE_GROUP string = resourceGroup.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = registry.outputs.loginServer
output AZURE_DEPLOY_CLIENT_ID string = deployIdentity.?outputs.clientId ?? ''
output SERVICE_API_NAME string = api.outputs.name
output SERVICE_API_URI string = api.outputs.uri
output SERVICE_WEB_NAME string = web.outputs.name
output SERVICE_WEB_URI string = web.outputs.uri
output FOUNDRY_PROJECT_ENDPOINT string = foundry.outputs.projectEndpoint
output AGENTS_IDENTITY_CLIENT_ID string = foundry.outputs.agentsIdentityClientId
