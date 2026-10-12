"""The configurations the Proving Ground can run: what writes the insights, named for the
scorecard. A configuration that drafts with models is added where its credentials are."""

from collections.abc import Callable
from dataclasses import dataclass

from fourth_official_contracts import Configuration, Moment
from fourth_official_explain import Explanation, explain
from fourth_official_proving.runner import Explainer
from fourth_official_verifier import MatchFacts


async def _template(moment: Moment, facts: MatchFacts) -> Explanation:
    return await explain(moment, facts, [])


@dataclass(frozen=True, slots=True)
class Runnable:
    configuration: Configuration
    explainer: Callable[[], Explainer]


TEMPLATE = Runnable(
    configuration=Configuration(
        name="template", analyst_prompt="template", localizer_prompt="template", models=()
    ),
    explainer=lambda: _template,
)

CONFIGURATIONS: dict[str, Runnable] = {TEMPLATE.configuration.name: TEMPLATE}
