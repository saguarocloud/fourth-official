"""Behavioural tests for the azd hooks, run as real processes with stubbed `gh`, `az` and `azd`."""

import json
import os
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[1] / "hooks"
REPOSITORY = "saguarocloud/fourth-official"
GOOD_PREFIX = "repo:saguarocloud@217376236/fourth-official@1413964965"


@dataclass(frozen=True, slots=True)
class HookRun:
    returncode: int
    output: str
    azd_calls: list[str]
    gh_calls: list[str]


def _stub(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def stubs(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # gh: records its arguments, then prints GH_STUB_OUTPUT or fails with GH_STUB_EXIT.
    _stub(
        bin_dir,
        "gh",
        'echo "$*" >> "$STUB_LOG.gh"\n'
        '[ "${GH_STUB_EXIT:-0}" = "0" ] || { echo "HTTP 403" >&2; exit "$GH_STUB_EXIT"; }\n'
        'printf "%s" "$GH_STUB_OUTPUT"',
    )
    _stub(bin_dir, "azd", 'echo "$*" >> "$STUB_LOG.azd"')
    _stub(bin_dir, "az", "echo false")
    return bin_dir


def _run(hook: str, stubs: Path, env: dict[str, str]) -> HookRun:
    log = stubs.parent / "calls"
    result = subprocess.run(  # noqa: S603 - fixed script path from this repository
        ["/bin/sh", str(HOOKS / hook)],
        env={
            "PATH": f"{stubs}:{os.environ['PATH']}",
            "STUB_LOG": str(log),
            "AZURE_SUBSCRIPTION_ID": "00000000-0000-0000-0000-000000000000",
            **env,
        },
        capture_output=True,
        text=True,
        check=False,
    )
    return HookRun(
        result.returncode,
        result.stdout + result.stderr,
        _calls(log, "azd"),
        _calls(log, "gh"),
    )


def _calls(log: Path, tool: str) -> list[str]:
    path = Path(f"{log}.{tool}")
    return path.read_text().splitlines() if path.exists() else []


def _oidc(prefix: str | None, *, use_default: bool = True) -> str:
    return json.dumps({"use_default": use_default, "sub_claim_prefix": prefix})


def test_preprovision_records_the_subject_prefix_github_reports(stubs: Path) -> None:
    run = _run(
        "preprovision.sh",
        stubs,
        {"GITHUB_DEPLOY_REPOSITORY": REPOSITORY, "GH_STUB_OUTPUT": _oidc(GOOD_PREFIX)},
    )

    assert run.returncode == 0, run.output
    assert f"env set GITHUB_DEPLOY_SUBJECT_PREFIX {GOOD_PREFIX}" in run.azd_calls
    assert run.gh_calls == [f"api repos/{REPOSITORY}/actions/oidc/customization/sub"]


def test_preprovision_accepts_name_based_subjects(stubs: Path) -> None:
    run = _run(
        "preprovision.sh",
        stubs,
        {"GITHUB_DEPLOY_REPOSITORY": REPOSITORY, "GH_STUB_OUTPUT": _oidc(f"repo:{REPOSITORY}")},
    )

    assert run.returncode == 0, run.output
    assert f"env set GITHUB_DEPLOY_SUBJECT_PREFIX repo:{REPOSITORY}" in run.azd_calls


@pytest.mark.parametrize(
    "prefix",
    [
        None,
        "",
        "repo:someone-else@1/fourth-official@2",
        "repo:saguarocloud/other-repo",
        f"{GOOD_PREFIX}:environment:prod",
        f"{GOOD_PREFIX}\nrepo:attacker/x",
        "*",
    ],
)
def test_preprovision_rejects_a_prefix_for_any_other_repository(
    stubs: Path, prefix: str | None
) -> None:
    run = _run(
        "preprovision.sh",
        stubs,
        {"GITHUB_DEPLOY_REPOSITORY": REPOSITORY, "GH_STUB_OUTPUT": _oidc(prefix)},
    )

    assert run.returncode != 0
    assert not any("GITHUB_DEPLOY_SUBJECT_PREFIX" in call for call in run.azd_calls)


def test_preprovision_refuses_custom_subject_templates(stubs: Path) -> None:
    run = _run(
        "preprovision.sh",
        stubs,
        {
            "GITHUB_DEPLOY_REPOSITORY": REPOSITORY,
            "GH_STUB_OUTPUT": _oidc(GOOD_PREFIX, use_default=False),
        },
    )

    assert run.returncode != 0
    assert "custom OIDC subject" in run.output


def test_preprovision_explains_how_to_recover_when_github_is_unreachable(stubs: Path) -> None:
    run = _run(
        "preprovision.sh", stubs, {"GITHUB_DEPLOY_REPOSITORY": REPOSITORY, "GH_STUB_EXIT": "1"}
    )

    assert run.returncode != 0
    assert "gh auth login" in run.output


def test_preprovision_skips_github_entirely_without_a_deploy_repository(stubs: Path) -> None:
    run = _run("preprovision.sh", stubs, {})

    assert run.returncode == 0, run.output
    assert run.gh_calls == []
    assert "env set SERVICE_API_RESOURCE_EXISTS false" in run.azd_calls


def test_postprovision_fails_when_a_deploy_repository_got_no_identity(stubs: Path) -> None:
    run = _run(
        "postprovision.sh",
        stubs,
        {"GITHUB_DEPLOY_REPOSITORY": REPOSITORY, "AZURE_DEPLOY_CLIENT_ID": ""},
    )

    assert run.returncode != 0
    assert "no deploy identity" in run.output


def test_postprovision_skips_github_when_no_deploy_repository_is_set(stubs: Path) -> None:
    run = _run("postprovision.sh", stubs, {})

    assert run.returncode == 0, run.output
    assert run.gh_calls == []


def test_preprovision_matches_repository_names_case_insensitively(stubs: Path) -> None:
    # GitHub owner and repository names are case-insensitive; the API returns canonical casing.
    run = _run(
        "preprovision.sh",
        stubs,
        {
            "GITHUB_DEPLOY_REPOSITORY": "SaguaroCloud/Fourth-Official",
            "GH_STUB_OUTPUT": _oidc(GOOD_PREFIX),
        },
    )

    assert run.returncode == 0, run.output
