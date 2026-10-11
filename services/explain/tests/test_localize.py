"""Localising a verified insight for a partner: the model rewrites words, code keeps the facts,
the Verifier decides, and the partner's template stands in when nothing else passes."""

from dataclasses import dataclass, field

import anyio
import pytest

from fourth_official_contracts import (
    Insight,
    LocalizedInsight,
    Provenance,
    TenantPolicy,
    parse_insight,
    parse_tenant_policy,
)
from fourth_official_explain.localize import (
    Localization,
    LocalizationRequest,
    LocalizedClaimDraft,
    LocalizedDraft,
    localize,
    to_localized,
)
from verifier_fixtures import FACTS, GOAL_MOMENT, POSSESSION, insight_wire

CANONICAL: Insight = parse_insight(insight_wire())
VALUE = "{{value:" + POSSESSION.snapshot_id + "}}"
LOCALIZER = Provenance(agent="localizer", prompt_version="v1.0", model="fast", produced_by="model")


def policy(tenant: str, locale: str, **changes: object) -> TenantPolicy:
    return parse_tenant_policy(
        {
            "tenantId": tenant,
            "version": 2,
            "displayName": tenant.replace("-", " ").title(),
            "locale": locale,
            "tone": ["energetic"],
            "preferTerms": [],
            "avoidTerms": [],
            "blockedTopics": ["betting"],
            "approvalRequired": [],
            "disclosureMode": "label-all",
            "latencyBudgetMs": 8000,
            "maxItemsPerMinute": 6,
            "templates": ["lower_third", "correction_strap"],
            "correctionBehaviour": "auto-amend",
            "dutyEditor": "R. Hale",
            **changes,
        }
    )


TRIBUNA = policy("tribuna-austral", "es-MX")
NORTHLIGHT = policy("northlight-sport", "en-GB")

GOOD = LocalizedDraft(
    headline="Gol de {{club:HCY}}",
    claims=[
        LocalizedClaimDraft(
            claim_id="cl-1",
            text="{{player:HCY-09}} adelanta a {{club:HCY}} en el {{minute:12}}: {{score}}.",
        ),
        LocalizedClaimDraft(claim_id="cl-2", text=f"{{{{club:HCY}}}} tiene el {VALUE} del balón."),
    ],
)
ADDS_A_FACT = GOOD.model_copy(
    update={
        "claims": [
            LocalizedClaimDraft(
                claim_id="cl-1",
                text="{{player:HCY-09}} y {{player:HCY-04}} adelantan a {{club:HCY}}: {{score}}.",
            ),
            GOOD.claims[1],
        ]
    }
)


@dataclass
class Scripted:
    """A localizer that answers from a script and remembers what it was asked."""

    answers: list[LocalizedDraft | Exception]
    requests: list[LocalizationRequest] = field(default_factory=list)
    provenance: Provenance = LOCALIZER

    async def draft(self, request: LocalizationRequest) -> LocalizedDraft:
        self.requests.append(request)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def run(
    target: TenantPolicy, localizer: Scripted | None, blocked: tuple[str, ...] = ()
) -> Localization:
    return anyio.run(
        lambda: localize(
            CANONICAL,
            GOAL_MOMENT,
            FACTS,
            target,
            localizer=localizer,
            blocked=lambda text: [w for w in blocked if w in text],
        )
    )


def aired(result: Localization) -> LocalizedInsight:
    assert result.localized is not None, result.attempts
    return result.localized


def test_code_copies_types_and_evidence_from_the_canonical_insight() -> None:
    localized = to_localized(GOOD, CANONICAL, policy=TRIBUNA, provenance=LOCALIZER, version=1)

    assert localized.locale == "es-MX"
    assert [c.evidence for c in localized.claims] == [c.evidence for c in CANONICAL.claims]
    assert [c.type for c in localized.claims] == [c.type for c in CANONICAL.claims]
    assert localized.item_id == f"it-tribuna-austral-{CANONICAL.insight_id}-v1"
    assert localized.policy_version == 2


def test_a_passing_draft_airs_as_written() -> None:
    result = run(TRIBUNA, Scripted([GOOD]))

    assert aired(result).headline == "Gol de {{club:HCY}}"
    assert result.verdict.passed
    assert [(a.model, a.outcome) for a in result.attempts] == [("fast", "passed")]


def test_a_refused_draft_is_retried_with_itself_and_the_findings() -> None:
    localizer = Scripted([ADDS_A_FACT, GOOD])

    result = run(TRIBUNA, localizer)

    assert [a.outcome for a in result.attempts] == ["failed", "passed"]
    retry = localizer.requests[1]
    assert retry.previous == ADDS_A_FACT
    assert "REFERENCES_CHANGED" in [f.code for f in retry.feedback]
    assert retry.policy == TRIBUNA


def test_after_its_retry_the_partner_s_template_stands_in() -> None:
    result = run(TRIBUNA, Scripted([ADDS_A_FACT, ADDS_A_FACT]))

    assert aired(result).provenance.produced_by == "template"
    assert aired(result).headline == "Gol de {{club:HCY}}"
    assert result.verdict.passed
    assert [a.model for a in result.attempts] == ["fast", "fast", "none"]


def test_a_draft_with_other_claims_is_malformed() -> None:
    other_claims = GOOD.model_copy(update={"claims": [GOOD.claims[0]]})

    result = run(TRIBUNA, Scripted([other_claims, GOOD]))

    assert result.attempts[0].findings == ("MALFORMED_INSIGHT",)
    assert result.verdict.passed


def test_a_model_failure_goes_straight_to_the_template() -> None:
    result = run(TRIBUNA, Scripted([TimeoutError("slow")]))

    assert [(a.outcome, a.error) for a in result.attempts[:1]] == [("error", "TimeoutError")]
    assert aired(result).provenance.produced_by == "template"


def test_without_a_model_the_template_is_used() -> None:
    result = run(TRIBUNA, None)

    assert aired(result).provenance.produced_by == "template"
    assert [a.model for a in result.attempts] == ["none"]


def test_an_english_partner_airs_the_canonical_words_without_a_model() -> None:
    result = run(NORTHLIGHT, Scripted([]))

    assert aired(result).headline == CANONICAL.headline
    assert [c.text for c in aired(result).claims] == [c.text for c in CANONICAL.claims]
    assert aired(result).provenance == CANONICAL.provenance


def test_an_english_partner_gets_its_template_when_the_canonical_breaks_its_policy() -> None:
    result = run(NORTHLIGHT, Scripted([]), blocked=("ball",))

    assert aired(result).provenance.produced_by == "template"


def test_a_blocked_topic_in_a_draft_costs_a_retry() -> None:
    result = run(TRIBUNA, Scripted([GOOD, GOOD]), blocked=("balón",))

    assert result.attempts[0].findings == ("BLOCKED_TOPIC",)
    assert aired(result).provenance.produced_by == "template"


# --- Review round -----------------------------------------------------------------------------


def test_an_english_partner_s_check_is_recorded() -> None:
    result = run(NORTHLIGHT, Scripted([]))

    assert [(a.agent, a.model, a.outcome) for a in result.attempts] == [
        ("localizer", "none", "passed")
    ]


def test_an_english_partner_s_failed_check_is_recorded_before_the_template() -> None:
    result = run(NORTHLIGHT, Scripted([]), blocked=("ball",))

    assert [(a.number, a.model, a.outcome) for a in result.attempts] == [
        (1, "none", "failed"),
        (2, "none", "passed"),
    ]
    assert result.attempts[0].findings == ("BLOCKED_TOPIC",)


def test_a_timeout_is_retried_once() -> None:
    result = run(TRIBUNA, Scripted([TimeoutError("slow"), GOOD]))

    assert [(a.outcome, a.error) for a in result.attempts] == [
        ("error", "TimeoutError"),
        ("passed", None),
    ]


def test_a_bug_in_our_code_is_never_hidden_behind_a_template() -> None:
    with pytest.raises(TypeError):
        run(TRIBUNA, Scripted([TypeError("bug")]))


def test_attempts_are_numbered_through_errors_to_the_template() -> None:
    result = run(TRIBUNA, Scripted([ADDS_A_FACT, RuntimeError("down")]))

    assert [(a.number, a.outcome) for a in result.attempts] == [
        (1, "failed"),
        (2, "error"),
        (3, "passed"),
    ]


def test_a_draft_that_breaks_the_contract_is_malformed() -> None:
    empty = GOOD.model_copy(
        update={"claims": [LocalizedClaimDraft(claim_id="cl-1", text=""), GOOD.claims[1]]}
    )

    result = run(TRIBUNA, Scripted([empty, GOOD]))

    assert result.attempts[0].findings == ("MALFORMED_INSIGHT",)


def test_nothing_airs_when_even_the_template_breaks_the_partner_s_policy() -> None:
    result = run(TRIBUNA, None, blocked=("Gol",))

    assert result.localized is None
    assert result.attempts[-1].outcome == "failed"


def test_a_first_version_is_numbered_one() -> None:
    localized = aired(run(TRIBUNA, Scripted([GOOD])))

    assert localized.version == 1
    assert localized.item_id.endswith("-v1")
