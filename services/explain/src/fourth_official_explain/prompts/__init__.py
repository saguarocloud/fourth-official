"""Versioned prompts, stored as files so every change is reviewed and released like code."""

import re
from dataclasses import dataclass
from importlib.resources import files

_FRONT_MATTER = re.compile(r"^---\n(?P<meta>.*?)\n---\n(?P<body>.*)$", re.DOTALL)
_VERSION = re.compile(r"^v[0-9]{1,3}\.[0-9]{1,3}$")


@dataclass(frozen=True, slots=True)
class Prompt:
    agent: str
    version: str
    text: str


def load_prompt(agent: str, version: str) -> Prompt:
    """Load `prompts/<agent>/<version>.md` and check its front matter matches what was asked."""
    if not re.fullmatch(r"[a-z][a-z-]{1,31}", agent) or not _VERSION.match(version):
        raise ValueError("unknown prompt")
    raw = (
        files("fourth_official_explain.prompts").joinpath(agent, f"{version}.md").read_text("utf-8")
    )
    return parse_prompt(raw, agent=agent, version=version)


def parse_prompt(raw: str, *, agent: str, version: str) -> Prompt:
    """A prompt file's text, once its front matter is checked against the name it was loaded by."""
    found = _FRONT_MATTER.match(raw)
    if found is None:
        raise ValueError(f"prompt {agent}/{version} has no front matter")
    meta = dict(line.split(":", 1) for line in found.group("meta").splitlines() if ":" in line)
    meta = {k.strip(): v.strip() for k, v in meta.items()}
    if (meta.get("agent"), meta.get("version")) != (agent, version):
        raise ValueError(
            f"prompt {agent}/{version} names itself {meta.get('agent')}/{meta.get('version')}"
        )
    return Prompt(agent=agent, version=version, text=found.group("body").strip())
