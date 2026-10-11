#!/bin/sh
# After `azd provision`: hand GitHub Actions what it needs to deploy, as environment-scoped
# secrets and variables. Runs only when a deploy identity was provisioned (GITHUB_DEPLOY_REPOSITORY set).
set -eu

if [ -z "${GITHUB_DEPLOY_REPOSITORY:-}" ] || [ -z "${AZURE_DEPLOY_CLIENT_ID:-}" ]; then
  echo "postprovision: no GitHub deploy identity configured; skipping GitHub setup."
  exit 0
fi
command -v gh >/dev/null 2>&1 || { echo "postprovision: gh CLI is required to configure GitHub" >&2; exit 1; }

REPO="$GITHUB_DEPLOY_REPOSITORY"
ENV_NAME="$AZURE_ENV_NAME"
echo "postprovision: configuring GitHub environment '$ENV_NAME' on $REPO"

# Deployments to this environment are allowed from main only.
gh api -X PUT "repos/$REPO/environments/$ENV_NAME" --input - >/dev/null <<JSON
{"deployment_branch_policy": {"protected_branches": false, "custom_branch_policies": true}}
JSON
if ! gh api "repos/$REPO/environments/$ENV_NAME/deployment-branch-policies" --jq '.branch_policies[].name' | grep -qx main; then
  gh api -X POST "repos/$REPO/environments/$ENV_NAME/deployment-branch-policies" -f name=main -f type=branch >/dev/null
fi

# Identifiers, not credentials: workload identity federation means there is no secret to leak.
# They are stored as secrets so they stay out of public logs.
gh secret set AZURE_CLIENT_ID --repo "$REPO" --env "$ENV_NAME" --body "$AZURE_DEPLOY_CLIENT_ID"
gh secret set AZURE_TENANT_ID --repo "$REPO" --env "$ENV_NAME" --body "$AZURE_TENANT_ID"
gh secret set AZURE_SUBSCRIPTION_ID --repo "$REPO" --env "$ENV_NAME" --body "$AZURE_SUBSCRIPTION_ID"

for name in AZURE_ENV_NAME AZURE_LOCATION AZURE_RESOURCE_GROUP AZURE_CONTAINER_REGISTRY_ENDPOINT \
            SERVICE_API_NAME SERVICE_API_URI SERVICE_WEB_NAME SERVICE_WEB_URI; do
  eval "value=\${$name}"
  gh variable set "$name" --repo "$REPO" --env "$ENV_NAME" --body "$value"
done

echo "postprovision: GitHub environment '$ENV_NAME' is ready for deployments."
