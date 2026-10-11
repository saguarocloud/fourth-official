// One HTTP container app. Scales to zero when idle; azd replaces the image on deploy.

@maxLength(32)
param name string
param location string
param tags object

@description('azd service name from azure.yaml; azd finds the app by this tag.')
param serviceName string

param environmentId string

@description('Resource ID of the user-assigned identity used to pull images.')
param identityId string

param registryServer string
param targetPort int
param exists bool

@minValue(1)
@maxValue(10)
param maxReplicas int = 3

@description('False keeps the app inside the environment: other apps reach it, the internet cannot.')
param external bool = true

@description('Plain settings for the container, as { name, value }. Never secrets: there are none.')
param env array = []

@description('Further user-assigned identities the app runs as, besides the image-pull identity.')
param additionalIdentityIds string[] = []

// Public placeholder used until the first `azd deploy` pushes a real image. It listens on port 80,
// not targetPort, so it never serves traffic; that is safe because minReplicas is 0 and provisioning
// does not wait for a healthy replica.
var placeholderImage = 'mcr.microsoft.com/k8se/quickstart@sha256:3a4d93c34c6753f24765ab17a36f1754aee9b02082b7d9553d17697b9e8252c4'

module fetchImage 'fetch-container-image.bicep' = {
  name: '${name}-image'
  params: {
    exists: exists
    name: name
  }
}

var currentContainers = fetchImage.outputs.containers

resource app 'Microsoft.App/containerApps@2025-07-01' = {
  name: name
  location: location
  tags: union(tags, { 'azd-service-name': serviceName })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: toObject(concat([identityId], additionalIdentityIds), id => id, id => {})
  }
  properties: {
    managedEnvironmentId: environmentId
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      maxInactiveRevisions: 2
      ingress: {
        external: external
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        { server: registryServer, identity: identityId }
      ]
    }
    template: {
      containers: [
        {
          name: serviceName
          image: empty(currentContainers) ? placeholderImage : currentContainers[0].image
          resources: { cpu: json('0.25'), memory: '0.5Gi' }
          env: env
          probes: [
            {
              type: 'Startup'
              httpGet: { path: '/healthz', port: targetPort }
              periodSeconds: 2
              failureThreshold: 30
            }
            {
              type: 'Readiness'
              httpGet: { path: '/healthz', port: targetPort }
              periodSeconds: 10
              failureThreshold: 3
            }
            {
              type: 'Liveness'
              httpGet: { path: '/healthz', port: targetPort }
              periodSeconds: 30
              failureThreshold: 3
            }
          ]
        }
      ]
      scale: {
        // Scale to zero between uses: we pay nothing while no requests arrive.
        minReplicas: 0
        maxReplicas: maxReplicas
        rules: [
          { name: 'http', http: { metadata: { concurrentRequests: '50' } } }
        ]
      }
    }
  }
}

output name string = app.name
output uri string = 'https://${app.properties.configuration.ingress.fqdn}'
