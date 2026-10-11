"""Infrastructure policy tests (cost, security, least privilege) on the compiled Bicep."""

import re

from arm import CompiledTemplate

ACR_PUSH = "8311e382-0749-4cb8-b61a-304f252e45ec"
ACR_PULL = "7f951dda-4ed3-4680-a7ca-43fe172d538d"
CONTAINER_APPS_CONTRIBUTOR = "358470bc-b998-42bd-ab17-a7e34c199c0f"
READER = "acdd72a7-3385-48ef-bd42-f606fba81ae7"
OWNER = "8e3af657-a8ff-443c-a75c-2fe8c4bcb635"
CONTRIBUTOR = "b24988ac-6180-42a0-ab88-20f7382dd24c"
USER_ACCESS_ADMINISTRATOR = "18d7d88d-d35e-4fb5-a5c3-7773c20a72d9"
RBAC_ADMINISTRATOR = "f58310d9-a9f6-439a-9e8d-f62e7b41a168"
MANAGED_IDENTITY_OPERATOR = "f1a07417-d97a-45cb-824c-7a7467783830"
GUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}")


def _number(value: object) -> float:
    """Read a numeric property, including Bicep's `json('0.5')` form for decimals."""
    if isinstance(value, int | float):
        return float(value)
    match = re.fullmatch(r"\[json\('([0-9.]+)'\)\]", str(value))
    assert match, f"not a numeric literal: {value!r}"
    return float(match.group(1))


def _role_ids_in(compiled: CompiledTemplate, module_fragment: str) -> set[str]:
    ids: set[str] = set()
    for assignment in compiled.of_type("Microsoft.Authorization/roleAssignments"):
        if module_fragment in assignment.module:
            ids.update(GUID.findall(str(assignment.body)))
    return ids


# --- Cost -------------------------------------------------------------------------------------


def test_every_container_app_scales_to_zero(compiled: CompiledTemplate) -> None:
    apps = compiled.of_type("Microsoft.App/containerApps")

    assert apps, "expected container apps in the template"
    for app in apps:
        assert app.properties["template"]["scale"]["minReplicas"] == 0, app.module


def test_container_apps_environment_uses_consumption_only(compiled: CompiledTemplate) -> None:
    (env,) = compiled.of_type("Microsoft.App/managedEnvironments")

    profiles = env.properties["workloadProfiles"]
    assert [p["workloadProfileType"] for p in profiles] == ["Consumption"]
    assert env.properties.get("zoneRedundant", False) is False


def test_log_analytics_has_daily_cap_and_short_retention(compiled: CompiledTemplate) -> None:
    (workspace,) = compiled.of_type("Microsoft.OperationalInsights/workspaces")

    assert 0 < _number(workspace.properties["workspaceCapping"]["dailyQuotaGb"]) <= 0.5
    assert workspace.properties["retentionInDays"] == 30


def test_registry_is_basic_tier(compiled: CompiledTemplate) -> None:
    (registry,) = compiled.of_type("Microsoft.ContainerRegistry/registries")

    assert registry.body["sku"]["name"] == "Basic"


def test_budget_alerts_at_quarter_thresholds(compiled: CompiledTemplate) -> None:
    (budget,) = compiled.of_type("Microsoft.Consumption/budgets")

    thresholds = sorted(n["threshold"] for n in budget.properties["notifications"].values())
    assert thresholds == [25, 50, 75, 100]
    assert budget.properties["timeGrain"] == "Monthly"


# --- Security ---------------------------------------------------------------------------------


def test_registry_disallows_admin_user_and_anonymous_pull(compiled: CompiledTemplate) -> None:
    (registry,) = compiled.of_type("Microsoft.ContainerRegistry/registries")

    assert registry.properties["adminUserEnabled"] is False
    assert registry.properties["anonymousPullEnabled"] is False


def test_container_apps_pull_images_with_managed_identity_only(compiled: CompiledTemplate) -> None:
    for app in compiled.of_type("Microsoft.App/containerApps"):
        registries = app.properties["configuration"]["registries"]
        assert registries, app.module
        for registry in registries:
            assert "identity" in registry, app.module
            assert "passwordSecretRef" not in registry, app.module
        assert not app.properties["configuration"].get("secrets"), app.module


def test_container_apps_reject_plain_http(compiled: CompiledTemplate) -> None:
    for app in compiled.of_type("Microsoft.App/containerApps"):
        assert app.properties["configuration"]["ingress"]["allowInsecure"] is False, app.module


def test_container_apps_probe_healthz(compiled: CompiledTemplate) -> None:
    for app in compiled.of_type("Microsoft.App/containerApps"):
        (container,) = app.properties["template"]["containers"]
        probes = {p["type"]: p for p in container["probes"]}
        assert set(probes) == {"Startup", "Liveness", "Readiness"}, app.module
        assert {p["httpGet"]["path"] for p in probes.values()} == {"/healthz"}, app.module


def test_container_apps_are_tagged_for_azd(compiled: CompiledTemplate) -> None:
    for app in compiled.of_type("Microsoft.App/containerApps"):
        assert "azd-service-name" in str(app.body["tags"]), app.module


def test_apps_identity_can_only_pull_images(compiled: CompiledTemplate) -> None:
    assert _role_ids_in(compiled, "app-identity") == {ACR_PULL}


def test_deploy_identity_is_least_privilege(compiled: CompiledTemplate) -> None:
    expected = {ACR_PUSH, CONTAINER_APPS_CONTRIBUTOR, READER, MANAGED_IDENTITY_OPERATOR}

    assert _role_ids_in(compiled, "deploy-identity") == expected


def test_no_broad_or_role_granting_roles_anywhere(compiled: CompiledTemplate) -> None:
    text = compiled.text()

    for role in (OWNER, CONTRIBUTOR, USER_ACCESS_ADMINISTRATOR, RBAC_ADMINISTRATOR):
        assert role not in text


def test_role_assignments_declare_service_principal_type(compiled: CompiledTemplate) -> None:
    for assignment in compiled.of_type("Microsoft.Authorization/roleAssignments"):
        assert assignment.properties["principalType"] == "ServicePrincipal", assignment.module


def test_github_federated_credential_is_scoped_to_one_environment(
    compiled: CompiledTemplate,
) -> None:
    (credential,) = compiled.of_type(
        "Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials"
    )

    assert credential.properties["issuer"] == "https://token.actions.githubusercontent.com"
    assert credential.properties["audiences"] == ["api://AzureADTokenExchange"]
    subject = credential.properties["subject"]
    assert "environment:" in subject
    assert "ref:" not in subject
    assert "pull_request" not in subject


def test_outputs_never_expose_secrets(compiled: CompiledTemplate) -> None:
    # A naming tripwire on top of the linter rule `outputs-should-not-contain-secrets` (an error
    # in bicepconfig.json), which inspects output values in every module.
    for name in compiled.template.get("outputs", {}):
        assert not re.search(r"key|secret|password|connectionstring", name, re.IGNORECASE), name


def test_deploy_identity_can_only_modify_the_container_apps_themselves(
    compiled: CompiledTemplate,
) -> None:
    contributor_assignments = [
        a
        for a in compiled.of_type("Microsoft.Authorization/roleAssignments")
        if "deploy-identity" in a.module and CONTAINER_APPS_CONTRIBUTOR in str(a.body)
    ]

    assert contributor_assignments
    for assignment in contributor_assignments:
        # Scoped to each app, not the resource group: the environment itself stays out of reach.
        assert "Microsoft.App/containerApps" in assignment.body.get("scope", ""), assignment.body


# Expected scope of each role, by resource type in the assignment's `scope` (None: resource group).
EXPECTED_ROLE_SCOPES = {
    ACR_PULL: "Microsoft.ContainerRegistry/registries",
    ACR_PUSH: "Microsoft.ContainerRegistry/registries",
    CONTAINER_APPS_CONTRIBUTOR: "Microsoft.App/containerApps",
    MANAGED_IDENTITY_OPERATOR: "Microsoft.ManagedIdentity/userAssignedIdentities",
    READER: None,
}


def test_every_role_assignment_has_its_narrowest_scope(compiled: CompiledTemplate) -> None:
    assignments = compiled.of_type("Microsoft.Authorization/roleAssignments")

    assert assignments
    for assignment in assignments:
        (role,) = set(GUID.findall(str(assignment.properties["roleDefinitionId"])))
        expected = EXPECTED_ROLE_SCOPES[role]
        scope = assignment.body.get("scope")
        if expected is None:
            assert scope is None, (role, scope)
        else:
            assert expected in str(scope), (role, scope)


def test_container_logs_flow_without_shared_keys(compiled: CompiledTemplate) -> None:
    (env,) = compiled.of_type("Microsoft.App/managedEnvironments")
    (workspace,) = compiled.of_type("Microsoft.OperationalInsights/workspaces")
    (diagnostics,) = compiled.of_type("Microsoft.Insights/diagnosticSettings")

    assert env.properties["appLogsConfiguration"]["destination"] == "azure-monitor"
    # Dedicated tables (ContainerAppConsoleLogs, ...), not the shared AzureDiagnostics table.
    assert diagnostics.properties["logAnalyticsDestinationType"] == "Dedicated"
    assert workspace.properties["features"]["disableLocalAuth"] is True
    categories = {log["category"] for log in diagnostics.properties["logs"] if log["enabled"]}
    assert categories == {"ContainerAppConsoleLogs", "ContainerAppSystemLogs"}
    assert "listKeys" not in compiled.text()
