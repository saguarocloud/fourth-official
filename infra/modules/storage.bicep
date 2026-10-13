// The matchday's start ledger (ADR-008) and the signed provenance records (ADR-013): one keyless
// Standard LRS account, a private container for each, and for each one identity allowed to read
// and write blobs in that container only.

@minLength(3)
@maxLength(24)
param name string
param location string
param tags object

@description('Container that holds the start ledger blob.')
param containerName string = 'matchday'

@description('Container that holds the signed provenance records.')
param provenanceContainerName string = 'provenance'

@description('Principal ID of the identity that claims matchday starts (the API).')
param writerPrincipalId string

@description('Principal ID of the identity that keeps provenance records (the API signer).')
param recordsWriterPrincipalId string

resource account 'Microsoft.Storage/storageAccounts@2025-01-01' = {
  name: name
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    accessTier: 'Hot'
    // Entra ID only: no account keys, no SAS signed with them.
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    allowBlobPublicAccess: false
    allowCrossTenantReplication: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    // Reachable from the Consumption environment, which has no fixed egress; useless without a token.
    publicNetworkAccess: 'Enabled'
  }
}

// The ledger is the spend control: a bad write or a delete must be recoverable.
resource blobs 'Microsoft.Storage/storageAccounts/blobServices@2025-01-01' = {
  parent: account
  name: 'default'
  properties: {
    isVersioningEnabled: true
    deleteRetentionPolicy: { enabled: true, days: 7 }
    containerDeleteRetentionPolicy: { enabled: true, days: 7 }
  }
}

resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-01-01' = {
  parent: blobs
  name: containerName
  properties: { publicAccess: 'None' }
}

resource writerCanUseLedger 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(container.id, writerPrincipalId, 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  scope: container
  properties: {
    // Storage Blob Data Contributor
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: writerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Policy Studio's book: every partner's policy history, one blob per partner (versioned too).
resource policies 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-01-01' = {
  parent: blobs
  name: 'policies'
  properties: {
    publicAccess: 'None'
  }
}

resource writerCanKeepPolicies 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(policies.id, writerPrincipalId, 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  scope: policies
  properties: {
    // Storage Blob Data Contributor, on the policy book's container only.
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: writerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource provenance 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-01-01' = {
  parent: blobs
  name: provenanceContainerName
  properties: { publicAccess: 'None' }
}

resource writerCanKeepRecords 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(provenance.id, recordsWriterPrincipalId, 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  scope: provenance
  properties: {
    // Storage Blob Data Contributor
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: recordsWriterPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output policyBookUrl string = '${account.properties.primaryEndpoints.blob}${policies.name}'
output provenanceContainerUrl string = '${account.properties.primaryEndpoints.blob}${provenance.name}'
output startLedgerUrl string = '${account.properties.primaryEndpoints.blob}${container.name}/starts.json'
