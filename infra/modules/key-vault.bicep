// The studio's provenance signing key (ADR-013): a Standard vault with RBAC only, one EC P-256 key
// that can only sign and verify, and one identity allowed to use that key and nothing else.
// The private key never leaves the vault.

@minLength(3)
@maxLength(24)
param name string
param location string
param tags object

@description('Principal ID of the identity that signs provenance records (the API).')
param signerPrincipalId string

resource vault 'Microsoft.KeyVault/vaults@2024-11-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    // Entra ID roles only: no access policies.
    enableRbacAuthorization: true
    accessPolicies: []
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    // Reachable from the Consumption environment, which has no fixed egress; useless without a role.
    publicNetworkAccess: 'Enabled'
  }
}

resource key 'Microsoft.KeyVault/vaults/keys@2024-11-01' = {
  parent: vault
  name: 'provenance'
  properties: {
    kty: 'EC'
    curveName: 'P-256'
    keyOps: ['sign', 'verify']
  }
}

resource signerCanUseKey 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(key.id, signerPrincipalId, '12338af0-0e69-4776-bea7-57ae8d297424')
  scope: key
  properties: {
    // Key Vault Crypto User
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '12338af0-0e69-4776-bea7-57ae8d297424')
    principalId: signerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// The key version that signs: records name it, so a rotated key does not verify old records falsely.
output keyUriWithVersion string = key.properties.keyUriWithVersion
