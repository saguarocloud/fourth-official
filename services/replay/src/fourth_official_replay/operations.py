"""Operations: what a run of the matchday measured, computed by code from each match's feed and
the times its log noted (when each event was played and each entry published).

- **Event to on air**: for each partner item aired without an editor (first versions of narrative
  items), from the replay playing the last event its insight rests on to the item's publication.
  Held items wait for a person, so they are counted, not timed.
- **Explaining**: from a moment's publication to its verified insight's.
- **Corrections**: the time the corrections desk itself measured for each correction.
- **Cost**: the tokens every model attempt recorded, at the production prices, plus the match's
  share of the infrastructure for as long as it ran (docs/cost-model.md).

Durations are whole milliseconds; percentiles are nearest rank; money is whole micro-dollars. The
objectives are the plan's (Fourth Official plan, §9).
"""

import logging
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from fourth_official_contracts import (
    CorrectionReportEntry,
    ErrorBudget,
    FeedEntry,
    InsightEntry,
    MatchOperations,
    ModelPrice,
    MomentEntry,
    Objective,
    OperationsReport,
    PartnerOperations,
    Pricing,
    Spread,
    TenantId,
    TenantItemEntry,
    TokenUse,
)
from fourth_official_contracts.feed import AttemptRecord
from fourth_official_contracts.operations import MatchState
from fourth_official_contracts.scorecard import Ratio
from fourth_official_explain.metering import TokenCount
from fourth_official_explain.production import PRICES, Price, micro_dollars
from fourth_official_replay.log import RunTiming

# The deterministic template's agent name in an attempt: anything else is a model.
TEMPLATE_AGENT = "template"
MAX_MS = 3_600_000


@dataclass(frozen=True, slots=True)
class Targets:
    """The service level objectives: event to on air at the median and 95th percentile, the
    corrections desk at the 95th, and the share of items the error budget expects on time."""

    on_air_p50_ms: int
    on_air_p95_ms: int
    correction_p95_ms: int
    within_percent: int


@dataclass(frozen=True, slots=True)
class Costs:
    """What tokens cost per model, and what the platform's infrastructure costs an hour."""

    prices: Mapping[str, Price]
    infra_microusd_per_hour: int


# Container Registry Basic, the one standing charge: Container Apps scale to zero within their
# free grant, and Key Vault, Storage and Log Analytics cost under a cent a month at this volume
# (measured; docs/cost-model.md).
INFRA_MICROUSD_PER_HOUR = 6_942
COSTS = Costs(prices=PRICES, infra_microusd_per_hour=INFRA_MICROUSD_PER_HOUR)
logger = logging.getLogger(__name__)
MS_PER_HOUR = 3_600_000

TARGETS = Targets(
    on_air_p50_ms=4000, on_air_p95_ms=8000, correction_p95_ms=10_000, within_percent=95
)


@dataclass(frozen=True, slots=True)
class Measured:
    """One match's operations, and the durations behind them, which a report pools across
    matches (percentiles of percentiles would be wrong)."""

    match: MatchOperations
    on_air: tuple[int, ...]
    corrections: tuple[int, ...]


def percentile(values: Sequence[int], p: int) -> int:
    """The nearest-rank `p`th percentile of a non-empty sample."""
    ordered = sorted(values)
    return ordered[max(math.ceil(p / 100 * len(ordered)), 1) - 1]


def spread(values: Sequence[int]) -> Spread:
    if not values:
        return Spread(count=0, p50_ms=None, p95_ms=None)
    return Spread(count=len(values), p50_ms=percentile(values, 50), p95_ms=percentile(values, 95))


def _ms(seconds: float) -> int:
    return min(max(round(seconds * 1000), 0), MAX_MS)


def _ratio(hits: Iterable[bool]) -> Ratio:
    counted = list(hits)
    return Ratio(hit=sum(counted), of=len(counted))


def _spent(attempts: Iterable[AttemptRecord]) -> list[TokenCount]:
    return [
        TokenCount(model=a.model, input=a.input_tokens, output=a.output_tokens)
        for a in attempts
        if a.agent != TEMPLATE_AGENT
    ]


def _use(spent: Sequence[TokenCount]) -> TokenUse:
    return TokenUse(input=sum(c.input for c in spent), output=sum(c.output for c in spent))


def _cost(spent: Sequence[TokenCount], costs: Costs) -> int:
    priced = [c for c in spent if c.model in costs.prices]
    if len(priced) != len(spent):
        logger.warning("tokens of a model without a price are counted but not priced")
    return micro_dollars(priced, costs.prices)


def _partner_items(entries: Sequence[FeedEntry]) -> list[TenantItemEntry]:
    """Each partner item version once (a decision republishes an item with its attempts)."""
    first: dict[str, TenantItemEntry] = {}
    for e in entries:
        if isinstance(e, TenantItemEntry):
            first.setdefault(e.overlay.item_id, e)
    return list(first.values())


def _explaining(entries: Sequence[FeedEntry], stamp: dict[int, float]) -> list[int]:
    moments = {e.moment.moment_id: e.entry_seq for e in entries if isinstance(e, MomentEntry)}
    return [
        _ms(stamp[e.entry_seq] - stamp[moments[e.insight.moment_id]])
        for e in entries
        if isinstance(e, InsightEntry) and e.insight.moment_id in moments
    ]


def _models(insights: Sequence[InsightEntry]) -> tuple[Ratio, Ratio, Ratio, int]:
    """First passes, fallbacks, drafts judged, and model errors."""
    drafted = [i for i in insights if any(a.agent != TEMPLATE_AGENT for a in i.attempts)]
    first = _ratio(
        i.attempts[0].agent != TEMPLATE_AGENT and i.attempts[0].outcome == "passed" for i in drafted
    )
    fallbacks = _ratio(i.attempts[-1].agent == TEMPLATE_AGENT for i in insights)
    tries = [a for i in insights for a in i.attempts if a.agent != TEMPLATE_AGENT]
    judged = _ratio(a.outcome == "passed" for a in tries if a.outcome != "error")
    errors = sum(a.outcome == "error" for a in tries)
    return first, fallbacks, judged, errors


def _partners(
    entries: Sequence[FeedEntry],
    stamp: dict[int, float],
    played: dict[int, float],
    *,
    target: int,
    costs: Costs,
    budgets: Mapping[TenantId, int],
) -> tuple[tuple[PartnerOperations, ...], tuple[int, ...]]:
    as_of = {
        e.insight.insight_id: e.insight.as_of_seq for e in entries if isinstance(e, InsightEntry)
    }
    first: dict[str, TenantItemEntry] = {}
    for e in entries:
        if isinstance(e, TenantItemEntry) and e.localized is not None and e.localized.version == 1:
            first.setdefault(e.overlay.item_id, e)
    by_partner: dict[TenantId, list[TenantItemEntry]] = defaultdict(list)
    for item in first.values():
        by_partner[item.tenant_id].append(item)
    written: dict[TenantId, list[TokenCount]] = defaultdict(list)
    for item in _partner_items(entries):
        written[item.tenant_id].extend(_spent(item.attempts))
    partners, every = [], []
    for tenant_id in sorted(by_partner):
        items = by_partner[tenant_id]
        timed = [
            _ms(stamp[i.entry_seq] - played[as_of[i.localized.insight_id]])
            for i in items
            if i.state == "on_air"
            and i.localized is not None
            and as_of.get(i.localized.insight_id) in played
        ]
        every.extend(timed)
        budget = budgets.get(tenant_id)
        partners.append(
            PartnerOperations(
                tenant_id=tenant_id,
                items=len(items),
                held=sum(i.state == "pending_approval" for i in items),
                on_air=spread(timed),
                within_target=_ratio(d <= target for d in timed),
                tokens=_use(written[tenant_id]),
                cost_microusd=_cost(written[tenant_id], costs),
                latency_budget_ms=budget,
                within_budget=_ratio(() if budget is None else (d <= budget for d in timed)),
            )
        )
    return tuple(partners), tuple(every)


def measure(  # noqa: PLR0913 - the match and its record, then how to judge and price it
    match_id: str,
    state: MatchState,
    entries: Sequence[FeedEntry],
    timing: RunTiming,
    *,
    now: float,
    targets: Targets = TARGETS,
    costs: Costs = COSTS,
    sharing: int = 1,
    budgets: Mapping[TenantId, int] | None = None,
) -> Measured:
    """One match's operations from its feed and its log's timing, read at `now` (the log's
    clock): a running match has lasted until now, a finished one until its last entry. The
    infrastructure is shared by the `sharing` matches of the run, and each partner's items are
    judged against its latency budget in `budgets`."""
    stamp = dict(zip((e.entry_seq for e in entries), timing.published, strict=False))
    played = dict(timing.played)
    if state == "idle":
        run_ms = 0
    elif state == "running" or not timing.published:
        run_ms = _ms(now - timing.started)
    else:
        run_ms = _ms(timing.published[-1] - timing.started)
    insights = [e for e in entries if isinstance(e, InsightEntry)]
    first, fallbacks, judged, errors = _models(insights)
    reports = [e for e in entries if isinstance(e, CorrectionReportEntry)]
    corrections = tuple(r.elapsed_ms for r in reports)
    partners, on_air = _partners(
        entries,
        stamp,
        played,
        target=targets.on_air_p95_ms,
        costs=costs,
        budgets=budgets or {},
    )
    spent = _spent(a for i in insights for a in i.attempts) + [
        c for item in _partner_items(entries) for c in _spent(item.attempts)
    ]
    infra = round(run_ms * costs.infra_microusd_per_hour / MS_PER_HOUR / max(sharing, 1))
    match = MatchOperations(
        match_id=match_id,
        state=state,
        run_ms=run_ms,
        events_played=len(played),
        moments=sum(isinstance(e, MomentEntry) for e in entries),
        explain=spread(_explaining(entries, stamp)),
        first_pass=first,
        fallbacks=fallbacks,
        model_drafts=judged,
        model_errors=errors,
        corrections=spread(corrections),
        corrected_items=sum(len(r.actions) for r in reports),
        tokens=_use(spent),
        model_cost_microusd=_cost(spent, costs),
        infra_cost_microusd=infra,
        partners=partners,
    )
    return Measured(match, on_air, corrections)


def report(
    measured: Sequence[Measured],
    *,
    generated_at: datetime,
    targets: Targets = TARGETS,
    costs: Costs = COSTS,
) -> OperationsReport:
    """Every match's operations, pooled against the objectives and the error budget."""
    on_air = [d for m in measured for d in m.on_air]
    corrections = [d for m in measured for d in m.corrections]
    pooled, desk = spread(on_air), spread(corrections)
    return OperationsReport(
        generated_at=generated_at,
        objectives=(
            Objective(key="on_air_p50", target_ms=targets.on_air_p50_ms, measured_ms=pooled.p50_ms),
            Objective(key="on_air_p95", target_ms=targets.on_air_p95_ms, measured_ms=pooled.p95_ms),
            Objective(
                key="correction_p95", target_ms=targets.correction_p95_ms, measured_ms=desk.p95_ms
            ),
        ),
        budget=ErrorBudget(
            within_percent=targets.within_percent,
            target_ms=targets.on_air_p95_ms,
            late=sum(d > targets.on_air_p95_ms for d in on_air),
            of=len(on_air),
        ),
        on_air=pooled,
        matches=tuple(m.match for m in measured),
        pricing=Pricing(
            models=tuple(
                ModelPrice(
                    model=model,
                    input_microusd_per_million=price.input_microusd_per_million,
                    output_microusd_per_million=price.output_microusd_per_million,
                )
                for model, price in sorted(costs.prices.items())
            ),
            infra_microusd_per_hour=costs.infra_microusd_per_hour,
        ),
    )
