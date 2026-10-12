"""Infrastructure policy tests (cost, security, least privilege) on the compiled Bicep."""

import re

from arm import CompiledTemplate, Resource

ACR_PUSH = "8311e382-0749-4cb8-b61a-304f252e45ec"
ACR_PULL = "7f951dda-4ed3-4680-a7ca-43fe172d538d"
CONTAINER_APPS_CONTRIBUTOR = "358470bc-b998-42bd-ab17-a7e34c199c0f"
READER = "acdd72a7-3385-48ef-bd42-f606fba81ae7"
OWNER = "8e3af657-a8ff-443c-a75c-2fe8c4bcb635"
CONTRIBUTOR = "b24988ac-6180-42a0-ab88-20f7382dd24c"
USER_ACCESS_ADMINISTRATOR = "18d7d88d-d35e-4fb5-a5c3-7773c20a72d9"
RBAC_ADMINISTRATOR = "f58310d9-a9f6-439a-9e8d-f62e7b41a168"
MANAGED_IDENTITY_OPERATOR = "f1a07417-d97a-45cb-824c-7a7467783830"
AZURE_AI_USER = "53ca6127-db72-4b80-b1b0-d745d6d5456d"
STORAGE_BLOB_DATA_CONTRIBUTOR = "ba92f5b4-2d11-453d-a403-e96b0029c9fe"
KEY_VAULT_CRYPTO_USER = "12338af0-0e69-4776-bea7-57ae8d297424"
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


def _is_developer_assignment(assignment: Resource) -> bool:
    return "developerPrincipalId" in str(assignment.properties["principalId"])


def test_role_assignments_declare_service_principal_type(compiled: CompiledTemplate) -> None:
    for assignment in compiled.of_type("Microsoft.Authorization/roleAssignments"):
        if not _is_developer_assignment(assignment):
            assert assignment.properties["principalType"] == "ServicePrincipal", assignment.module


def test_the_only_role_a_person_can_hold_is_using_models_on_the_foundry_account(
    compiled: CompiledTemplate,
) -> None:
    (developer,) = [
        a
        for a in compiled.of_type("Microsoft.Authorization/roleAssignments")
        if _is_developer_assignment(a)
    ]

    assert "foundry" in developer.module
    assert GUID.findall(str(developer.properties["roleDefinitionId"])) == [AZURE_AI_USER]
    # Granted only when a developer is named, and only on the account.
    assert "empty(parameters('developerPrincipalId'))" in str(developer.body["condition"])
    assert "Microsoft.CognitiveServices/accounts'" in str(developer.body["scope"])
    assert "developerPrincipalType" in str(developer.properties["principalType"])


def test_github_federated_credential_is_scoped_to_one_environment(
    compiled: CompiledTemplate,
) -> None:
    (credential,) = [
        c
        for c in compiled.of_type(
            "Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials"
        )
        if "deploy-identity" in c.module
    ]

    assert credential.properties["issuer"] == "https://token.actions.githubusercontent.com"
    assert credential.properties["audiences"] == ["api://AzureADTokenExchange"]
    # Exactly the prefix GitHub reports for the repository (ID-based when immutable subjects are
    # on) plus one environment: no branch, pull request or wildcard form can match.
    assert credential.properties["subject"] == (
        "[format('{0}:environment:{1}', parameters('githubSubjectPrefix'), "
        "parameters('githubEnvironment'))]"
    )


def test_the_proving_identity_is_trusted_only_for_pull_requests(
    compiled: CompiledTemplate,
) -> None:
    (credential,) = [
        c
        for c in compiled.of_type(
            "Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials"
        )
        if "proving-identity" in c.module
    ]

    assert credential.properties["issuer"] == "https://token.actions.githubusercontent.com"
    assert credential.properties["audiences"] == ["api://AzureADTokenExchange"]
    # Pull requests of this repository only: GitHub issues no token to a fork's pull request, and
    # no branch, environment or wildcard form can match.
    assert credential.properties["subject"] == (
        "[format('{0}:pull_request', parameters('githubSubjectPrefix'))]"
    )


def test_the_proving_identity_can_only_use_models(compiled: CompiledTemplate) -> None:
    assignments = [
        a
        for a in compiled.of_type("Microsoft.Authorization/roleAssignments")
        if "proving-identity" in a.module
    ]

    assert [GUID.findall(str(a.properties["roleDefinitionId"])) for a in assignments] == [
        [AZURE_AI_USER]
    ]
    assert "Microsoft.CognitiveServices/accounts'" in str(assignments[0].body["scope"])
    assert "AZURE_PROVING_CLIENT_ID" in compiled.template["outputs"]


def test_outputs_never_expose_secrets(compiled: CompiledTemplate) -> None:
    # A naming tripwire on top of the linter rule `outputs-should-not-contain-secrets` (an error
    # in bicepconfig.json), which inspects output values in every module.
    for name in compiled.template.get("outputs", {}):
        assert not re.search(r"key|secret|password|connectionstring", name, re.IGNORECASE), name


def test_deploy_identity_container_apps_role_is_on_the_apps_and_environment_only(
    compiled: CompiledTemplate,
) -> None:
    contributor_assignments = [
        a
        for a in compiled.of_type("Microsoft.Authorization/roleAssignments")
        if "deploy-identity" in a.module and CONTAINER_APPS_CONTRIBUTOR in str(a.body)
    ]

    # One assignment per app (a copy loop over the app names) and one on the environment, where the
    # role amounts to read and join, which ARM checks on every revision update. Never the group.
    app_scoped = [
        a
        for a in contributor_assignments
        if "Microsoft.App/containerApps'" in str(a.body.get("scope"))
    ]
    environment_scoped = [
        a
        for a in contributor_assignments
        if "Microsoft.App/managedEnvironments'" in str(a.body.get("scope"))
    ]
    assert len(contributor_assignments) == len(app_scoped) + len(environment_scoped)
    assert len(environment_scoped) == 1
    (app_loop,) = app_scoped
    assert "containerAppNames" in str(app_loop.body.get("copy"))


# Allowed scopes of each role, by resource type in the assignment's `scope` (None: resource group).
EXPECTED_ROLE_SCOPES: dict[str, tuple[str, ...] | None] = {
    ACR_PULL: ("Microsoft.ContainerRegistry/registries'",),
    ACR_PUSH: ("Microsoft.ContainerRegistry/registries'",),
    CONTAINER_APPS_CONTRIBUTOR: (
        "Microsoft.App/containerApps'",
        "Microsoft.App/managedEnvironments'",
    ),
    MANAGED_IDENTITY_OPERATOR: ("Microsoft.ManagedIdentity/userAssignedIdentities'",),
    AZURE_AI_USER: ("Microsoft.CognitiveServices/accounts'",),
    # On the ledger's and the records' containers, never the account.
    STORAGE_BLOB_DATA_CONTRIBUTOR: ("Microsoft.Storage/storageAccounts/blobServices/containers'",),
    # On the one signing key, never the vault.
    KEY_VAULT_CRYPTO_USER: ("Microsoft.KeyVault/vaults/keys'",),
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
            assert any(allowed in str(scope) for allowed in expected), (role, scope)


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


# --- Microsoft Foundry ------------------------------------------------------------------------


def test_foundry_is_keyless(compiled: CompiledTemplate) -> None:
    (account,) = compiled.of_type("Microsoft.CognitiveServices/accounts")

    assert account.body["kind"] == "AIServices"
    assert account.properties["disableLocalAuth"] is True


def test_models_are_pay_per_token_and_never_upgrade_themselves(compiled: CompiledTemplate) -> None:
    (deployments,) = compiled.of_type("Microsoft.CognitiveServices/accounts/deployments")
    (module,) = [m for m in compiled.modules if m.name == "foundry"]
    declared = module.parameters["deployments"]

    assert deployments.body["sku"]["name"] == "GlobalStandard"
    assert deployments.properties["versionUpgradeOption"] == "NoAutoUpgrade"
    assert {d["name"] for d in declared} == {"fast", "fallback"}
    assert all(d["version"] for d in declared)
    # Capacity is a rate limit, not a reservation, but keep it modest.
    assert sum(d["capacity"] for d in declared) <= 200


def test_agents_identity_can_only_use_models(compiled: CompiledTemplate) -> None:
    roles = {
        GUID.findall(str(a.properties["roleDefinitionId"]))[0]
        for a in compiled.of_type("Microsoft.Authorization/roleAssignments")
        if "foundry" in a.module
    }

    assert roles == {AZURE_AI_USER}


def test_the_api_runs_as_one_replica_so_its_spend_guards_hold(compiled: CompiledTemplate) -> None:
    (api,) = [m for m in compiled.modules if m.name == "api"]

    assert api.parameters["maxReplicas"] == 1


# --- Storage and the Analyst's wiring ---------------------------------------------------------


def _env(compiled: CompiledTemplate, module: str) -> dict[str, str]:
    (app,) = [m for m in compiled.modules if m.name == module]
    return {e["name"]: str(e["value"]) for e in app.parameters.get("env", [])}


def test_storage_is_keyless_private_and_locally_redundant(compiled: CompiledTemplate) -> None:
    (account,) = compiled.of_type("Microsoft.Storage/storageAccounts")

    assert account.body["sku"]["name"] == "Standard_LRS"
    assert account.properties["allowSharedKeyAccess"] is False
    assert account.properties["allowBlobPublicAccess"] is False
    assert account.properties["defaultToOAuthAuthentication"] is True
    assert account.properties["minimumTlsVersion"] == "TLS1_2"
    assert account.properties["supportsHttpsTrafficOnly"] is True
    containers = compiled.of_type("Microsoft.Storage/storageAccounts/blobServices/containers")
    assert len(containers) == 2  # the start ledger, and the provenance records
    assert {c.properties["publicAccess"] for c in containers} == {"None"}


def test_only_the_api_identity_writes_the_ledger_and_the_records(
    compiled: CompiledTemplate,
) -> None:
    grants = [
        a
        for a in compiled.of_type("Microsoft.Authorization/roleAssignments")
        if STORAGE_BLOB_DATA_CONTRIBUTOR in str(a.properties["roleDefinitionId"])
    ]

    # One grant per container, each scoped to its container, never to the account: the ledger to
    # the agents identity, the records to the signer identity.
    assert len(grants) == 2
    principals = {str(g.properties["principalId"]) for g in grants}
    assert any("writerPrincipalId" in p for p in principals)
    assert any("recordsWriterPrincipalId" in p for p in principals)
    for grant in grants:
        assert "storage" in grant.module
        assert "containers" in str(grant.body.get("scope", ""))
    (storage_module,) = [m for m in compiled.modules if m.name == "storage"]
    assert "signerPrincipalId" in str(storage_module.parameters["recordsWriterPrincipalId"])
    (storage,) = [m for m in compiled.modules if m.name == "storage"]
    assert "agentsIdentityPrincipalId" in str(storage.parameters["writerPrincipalId"])


def test_match_data_is_reachable_only_inside_the_environment(compiled: CompiledTemplate) -> None:
    external = {
        m.parameters["serviceName"]: m.parameters.get("external", True)
        for m in compiled.modules
        if "serviceName" in m.parameters
    }

    assert external == {"api": True, "web": True, "match-data": False}


def test_the_api_runs_the_analyst_with_a_durable_ledger_and_a_small_daily_allowance(
    compiled: CompiledTemplate,
) -> None:
    env = _env(compiled, "api")

    assert set(env) == {
        "FOUNDRY_PROJECT_ENDPOINT",
        "MATCH_DATA_URL",
        "AZURE_CLIENT_ID",
        "START_LEDGER_URL",
        "MATCHDAY_RUNS_PER_DAY",
        "PROVENANCE_KEY_ID",
        "PROVENANCE_CONTAINER_URL",
        "PROVENANCE_CLIENT_ID",
    }
    assert env["MATCHDAY_RUNS_PER_DAY"] == "6"
    assert ".internal." in env["MATCH_DATA_URL"]
    assert "/mcp" in env["MATCH_DATA_URL"]
    (api,) = [m for m in compiled.modules if m.name == "api"]
    assert "agentsIdentityId" in str(api.parameters["additionalIdentityIds"])


def test_the_web_app_reaches_the_api_through_its_own_proxy(compiled: CompiledTemplate) -> None:
    assert set(_env(compiled, "web")) == {"API_URL"}


def test_match_data_accepts_only_its_internal_host(compiled: CompiledTemplate) -> None:
    env = _env(compiled, "match-data")

    assert set(env) == {"MATCH_DATA_ALLOWED_HOSTS"}
    assert ".internal." in env["MATCH_DATA_ALLOWED_HOSTS"]


def test_the_deploy_identity_may_assign_exactly_the_identities_the_apps_run_as(
    compiled: CompiledTemplate,
) -> None:
    grants = [
        a
        for a in compiled.of_type("Microsoft.Authorization/roleAssignments")
        if MANAGED_IDENTITY_OPERATOR in str(a.properties["roleDefinitionId"])
    ]
    (deploy,) = [m for m in compiled.modules if m.name == "deploy-identity"]

    assert len(grants) == 3
    assert {"appIdentityName", "agentsIdentityName", "signerIdentityName"} <= set(deploy.parameters)


def test_the_ledger_survives_a_bad_write_or_delete(compiled: CompiledTemplate) -> None:
    (blobs,) = compiled.of_type("Microsoft.Storage/storageAccounts/blobServices")

    assert blobs.properties["isVersioningEnabled"] is True
    assert blobs.properties["deleteRetentionPolicy"] == {"enabled": True, "days": 7}
    assert blobs.properties["containerDeleteRetentionPolicy"] == {"enabled": True, "days": 7}


# --- Provenance -------------------------------------------------------------------------------


def test_the_signing_key_lives_in_a_standard_rbac_vault(compiled: CompiledTemplate) -> None:
    (vault,) = compiled.of_type("Microsoft.KeyVault/vaults")

    assert vault.properties["sku"]["name"] == "standard"
    assert vault.properties["enableRbacAuthorization"] is True
    assert vault.properties.get("accessPolicies", []) == []
    assert vault.properties["enableSoftDelete"] is True
    # Nobody can delete and purge the key that every record's signature depends on.
    assert vault.properties["enablePurgeProtection"] is True


def test_the_signing_key_is_ec_p256_and_can_only_sign_and_verify(
    compiled: CompiledTemplate,
) -> None:
    (key,) = compiled.of_type("Microsoft.KeyVault/vaults/keys")

    assert key.properties["kty"] == "EC"
    assert key.properties["curveName"] == "P-256"
    assert sorted(key.properties["keyOps"]) == ["sign", "verify"]


def test_only_the_api_identity_uses_the_key_and_only_that_key(compiled: CompiledTemplate) -> None:
    (grant,) = [
        a
        for a in compiled.of_type("Microsoft.Authorization/roleAssignments")
        if KEY_VAULT_CRYPTO_USER in str(a.properties["roleDefinitionId"])
    ]

    assert "keys" in str(grant.body.get("scope", ""))
    # A signer identity of its own: not the one that talks to the models.
    assert "signerIdentityName" in str(grant.properties["principalId"])
    (api,) = [m for m in compiled.modules if m.name == "api"]
    assert "signerIdentityId" in str(api.parameters["additionalIdentityIds"])
    env = _env(compiled, "api")
    assert "signerClientId" in env["PROVENANCE_CLIENT_ID"]
    assert "keyUriWithVersion" in env["PROVENANCE_KEY_ID"]
