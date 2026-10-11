"""Name pools for fictional players, and the blocklist of real footballers they must avoid."""

from importlib.resources import files


def _load(filename: str) -> tuple[str, ...]:
    text = files("fourth_official_simulator.data").joinpath(filename).read_text(encoding="utf-8")
    return tuple(
        line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")
    )


FIRST_NAMES = _load("first_names.txt")
LAST_NAMES = _load("last_names.txt")
BLOCKLIST = _load("blocklist-names.txt")
