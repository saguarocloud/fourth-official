#!/bin/sh
# Before `azd provision`: record which container apps already exist, so the Bicep keeps the image
# `azd deploy` last released instead of resetting it to the placeholder (see fetch-container-image.bicep).
# azd does not refresh SERVICE_<NAME>_RESOURCE_EXISTS on its own after the first provision.
# Fails closed: if existence cannot be determined, provisioning stops rather than risk a reset.
set -eu

SERVICES="api web"
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-}"
SUBSCRIPTION="${AZURE_SUBSCRIPTION_ID:?AZURE_SUBSCRIPTION_ID must be set}"

group_exists=false
if [ -n "$RESOURCE_GROUP" ]; then
  command -v az >/dev/null 2>&1 || { echo "preprovision: the az CLI is required" >&2; exit 1; }
  # `az group exists` answers true/false and fails on auth or subscription problems.
  group_exists="$(az group exists --name "$RESOURCE_GROUP" --subscription "$SUBSCRIPTION")"
fi

for service in $SERVICES; do
  exists=false
  if [ "$group_exists" = "true" ]; then
    count="$(az resource list --subscription "$SUBSCRIPTION" -g "$RESOURCE_GROUP" \
      --resource-type Microsoft.App/containerApps \
      --query "length([?tags.\"azd-service-name\" == '$service'])" -o tsv)"
    [ "$count" -gt 0 ] && exists=true
  fi
  key="SERVICE_$(echo "$service" | tr '[:lower:]' '[:upper:]')_RESOURCE_EXISTS"
  azd env set "$key" "$exists"
  echo "preprovision: $key=$exists"
done
