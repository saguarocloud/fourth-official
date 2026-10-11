// Log Analytics (with a hard daily cap) and workspace-based Application Insights.

@description('Log Analytics workspace name.')
param logAnalyticsName string

@description('Application Insights component name.')
param applicationInsightsName string

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
    features: { enableLogAccessUsingOnlyResourcePermissions: true }
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

output logAnalyticsName string = workspace.name
output applicationInsightsName string = applicationInsights.name
