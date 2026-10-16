"use client";

import type { ReactNode } from "react";

import { LedReadout } from "@/components/led/LedReadout";
import { useMatches } from "@/components/matchday/useMatchday";
import { AppShell } from "@/components/shell/AppShell";
import { type Column, DataTable } from "@/components/ui/DataTable";
import type {
  MatchOperations,
  Objective,
  OperationsReport,
  PartnerOperations,
  Ratio,
} from "@/contracts/operations";
import { PARTNERS } from "@/domain/broadcast";
import {
  budgetUse,
  dollars,
  objectiveMet,
  phase,
  ranFor,
  seconds,
  totals,
  verdict,
} from "@/domain/operations";

import { type Lookup, useOperations } from "./useOperations";

const OBJECTIVE_NAMES: Readonly<Record<Objective["key"], string>> = {
  on_air_p50: "Event to on air, median",
  on_air_p95: "Event to on air, 95th percentile",
  correction_p95: "Corrections desk, 95th percentile",
};
const STATE_NAMES: Readonly<Record<MatchOperations["state"], string>> = {
  idle: "Not started",
  running: "Running",
  finished: "Finished",
  failed: "Failed",
};
// The error budget's meter: twenty segments, each five percent of the budget.
const SEGMENTS = 20;
const PER_SEGMENT = 100 / SEGMENTS;
const MS_PER_MINUTE = 60_000;

const counted = (r: Ratio): string => `${r.hit} of ${r.of}`;
const tokens = (n: number): string => n.toLocaleString("en-GB");
const spread = (p50: number | null, p95: number | null): string =>
  p50 === null || p95 === null ? "–" : `${seconds(p50)} · ${seconds(p95)}`;
const perMillion = (micro: number): string => `$${(micro / 1_000_000).toFixed(2)}`;

function Verdict({ lookup }: { readonly lookup: Lookup }) {
  let tone = "neutral";
  let text = "Reading what the platform measured.";
  if (lookup.status === "unavailable") {
    tone = "red";
    text = "The operations service did not answer. This page reads it again every few seconds.";
  } else if (lookup.status === "ready") {
    ({ tone, text } = verdict(lookup.report));
  }
  return (
    <p role="status" aria-label="Operations verdict" className="verdict" data-tone={tone}>
      <span aria-hidden="true" className="verdict__lamp" />
      {text}
    </p>
  );
}

function Standing({ objective }: { readonly objective: Objective }) {
  const met = objectiveMet(objective);
  const word = met === null ? "Not yet measured" : met ? "Met" : "Missed";
  return (
    <span className="standing" data-met={met === null ? undefined : String(met)}>
      <span aria-hidden="true" className="standing__lamp" />
      {word}
    </span>
  );
}

const OBJECTIVE_COLUMNS: readonly Column<Objective>[] = [
  { key: "objective", header: "Objective", cell: (o) => OBJECTIVE_NAMES[o.key] },
  { key: "target", header: "Target", numeric: true, cell: (o) => `≤ ${seconds(o.targetMs)}` },
  {
    key: "measured",
    header: "Measured",
    numeric: true,
    cell: (o) => (o.measuredMs === null ? "–" : seconds(o.measuredMs)),
  },
  { key: "standing", header: "Standing", cell: (o) => <Standing objective={o} /> },
];

function BudgetMeter({ report }: { readonly report: OperationsReport }) {
  const { budget } = report;
  const use = budgetUse(budget);
  const spent = use?.spentPercent ?? 0;
  const lit = Math.min(SEGMENTS, Math.ceil(spent / PER_SEGMENT));
  const over = spent > 100;
  const objective = `${budget.withinPercent}% of items on air within ${seconds(budget.targetMs)}`;
  const reading =
    use === null
      ? "Not yet measured: no item has gone on air without an editor."
      : `${use.late} of ${use.of} items later than ${seconds(budget.targetMs)}; the objective allows ${use.allowed.toFixed(1)}. ${spent}% of the budget spent.`;
  return (
    <div className="budget">
      <h3 className="budget__title">Error budget</h3>
      <p className="budget__objective">{objective}</p>
      <div
        role="meter"
        aria-label="Error budget spent"
        aria-valuemin={0}
        aria-valuemax={Math.max(100, spent)}
        aria-valuenow={spent}
        aria-valuetext={use === null ? "Not yet measured" : `${spent}% spent`}
        className="budget__meter"
        data-over={over || undefined}
      >
        {Array.from({ length: SEGMENTS }, (_, i) => (
          <span key={i} className="budget__segment" data-lit={i < lit || undefined} />
        ))}
      </div>
      <p className="budget__reading">{reading}</p>
    </div>
  );
}

function Amount({ report }: { readonly report: OperationsReport }) {
  const sum = totals(report);
  const sofar = phase(report) === "running";
  const total = dollars(sum.totalMicrousd);
  return (
    <section aria-labelledby="amount-heading" className="amount">
      <h2 id="amount-heading" className="panel-heading">
        Amount
      </h2>
      <LedReadout
        text={total}
        label={`Cost${sofar ? " so far" : ""}: ${total}`}
        dotSize={5}
        className="amount__readout"
      />
      <p className="amount__note">{sofar ? "So far, while the matchday runs" : "This run"}</p>
      <dl className="amount__lines">
        <div>
          <dt>Models</dt>
          <dd className="tabular">{dollars(sum.modelMicrousd)}</dd>
        </div>
        <div>
          <dt>Infrastructure</dt>
          <dd className="tabular">{dollars(sum.infraMicrousd)}</dd>
        </div>
        <div>
          <dt>Tokens in · out</dt>
          <dd className="tabular">
            {tokens(sum.tokensIn)} · {tokens(sum.tokensOut)}
          </dd>
        </div>
      </dl>
    </section>
  );
}

function matchColumns(names: ReadonlyMap<string, string>): readonly Column<MatchOperations>[] {
  return [
    {
      key: "match",
      header: "Match",
      cell: (m) => (
        <span className="statement__match">
          <span>{names.get(m.matchId) ?? m.matchId}</span>
          <span className="statement__state">{STATE_NAMES[m.state]}</span>
        </span>
      ),
    },
    { key: "ran", header: "Ran", numeric: true, cell: (m) => ranFor(m.runMs) },
    {
      key: "items",
      header: "Items a minute",
      numeric: true,
      cell: (m) => {
        const items = m.partners.reduce((n, p) => n + p.items, 0);
        return m.runMs === 0 ? "–" : ((items * MS_PER_MINUTE) / m.runMs).toFixed(1);
      },
    },
    {
      key: "onair",
      header: "On air, median · 95th",
      numeric: true,
      cell: (m) => spread(m.onAir.p50Ms, m.onAir.p95Ms),
    },
    {
      key: "corrections",
      header: "Corrections, 95th",
      numeric: true,
      cell: (m) =>
        m.corrections.p95Ms === null
          ? "–"
          : `${m.corrections.count} · ${seconds(m.corrections.p95Ms)}`,
    },
    {
      key: "tokens",
      header: "Tokens",
      numeric: true,
      cell: (m) => tokens(m.tokens.input + m.tokens.output),
    },
    { key: "models", header: "Models", numeric: true, cell: (m) => dollars(m.modelCostMicrousd) },
    {
      key: "infra",
      header: "Infrastructure",
      numeric: true,
      cell: (m) => dollars(m.infraCostMicrousd),
    },
    {
      key: "total",
      header: "Total",
      numeric: true,
      cell: (m) => <strong>{dollars(m.modelCostMicrousd + m.infraCostMicrousd)}</strong>,
    },
  ];
}

interface PartnerTotal {
  readonly tenantId: string;
  readonly name: string;
  readonly items: number;
  readonly held: number;
  readonly budgetMs: number | null;
  readonly withinBudget: Ratio;
  readonly tokens: number;
  readonly costMicrousd: number;
}

/** Each partner across the run's matches: everything that adds up, added up. */
function byPartner(report: OperationsReport): readonly PartnerTotal[] {
  const all = report.matches.flatMap((m) => m.partners);
  return PARTNERS.flatMap((partner) => {
    const theirs: PartnerOperations[] = all.filter((p) => p.tenantId === partner.id);
    if (theirs.length === 0) return [];
    const add = (of: (p: PartnerOperations) => number) => theirs.reduce((n, p) => n + of(p), 0);
    return [
      {
        tenantId: partner.id,
        name: partner.name,
        items: add((p) => p.items),
        held: add((p) => p.held),
        budgetMs: theirs.at(-1)?.latencyBudgetMs ?? null,
        withinBudget: { hit: add((p) => p.withinBudget.hit), of: add((p) => p.withinBudget.of) },
        tokens: add((p) => p.tokens.input + p.tokens.output),
        costMicrousd: add((p) => p.costMicrousd),
      },
    ];
  });
}

const PARTNER_COLUMNS: readonly Column<PartnerTotal>[] = [
  { key: "partner", header: "Partner", cell: (p) => p.name },
  { key: "items", header: "Items", numeric: true, cell: (p) => p.items },
  { key: "held", header: "Held for an editor", numeric: true, cell: (p) => p.held },
  {
    key: "budget",
    header: "Own latency budget",
    numeric: true,
    cell: (p) => (p.budgetMs === null ? "–" : seconds(p.budgetMs)),
  },
  {
    key: "within",
    header: "On air within it",
    numeric: true,
    cell: (p) => (p.budgetMs === null ? "–" : counted(p.withinBudget)),
  },
  { key: "tokens", header: "Localizer tokens", numeric: true, cell: (p) => tokens(p.tokens) },
  { key: "cost", header: "Cost", numeric: true, cell: (p) => dollars(p.costMicrousd) },
];

function draftingColumns(names: ReadonlyMap<string, string>): readonly Column<MatchOperations>[] {
  return [
    { key: "match", header: "Match", cell: (m) => names.get(m.matchId) ?? m.matchId },
    { key: "insights", header: "Insights", numeric: true, cell: (m) => m.fallbacks.of },
    {
      key: "explain",
      header: "Explained in, median · 95th",
      numeric: true,
      cell: (m) => spread(m.explain.p50Ms, m.explain.p95Ms),
    },
    {
      key: "first",
      header: "First draft passed",
      numeric: true,
      cell: (m) => counted(m.firstPass),
    },
    {
      key: "drafts",
      header: "Drafts the Verifier passed",
      numeric: true,
      cell: (m) => counted(m.modelDrafts),
    },
    { key: "errors", header: "Model errors", numeric: true, cell: (m) => m.modelErrors },
    {
      key: "fallbacks",
      header: "Written by the template",
      numeric: true,
      cell: (m) => counted(m.fallbacks),
    },
  ];
}

interface Rate {
  readonly name: string;
  readonly input: string;
  readonly output: string;
}

function rates(report: OperationsReport): readonly Rate[] {
  return report.pricing.models.map((m) => ({
    name: m.model,
    input: perMillion(m.inputMicrousdPerMillion),
    output: perMillion(m.outputMicrousdPerMillion),
  }));
}

const RATE_COLUMNS: readonly Column<Rate>[] = [
  { key: "model", header: "Model", cell: (r) => <code>{r.name}</code> },
  { key: "input", header: "Input, a million tokens", numeric: true, cell: (r) => r.input },
  { key: "output", header: "Output, a million tokens", numeric: true, cell: (r) => r.output },
];

const NOT_RUN = "No match has run since the platform last started.";

/** A wide table that scrolls inside its panel: reachable by keyboard, named for screen readers. */
function Scroll({ label, children }: { readonly label: string; readonly children: ReactNode }) {
  return (
    <div role="region" aria-label={label} tabIndex={0} className="statement__scroll">
      {children}
    </div>
  );
}

function Statement({
  report,
  names,
}: {
  readonly report: OperationsReport;
  readonly names: ReadonlyMap<string, string>;
}) {
  const ran = report.matches.filter((m) => m.state !== "idle");
  const infraHour = dollars(report.pricing.infraMicrousdPerHour);
  return (
    <>
      <div className="statement__top">
        <section aria-labelledby="levels-heading" className="levels">
          <h2 id="levels-heading" className="panel-heading">
            Service levels
          </h2>
          <DataTable
            caption="Service levels"
            hideCaption
            columns={OBJECTIVE_COLUMNS}
            rows={report.objectives}
            rowKey={(o) => o.key}
          />
          <BudgetMeter report={report} />
        </section>
        <Amount report={report} />
      </div>
      <section aria-labelledby="matches-heading" className="statement__section">
        <h2 id="matches-heading" className="panel-heading">
          Itemised by match
        </h2>
        <Scroll label="Itemised by match, scrolls sideways">
          <DataTable
            caption="Itemised by match"
            hideCaption
            columns={matchColumns(names)}
            rows={ran}
            rowKey={(m) => m.matchId}
            empty={NOT_RUN}
          />
        </Scroll>
      </section>
      <div className="statement__pair">
        <section aria-labelledby="partners-heading" className="statement__section">
          <h2 id="partners-heading" className="panel-heading">
            By partner
          </h2>
          <Scroll label="By partner, scrolls sideways">
            <DataTable
              caption="By partner"
              hideCaption
              columns={PARTNER_COLUMNS}
              rows={byPartner(report)}
              rowKey={(p) => p.tenantId}
              empty="No partner has published an item yet."
            />
          </Scroll>
        </section>
        <section aria-labelledby="rates-heading" className="statement__section">
          <h2 id="rates-heading" className="panel-heading">
            Rates
          </h2>
          <DataTable
            caption="Rates"
            hideCaption
            columns={RATE_COLUMNS}
            rows={rates(report)}
            rowKey={(r) => r.name}
          />
          <p className="statement__note">
            Infrastructure: {infraHour} an hour, the platform&apos;s standing charge, shared by the
            matches of a run for as long as they run.
          </p>
        </section>
      </div>
      <section aria-labelledby="drafting-heading" className="statement__section">
        <h2 id="drafting-heading" className="panel-heading">
          How the words were written
        </h2>
        <Scroll label="How the words were written, scrolls sideways">
          <DataTable
            caption="How the words were written"
            hideCaption
            columns={draftingColumns(names)}
            rows={ran}
            rowKey={(m) => m.matchId}
            empty={NOT_RUN}
          />
        </Scroll>
      </section>
    </>
  );
}

/** Operations: the matchday run as a statement of service (ADR-016, docs/cost-model.md). */
export function OperationsScreen() {
  const lookup = useOperations();
  const { matches } = useMatches({ availability: false });
  const names = new Map(
    (matches ?? []).map((m) => [m.matchId, `${m.homeName} v ${m.awayName}`] as const),
  );
  return (
    <AppShell current="/operations" studio="Meridian League Studios" replay>
      <header className="page-header">
        <h1>Operations</h1>
        <Verdict lookup={lookup} />
        {lookup.status === "ready" && lookup.stale && (
          <p className="statement__stale">
            The last reading failed: these are the figures as they stood before.
          </p>
        )}
      </header>
      {lookup.status === "ready" && <Statement report={lookup.report} names={names} />}
      <p className="page-footnote statement__footnote">
        All data is synthetic. Every figure is measured by the platform as the matchday runs and
        restarts with it (the platform scales to zero). Model cost is a floor: a call that fails
        before reporting its tokens is not counted. Method: docs/cost-model.md.
      </p>
    </AppShell>
  );
}
