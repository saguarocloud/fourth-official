"""Compile Bicep to ARM JSON and walk every resource it declares, modules included."""

import json
import shutil
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class Resource:
    """A resource from the compiled template, with the module path that declared it."""

    type: str
    body: JsonObject
    module: str

    @property
    def properties(self) -> JsonObject:
        props: JsonObject = self.body.get("properties", {})
        return props


@dataclass(frozen=True, slots=True)
class CompiledTemplate:
    template: JsonObject
    resources: tuple[Resource, ...]

    def of_type(self, resource_type: str) -> list[Resource]:
        return [r for r in self.resources if r.type.lower() == resource_type.lower()]

    def text(self) -> str:
        return json.dumps(self.template)


def _resources_of(template: JsonObject) -> list[JsonObject]:
    declared = template.get("resources", [])
    # languageVersion 2.0 templates use a symbolic-name dictionary instead of a list.
    return list(declared.values()) if isinstance(declared, dict) else list(declared)


def _walk(template: JsonObject, module: str) -> Iterator[Resource]:
    for body in _resources_of(template):
        resource_type = body["type"]
        if resource_type == "Microsoft.Resources/deployments":
            nested = body.get("properties", {}).get("template", {})
            yield from _walk(nested, f"{module}/{body.get('name', '?')}")
        else:
            yield Resource(type=resource_type, body=body, module=module)


def compile_bicep(path: Path) -> JsonObject:
    if shutil.which("az") is None:
        raise RuntimeError("The Azure CLI (az) is required to compile Bicep")
    result = subprocess.run(  # noqa: S603 - fixed arguments, no user input
        ["az", "bicep", "build", "--file", str(path), "--stdout"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Bicep compilation failed:\n{result.stderr}")
    compiled: JsonObject = json.loads(result.stdout)
    return compiled


def load_template(path: Path) -> CompiledTemplate:
    """Compile a Bicep file and index all of its resources."""
    template = compile_bicep(path)
    return CompiledTemplate(template=template, resources=tuple(_walk(template, "main")))
