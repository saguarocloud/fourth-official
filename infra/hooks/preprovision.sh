#!/bin/sh
# Before `azd provision`: record which container apps already exist, so the Bicep keeps the image
# `azd deploy` last released instead of resetting it to the placeholder (see fetch-container-image.bicep).
# azd does not refresh SERVICE_<NAME>_RESOURCE_EXISTS on its own after the first provision.
set -eu

SERVICES="api web"
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-}"

for service in $SERVICES; do
  exists=false
  if [ -n "$RESOURCE_GROUP" ] && az group show -n "$RESOURCE_GROUP" >/dev/null 2>&1; then
    count="$(az resource list -g "$RESOURCE_GROUP" --resource-type Microsoft.App/containerApps \
      --query "length([?tags.\"azd-service-name\" == '$service'])" -o tsv)"
    [ "$count" -gt 0 ] && exists=true
  fi
  key="SERVICE_$(echo "$service" | tr '[:lower:]' '[:upper:]')_RESOURCE_EXISTS"
  azd env set "$key" "$exists"
  echo "preprovision: $key=$exists"
done
