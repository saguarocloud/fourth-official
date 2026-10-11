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


def test_deploy_workflow_reads_only_variables_the_hook_writes() -> None:
    hook = (REPO / "infra/hooks/postprovision.sh").read_text()
    workflow_vars = _consumed_names(REPO / ".github/workflows/deploy.yml", r"vars\.([A-Z0-9_]+)")

    assert workflow_vars
    for name in workflow_vars:
        assert re.search(rf"\b{name}\b", hook), f"{name} is read by deploy.yml but never written"
