"""Policies as versioned YAML files, one per partner, reviewed in pull requests like code.

A store loads every file once, strictly: an invalid file stops the service with an explanation
naming the file and the fields, rather than letting a partner run on a half-understood policy.
Each loaded policy keeps the SHA-256 of its file, so every item can record exactly what applied.
"""

import hashlib
from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Protocol, get_args

import yaml
from pydantic import ValidationError

from fourth_official_contracts import TenantId, TenantPolicy, parse_tenant_policy

MAX_POLICY_BYTES = 64 * 1024
MAX_FIELD_NAME = 40


class PolicyError(ValueError):
    """A policy file that cannot be used, with the reason in words."""


@dataclass(frozen=True, slots=True)
class LoadedPolicy:
    policy: TenantPolicy
    # Fingerprint of the file the policy came from.
    sha256: str


class PolicyStore(Protocol):
    def get(self, tenant_id: TenantId) -> LoadedPolicy: ...

    def all(self) -> tuple[LoadedPolicy, ...]: ...


class _StrictLoader(yaml.SafeLoader):
    """Plain data only, and every key once: a repeated key would silently drop a rule."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[object, object]:
        seen: set[object] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise PolicyError(f"repeats the key {key}")
            seen.add(key)
        return super().construct_mapping(node, deep=deep)

    def compose_node(self, parent: yaml.Node | None, index: object) -> yaml.Node | None:
        # Aliases can multiply a small file into a huge one; a policy never needs them.
        if self.check_event(yaml.AliasEvent):
            raise PolicyError("uses YAML aliases, which policies never need")
        return super().compose_node(parent, index)  # type: ignore[arg-type]


def _explain(name: str, error: ValidationError) -> PolicyError:
    # A field name may be the caller's own (an unknown key): shown, but never at length.
    problems = [
        f"{'.'.join(str(p)[:MAX_FIELD_NAME] for p in problem['loc']) or 'policy'}: {problem['msg']}"
        for problem in error.errors(include_input=False)
    ]
    return PolicyError(f"{name} is not a valid policy: " + "; ".join(problems[:5]))


def _parse(name: str, data: bytes) -> object:
    try:
        return yaml.load(data.decode("utf-8"), Loader=_StrictLoader)  # noqa: S506 - strict SafeLoader
    except PolicyError as error:
        raise PolicyError(f"{name} {error}") from None
    except yaml.MarkedYAMLError as error:
        mark = error.problem_mark
        where = f" at line {mark.line + 1}" if mark is not None else ""
        raise PolicyError(f"{name} is not valid YAML{where}: {error.problem}") from None
    except (yaml.YAMLError, UnicodeDecodeError) as error:
        raise PolicyError(f"{name} is not valid YAML: {type(error).__name__}") from None


def _load(name: str, data: bytes) -> LoadedPolicy:
    raw = _parse(name, data)
    if not isinstance(raw, dict):
        raise PolicyError(f"{name} must hold a mapping of policy fields")
    try:
        policy = parse_tenant_policy(raw)
    except ValidationError as error:
        raise _explain(name, error) from None
    if name != f"{policy.tenant_id}.yaml":
        raise PolicyError(f"{name} must be named for its partner: {policy.tenant_id}.yaml")
    return LoadedPolicy(policy=policy, sha256=hashlib.sha256(data).hexdigest())


def _read(entry: Path | Traversable) -> bytes:
    if isinstance(entry, Path) and (entry.is_symlink() or not entry.is_file()):
        raise PolicyError(f"{entry.name} must be a regular file")
    with entry.open("rb") as handle:
        data: bytes = handle.read(MAX_POLICY_BYTES + 1)
    if len(data) > MAX_POLICY_BYTES:
        raise PolicyError(f"{entry.name} is larger than {MAX_POLICY_BYTES} bytes")
    return data


class FilePolicyStore:
    """Every partner's `<tenant>.yaml` in a directory, loaded and checked once. The directory holds
    exactly one policy per partner and nothing else."""

    def __init__(self, directory: Path | Traversable) -> None:
        entries = sorted(directory.iterdir(), key=lambda e: e.name)
        others = [e.name for e in entries if not e.name.endswith(".yaml")]
        if others:
            raise PolicyError(f"only policy files belong here, not {', '.join(others)}")
        loaded = [_load(entry.name, _read(entry)) for entry in entries]
        if not loaded:
            raise PolicyError("no policy found: every partner needs one")
        self._policies = {item.policy.tenant_id: item for item in loaded}
        missing = sorted(set(get_args(TenantId)) - set(self._policies))
        if missing:
            raise PolicyError(f"no policy for {', '.join(missing)}")

    def get(self, tenant_id: TenantId) -> LoadedPolicy:
        return self._policies[tenant_id]

    def all(self) -> tuple[LoadedPolicy, ...]:
        return tuple(self._policies[t] for t in sorted(self._policies))


def bundled_store() -> FilePolicyStore:
    """The partners' policies shipped with this release."""
    return FilePolicyStore(files("fourth_official_policy").joinpath("policies"))
