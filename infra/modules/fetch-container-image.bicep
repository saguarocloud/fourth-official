// Returns the containers of an existing app, so re-running `azd provision` keeps the image that
// `azd deploy` last released instead of resetting it to the placeholder.

param exists bool
param name string

resource existingApp 'Microsoft.App/containerApps@2025-07-01' existing = if (exists) {
  name: name
}

output containers array = exists ? existingApp!.properties.template.containers : []
