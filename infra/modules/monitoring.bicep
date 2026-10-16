// Log Analytics (with a hard daily cap) and workspace-based Application Insights.

@description('Log Analytics workspace name.')
param logAnalyticsName string

@description('Application Insights component name.')
param applicationInsightsName string

@description('Principal ID of the identity the API signs in with: the only publisher of telemetry.')
param publisherPrincipalId string

param location string
param tags object

resource workspace 'Microsoft.OperationalInsights/workspaces@2025-02-01' = {
  name: logAnalyticsName
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    // Hard cap on ingestion: a runaway log loop must not drain the credit.
    workspaceCapping: { dailyQuotaGb: json('0.5') }
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
      // Entra ID only: no workspace shared keys can be used to read or write data.
      disableLocalAuth: true
    }
  }
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: applicationInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspace.id
    // Ingestion requires Entra ID auth; instrumentation keys alone cannot write telemetry.
    DisableLocalAuth: true
  }
}

// The API's traces and metrics, written with Entra ID (local auth is disabled above).
resource apiCanPublish 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(applicationInsights.id, publisherPrincipalId, '3913510d-42f4-4e42-8a64-420c390055eb')
  scope: applicationInsights
  properties: {
    // Monitoring Metrics Publisher, on this component only.
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '3913510d-42f4-4e42-8a64-420c390055eb')
    principalId: publisherPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output logAnalyticsName string = workspace.name
output applicationInsightsName string = applicationInsights.name
// Not a secret: it names where to send telemetry, and sending requires Entra ID.
output connectionString string = applicationInsights.properties.ConnectionString
