"""Cross-file contracts: azure.yaml, the Bicep, the provision hook and the deploy workflow agree."""

import re
from pathlib import Path

import yaml
from arm import CompiledTemplate

REPO = Path(__file__).resolve().parents[2]
# Values azd itself supplies; everything else consumed downstream must be a template output.
AZD_PROVIDED = {"AZURE_ENV_NAME", "AZURE_SUBSCRIPTION_ID"}


def _consumed_names(path: Path, pattern: str) -> set[str]:
    names = set(re.findall(pattern, path.read_text()))
    return {n for n in names if n.startswith(("AZURE_", "SERVICE_"))} - AZD_PROVIDED


def test_every_azd_service_has_a_container_app_tagged_with_its_name(
    compiled: CompiledTemplate,
) -> None:
    services = set(yaml.safe_load((REPO / "azure.yaml").read_text())["services"])
    tagged = {
        m.parameters["serviceName"] for m in compiled.modules if "serviceName" in m.parameters
    }

    assert services == tagged


def _hook_reads(hook: str) -> set[str]:
    referenced = set(re.findall(r"\$\{?([A-Z][A-Z0-9_]+)", hook))
    published = re.search(r"GITHUB_VARIABLES=\"([^\"]+)\"", hook)
    assert published, "hook must list the variables it publishes in GITHUB_VARIABLES"
    names = referenced | set(published.group(1).split())
    return {n for n in names if n.startswith(("AZURE_", "SERVICE_"))} - AZD_PROVIDED


def test_provision_hook_reads_only_template_outputs(compiled: CompiledTemplate) -> None:
    consumed = _hook_reads((REPO / "infra/hooks/postprovision.sh").read_text())

    assert consumed
    assert consumed <= set(compiled.template["outputs"])


def test_deploy_workflow_reads_only_what_the_hook_publishes() -> None:
    hook = (REPO / "infra/hooks/postprovision.sh").read_text()
    workflow = (REPO / ".github/workflows/deploy.yml").read_text()
    listed = re.search(r'GITHUB_VARIABLES="([^"]+)"', hook)
    assert listed, "hook must list the variables it publishes in GITHUB_VARIABLES"
    published_vars = set(listed.group(1).split())
    published_secrets = set(re.findall(r"gh secret set ([A-Z0-9_]+)", hook))

    read_vars = set(re.findall(r"vars\.([A-Z0-9_]+)", workflow))
    read_secrets = set(re.findall(r"secrets\.([A-Z0-9_]+)", workflow))

    assert read_vars
    assert read_secrets
    assert read_vars <= published_vars
    assert read_secrets <= published_secrets


def test_main_parameters_read_the_prefix_the_preprovision_hook_writes() -> None:
    parameters = (REPO / "infra/main.parameters.json").read_text()

    assert "${GITHUB_DEPLOY_SUBJECT_PREFIX=}" in parameters


def test_api_image_copies_every_workspace_manifest() -> None:
    # uv validates the whole workspace lockfile, so the image needs every member's pyproject.
    import tomllib

    members = tomllib.loads((REPO / "pyproject.toml").read_text())["tool"]["uv"]["workspace"][
        "members"
    ]
    dockerfile = (REPO / "apps/api/Dockerfile").read_text()

    for member in members:
        assert f"COPY {member}/pyproject.toml {member}/pyproject.toml" in dockerfile, member
