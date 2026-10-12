"use client";

import { LedReadout } from "@/components/led/LedReadout";
import { AppShell } from "@/components/shell/AppShell";
import { type Column, DataTable } from "@/components/ui/DataTable";
import type { FailedClaim, Ratio, Scorecard } from "@/contracts/scorecard";
import {
  type Measure,
  measures,
  poll,
  promptName,
  type ProvingGround,
  type Station,
  verdictLine,
} from "@/domain/proving";

import { type Lookup, useProvingGround } from "./useProvingGround";

const counted = (r: Ratio): string => `${r.hit} of ${r.of}`;
const costOf = (card: Scorecard): string =>
  card.metrics.costUsd === null ? "none" : `$${card.metrics.costUsd.toFixed(2)}`;

function TheCall({ ground }: { readonly ground: ProvingGround }) {
  const go = ground.verdict.allowed;
  const { candidate, baseline } = ground;
  return (
    <div className="call" data-go={go}>
      <h2 className="panel-heading">The call</h2>
      <LedReadout
        text={go ? "GO" : "NO-GO"}
        label={`The call: ${go ? "go" : "no-go"}`}
        tone={go ? "green" : "red"}
        dotSize={6}
        className="call__readout"
      />
      <p className="call__subject">
        {promptName(candidate)} against production&apos;s{" "}
        {baseline.configuration.analystPrompt.split("/")[1]}
      </p>
      <dl className="call__facts">
        <div>
          <dt>Benchmark</dt>
          <dd className="tabular">
            {candidate.matches} matches from {candidate.firstMatch}
          </dd>
        </div>
        <div>
          <dt>Models</dt>
          <dd>{candidate.configuration.models.join(", then ")}</dd>
        </div>
        <div>
          <dt>Cost</dt>
          <dd className="tabular">
            {costOf(candidate)} candidate · {costOf(baseline)} production
          </dd>
        </div>
        <div>
          <dt>Recorded</dt>
          <dd>
            <time dateTime={candidate.generatedAt}>{candidate.generatedAt.slice(0, 10)}</time>
          </dd>
        </div>
      </dl>
    </div>
  );
}

function StationRow({ station }: { readonly station: Station }) {
  return (
    <li className="station" data-go={station.go}>
      <span className="station__call">
        <span aria-hidden="true" className="station__lamp" />
        {station.go ? "Go" : "No-go"}
      </span>
      <h3 className="station__title">{station.title}</h3>
      <p className="station__figure tabular">{station.candidate}</p>
      <p className="station__against">
        <span className="tabular">Production {station.baseline}</span>
        <span className="station__allowance">{station.allowance}</span>
      </p>
    </li>
  );
}

const MEASURE_COLUMNS: readonly Column<Measure>[] = [
  {
    key: "measure",
    header: "Measure",
    cell: (m) => (
      <>
        {m.label}
        {!m.gated && <span className="measure__reported"> (reported)</span>}
      </>
    ),
  },
  { key: "baseline", header: "Production", cell: (m) => m.baseline, numeric: true },
  { key: "candidate", header: "Candidate", cell: (m) => m.candidate, numeric: true },
];

function Benchmark({ card }: { readonly card: Scorecard }) {
  const m = card.metrics;
  const facts: readonly (readonly [string, string])[] = [
    ["Claims on air that were true", counted(m.supportedClaims)],
    ["Planted stories found", counted(m.storylineRecall)],
    ["About a real moment", counted(m.keyMomentPrecision)],
    ["Planted lies refused", counted(m.verifierCatch)],
    ["Corrections carried", counted(m.correctionsCarried)],
    ["Policy breaches", String(m.policyViolations)],
  ];
  return (
    <section aria-labelledby="benchmark-heading" className="benchmark">
      <h2 id="benchmark-heading" className="panel-heading">
        The full benchmark
      </h2>
      <p className="benchmark__lede">
        {card.matches} matches from {card.firstMatch}, written by {promptName(card)}: the harness
        itself, with no model and no cost.
      </p>
      <dl className="benchmark__facts">
        {facts.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd className="tabular">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function Failures({ ground }: { readonly ground: ProvingGround }) {
  const runs: readonly (readonly [string, readonly FailedClaim[]])[] = [
    ["Candidate", ground.candidate.failures],
    ["Production", ground.baseline.failures],
  ];
  const all = runs.flatMap(([run, failures]) => failures.map((f) => ({ run, failure: f })));
  return (
    <section aria-labelledby="failures-heading" className="failures">
      <h2 id="failures-heading" className="panel-heading">
        Unsupported claims
      </h2>
      {all.length === 0 ? (
        <p className="failures__none">
          No claim on air at full time was unsupported, in either run.
        </p>
      ) : (
        <ul aria-labelledby="failures-heading" className="failures__list">
          {all.map(({ run, failure }) => (
            <li key={`${run}:${failure.itemId}:${failure.claimId}`} className="failure">
              <p className="failure__where">
                {run} · {failure.matchId} · <span className="failure__id">{failure.itemId}</span>
              </p>
              <p className="failure__text">{failure.text}</p>
              <ul className="failure__reasons">
                {failure.reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
              <p className="failure__evidence">
                Rests on <span className="failure__id">{failure.eventIds.join(", ")}</span>
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

const NOTES: Readonly<Record<Exclude<Lookup["status"], "ready">, string>> = {
  loading: "Reading the recorded runs.",
  busy: "Too many reads from here. Wait a moment and try again.",
  unavailable: "The recorded runs could not be read: the match service did not answer.",
};

function Verdict({ ground }: { readonly ground: ProvingGround }) {
  const verdict = verdictLine(ground);
  return (
    <p role="status" aria-label="Release Gate verdict" className="verdict" data-tone={verdict.tone}>
      <span aria-hidden="true" className="verdict__lamp" />
      {verdict.text}
    </p>
  );
}

function Recorded({ ground }: { readonly ground: ProvingGround }) {
  return (
    <>
      <div className="poll-board">
        <TheCall ground={ground} />
        <ol aria-label="The poll" className="poll">
          {poll(ground).map((station) => (
            <StationRow key={station.rule} station={station} />
          ))}
        </ol>
      </div>
      <section aria-labelledby="measures-heading" className="measures">
        <h2 id="measures-heading" className="panel-heading">
          Side by side
        </h2>
        <DataTable
          caption="Every measure, both runs"
          hideCaption
          columns={MEASURE_COLUMNS}
          rows={measures(ground)}
          rowKey={(m) => m.label}
        />
      </section>
      <div className="proving__lower">
        <Failures ground={ground} />
        <Benchmark card={ground.benchmark} />
      </div>
    </>
  );
}

/** The Proving Ground: the Release Gate's last call on a candidate, rule by rule, and the runs
 * behind it. */
export function ProvingGroundScreen() {
  const { lookup, retry } = useProvingGround();
  return (
    <AppShell current="/proving-ground" studio="Meridian League Studios" replay>
      <header className="page-header">
        <h1>Proving Ground</h1>
        {lookup.status === "ready" && (
          <>
            <p>
              {promptName(lookup.ground.candidate)} against production ·{" "}
              {lookup.ground.candidate.matches} benchmark matches
            </p>
            <Verdict ground={lookup.ground} />
          </>
        )}
      </header>
      {lookup.status === "ready" ? (
        <Recorded ground={lookup.ground} />
      ) : (
        <div className="provenance__note" data-status={lookup.status}>
          <p>{NOTES[lookup.status]}</p>
          {lookup.status !== "loading" && (
            <button type="button" className="key" data-size="sm" onClick={retry}>
              <span>Try again</span>
            </button>
          )}
        </div>
      )}
      <p className="page-footnote">
        All data is synthetic. Every pull request that changes the pipeline runs its own production
        configuration beside the base branch&apos;s on the same 20 matches, on the models, and the
        Release Gate blocks it if it is worse. The runs here were recorded with the candidate prompt
        kept for this purpose.
      </p>
    </AppShell>
  );
}
