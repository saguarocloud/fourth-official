"""The configurations the Proving Ground can run, named for the scorecard.

- `template`: the deterministic templates alone, free; it tests the harness itself.
- `production`: exactly what the API runs (`fourth_official_explain.production`). In CI, a pull
  request's own production configuration is the candidate the Release Gate judges.
- `candidate`: production with the Analyst's v1.4 prompt, kept deliberately worse, so the gate
  can be shown blocking a change (plan §9.3).
"""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager
from dataclasses import dataclass

from azure.identity.aio import DefaultAzureCredential

from fourth_official_contracts import Configuration, Moment
from fourth_official_explain import Explanation, explain
from fourth_official_explain.analyst import Meter
from fourth_official_explain.production import ANALYST, MODELS, analyst_drafters
from fourth_official_match_data import MatchStore
from fourth_official_proving.models import match_data_server, project_endpoint
from fourth_official_proving.runner import Explainer
from fourth_official_verifier import MatchFacts

CANDIDATE = ("analyst", "v1.4")
# Partners localise by template in every configuration: the Proving Ground judges the Analyst.
LOCALIZED_BY = "template"

Opener = Callable[[MatchStore, Meter], AbstractAsyncContextManager[Explainer]]


async def _template(moment: Moment, facts: MatchFacts) -> Explanation:
    return await explain(moment, facts, [])


@asynccontextmanager
async def _templates(store: MatchStore, meter: Meter) -> AsyncIterator[Explainer]:
    yield _template


def _with_models(prompt: tuple[str, str]) -> Opener:
    @asynccontextmanager
    async def open_models(store: MatchStore, meter: Meter) -> AsyncIterator[Explainer]:
        endpoint = project_endpoint()
        async with AsyncExitStack() as stack:
            url = await stack.enter_async_context(match_data_server(store))
            credential = await stack.enter_async_context(DefaultAzureCredential())
            drafters = analyst_drafters(
                project_endpoint=endpoint,
                match_data_url=url,
                credential=credential,
                prompt=prompt,
                meter=meter,
            )
            for drafter in drafters:
                await stack.enter_async_context(drafter)

            async def explainer(moment: Moment, facts: MatchFacts) -> Explanation:
                return await explain(moment, facts, drafters)

            yield explainer

    return open_models


@dataclass(frozen=True, slots=True)
class Runnable:
    configuration: Configuration
    open: Opener

    @property
    def uses_models(self) -> bool:
        return bool(self.configuration.models)


def _model_configuration(name: str, prompt: tuple[str, str]) -> Runnable:
    return Runnable(
        configuration=Configuration(
            name=name,
            analyst_prompt="/".join(prompt),
            localizer_prompt=LOCALIZED_BY,
            models=tuple(alias for alias, _ in MODELS),
        ),
        open=_with_models(prompt),
    )


TEMPLATE = Runnable(
    configuration=Configuration(
        name="template", analyst_prompt="template", localizer_prompt=LOCALIZED_BY, models=()
    ),
    open=_templates,
)

CONFIGURATIONS: dict[str, Runnable] = {
    runnable.configuration.name: runnable
    for runnable in (
        TEMPLATE,
        _model_configuration("production", ANALYST),
        _model_configuration("candidate", CANDIDATE),
    )
}
