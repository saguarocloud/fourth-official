// Container Apps environment on the serverless Consumption profile only.
// Logs reach Log Analytics through Azure Monitor diagnostic settings, so no workspace key is used.

param name string
param location string
param tags object

@description('Log Analytics workspace that receives container logs.')
param logAnalyticsName string

resource workspace 'Microsoft.OperationalInsights/workspaces@2025-02-01' existing = {
  name: logAnalyticsName
}

resource environment 'Microsoft.App/managedEnvironments@2025-07-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: { destination: 'azure-monitor' }
    workloadProfiles: [
      { name: 'Consumption', workloadProfileType: 'Consumption' }
    ]
    zoneRedundant: false
  }
}

// 2021-05-01-preview is the current schema for resource diagnostic settings (the only stable
// version, 2016-09-01, is the legacy service-level shape); Azure Verified Modules use it too.
#disable-next-line use-recent-api-versions
resource logs 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'logs-to-workspace'
  scope: environment
  properties: {
    workspaceId: workspace.id
    // Resource-specific tables (ContainerAppConsoleLogs, ContainerAppSystemLogs), not AzureDiagnostics.
    logAnalyticsDestinationType: 'Dedicated'
    logs: [
      { category: 'ContainerAppConsoleLogs', enabled: true }
      { category: 'ContainerAppSystemLogs', enabled: true }
    ]
  }
}

output id string = environment.id
output defaultDomain string = environment.properties.defaultDomain
