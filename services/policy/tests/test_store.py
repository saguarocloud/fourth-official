"""Partner policies are versioned files: loaded strictly, explained when wrong, fingerprinted."""

import hashlib
from pathlib import Path

import pytest

from fourth_official_policy import FilePolicyStore, PolicyError, bundled_store

BUNDLED = Path(__file__).parents[1] / "src/fourth_official_policy/policies"
PARTNERS = ("northlight-sport", "tribuna-austral", "rheinblick-sport")
NORTHLIGHT = (BUNDLED / "northlight-sport.yaml").read_text(encoding="utf-8")


def write(directory: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        (directory / name).write_text(text, encoding="utf-8")
    return directory


def full_set(tmp_path: Path, **override: str) -> FilePolicyStore:
    """Every partner's bundled policy, with the files named in `override` replaced."""
    files = {f"{p}.yaml": (BUNDLED / f"{p}.yaml").read_text(encoding="utf-8") for p in PARTNERS}
    files |= {f"{name}.yaml": text for name, text in override.items()}
    return FilePolicyStore(write(tmp_path, files))


def test_the_three_partners_ship_with_valid_policies() -> None:
    store = bundled_store()

    assert {p.policy.tenant_id: p.policy.locale for p in store.all()} == {
        "northlight-sport": "en-GB",
        "rheinblick-sport": "de-DE",
        "tribuna-austral": "es-MX",
    }


def test_a_policy_is_found_by_partner_with_its_file_fingerprint(tmp_path: Path) -> None:
    store = full_set(tmp_path)

    loaded = store.get("northlight-sport")

    assert loaded.policy.locale == "en-GB"
    assert loaded.sha256 == hashlib.sha256(NORTHLIGHT.encode()).hexdigest()


def test_an_unknown_partner_has_no_policy(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        full_set(tmp_path).get("evil-sport")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("text", "explanation"),
    [
        (NORTHLIGHT.replace("locale: en-GB", "locale: fr-FR"), "locale"),
        (NORTHLIGHT.replace("version: 1", "version: zero"), "version"),
        (NORTHLIGHT + "autoPublish: true\n", "autoPublish"),
        ("tenantId: [unclosed", "not valid YAML"),
        ("- just\n- a list\n", "a mapping"),
        ("!!python/object/apply:os.system ['echo pwned']\n", "not valid YAML"),
    ],
)
def test_an_invalid_policy_is_refused_with_a_readable_reason(
    tmp_path: Path, text: str, explanation: str
) -> None:
    with pytest.raises(PolicyError, match=explanation) as refused:
        full_set(tmp_path, **{"northlight-sport": text})

    assert "northlight-sport.yaml" in str(refused.value)


def test_a_file_must_be_named_for_its_partner(tmp_path: Path) -> None:
    with pytest.raises(PolicyError, match="named for its partner"):
        full_set(tmp_path, **{"tribuna-austral": NORTHLIGHT})


def test_every_partner_must_have_a_policy(tmp_path: Path) -> None:
    write(tmp_path, {"northlight-sport.yaml": NORTHLIGHT})

    with pytest.raises(PolicyError, match="rheinblick-sport, tribuna-austral"):
        FilePolicyStore(tmp_path)


def test_an_empty_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(PolicyError, match="no policy"):
        FilePolicyStore(tmp_path)


def test_other_files_in_the_directory_are_refused_not_ignored(tmp_path: Path) -> None:
    (tmp_path / "tribuna-austral.yml").write_text(NORTHLIGHT, encoding="utf-8")

    with pytest.raises(PolicyError, match=r"\.yml"):
        full_set(tmp_path)


def test_a_repeated_key_is_refused_not_overridden(tmp_path: Path) -> None:
    repeated = NORTHLIGHT + "blockedTopics: []\n"

    with pytest.raises(PolicyError, match="repeats the key blockedTopics"):
        full_set(tmp_path, **{"northlight-sport": repeated})


def test_aliases_are_refused(tmp_path: Path) -> None:
    aliased = NORTHLIGHT.replace("tone: [measured, analytical]", "tone: &t [measured]").replace(
        "preferTerms: [pressing, transition, chance]", "preferTerms: *t"
    )

    with pytest.raises(PolicyError, match="aliases"):
        full_set(tmp_path, **{"northlight-sport": aliased})


def test_an_oversized_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(PolicyError, match="larger than"):
        full_set(tmp_path, **{"northlight-sport": NORTHLIGHT + "#" * 70_000})


def test_a_symlink_is_refused(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "policy.yaml").write_text(NORTHLIGHT, encoding="utf-8")
    store = tmp_path / "store"
    store.mkdir()
    (store / "northlight-sport.yaml").symlink_to(elsewhere / "policy.yaml")

    with pytest.raises(PolicyError, match="regular file"):
        FilePolicyStore(store)


def test_a_yaml_error_names_its_line(tmp_path: Path) -> None:
    with pytest.raises(PolicyError, match="line 2"):
        full_set(tmp_path, **{"northlight-sport": "tenantId: x\nversion: 1: 2\n"})


def test_text_that_is_not_utf8_is_refused(tmp_path: Path) -> None:
    full_set(tmp_path)
    (tmp_path / "northlight-sport.yaml").write_bytes("locale: \xe9".encode("latin-1"))

    with pytest.raises(PolicyError, match="not valid YAML"):
        FilePolicyStore(tmp_path)
