#!/bin/sh
# After `azd provision`: hand GitHub Actions what it needs to deploy, as environment-scoped
# secrets and variables. Runs only when a deploy identity was provisioned (GITHUB_DEPLOY_REPOSITORY set).
# POSIX shells only; on Windows, run it from WSL or Git Bash.
set -eu

# Template outputs published as GitHub environment variables for the deploy workflow.
GITHUB_VARIABLES="AZURE_ENV_NAME AZURE_LOCATION AZURE_RESOURCE_GROUP AZURE_CONTAINER_REGISTRY_ENDPOINT SERVICE_API_NAME SERVICE_API_URI SERVICE_WEB_NAME SERVICE_WEB_URI"
# The only branch allowed to deploy to the environment.
DEPLOY_BRANCH="main"

if [ -z "${GITHUB_DEPLOY_REPOSITORY:-}" ] || [ -z "${AZURE_DEPLOY_CLIENT_ID:-}" ]; then
  echo "postprovision: no GitHub deploy identity configured; skipping GitHub setup."
  exit 0
fi
command -v gh >/dev/null 2>&1 || { echo "postprovision: the gh CLI is required" >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "postprovision: jq is required" >&2; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "postprovision: run 'gh auth login' first" >&2; exit 1; }

REPO="$GITHUB_DEPLOY_REPOSITORY"
ENV_NAME="$AZURE_ENV_NAME"
ENV_API="repos/$REPO/environments/$ENV_NAME"
echo "postprovision: configuring GitHub environment '$ENV_NAME' on $REPO"

# PUT replaces the environment's protection settings, so carry over reviewers and wait timer
# that an admin may have configured in the GitHub UI.
current="$(gh api "$ENV_API" 2>/dev/null || echo '{}')"
jq -n --argjson current "$current" '{
  wait_timer: ([$current.protection_rules[]? | select(.type == "wait_timer") | .wait_timer][0] // 0),
  prevent_self_review: ([$current.protection_rules[]? | select(.type == "required_reviewers") | .prevent_self_review][0] // false),
  reviewers: ([$current.protection_rules[]? | select(.type == "required_reviewers") | .reviewers[]? | {type, id: .reviewer.id}]),
  deployment_branch_policy: {protected_branches: false, custom_branch_policies: true}
}' | gh api -X PUT "$ENV_API" --input - >/dev/null

# Exactly one branch policy: remove anything else, then ensure the deploy branch is present.
policies="$(gh api "$ENV_API/deployment-branch-policies" --jq '.branch_policies[] | "\(.id) \(.name)"')"
echo "$policies" | while read -r id name; do
  if [ -n "$id" ] && [ "$name" != "$DEPLOY_BRANCH" ]; then
    echo "postprovision: removing branch policy '$name'"
    gh api -X DELETE "$ENV_API/deployment-branch-policies/$id" >/dev/null
  fi
done
if ! echo "$policies" | awk '{print $2}' | grep -qx "$DEPLOY_BRANCH"; then
  gh api -X POST "$ENV_API/deployment-branch-policies" -f name="$DEPLOY_BRANCH" -f type=branch >/dev/null
fi

# Identifiers, not credentials: workload identity federation means there is no secret to leak.
# They are stored as secrets so they stay out of public logs.
gh secret set AZURE_CLIENT_ID --repo "$REPO" --env "$ENV_NAME" --body "$AZURE_DEPLOY_CLIENT_ID"
gh secret set AZURE_TENANT_ID --repo "$REPO" --env "$ENV_NAME" --body "$AZURE_TENANT_ID"
gh secret set AZURE_SUBSCRIPTION_ID --repo "$REPO" --env "$ENV_NAME" --body "$AZURE_SUBSCRIPTION_ID"

for name in $GITHUB_VARIABLES; do
  value="$(printenv "$name" || true)"
  [ -n "$value" ] || { echo "postprovision: $name is empty; was provisioning incomplete?" >&2; exit 1; }
  gh variable set "$name" --repo "$REPO" --env "$ENV_NAME" --body "$value"
done

echo "postprovision: GitHub environment '$ENV_NAME' deploys from '$DEPLOY_BRANCH' only."
