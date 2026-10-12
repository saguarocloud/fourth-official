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
const unsupported = (r: Ratio): string => `${r.of - r.hit} of ${r.of}`;

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

function Poll({ ground }: { readonly ground: ProvingGround }) {
  const stations = poll(ground);
  return (
    <section aria-labelledby="poll-heading" className="poll-panel">
      <h2 id="poll-heading" className="panel-heading">
        The poll · {stations.length} rules
      </h2>
      <ol aria-labelledby="poll-heading" className="poll">
        {stations.map((station) => (
          <StationRow key={station.rule} station={station} />
        ))}
      </ol>
    </section>
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
    ["Unsupported claims on air", unsupported(m.supportedClaims)],
    ["Policy breaches", String(m.policyViolations)],
    ["Planted lies refused", counted(m.verifierCatch)],
    ["Corrections carried", counted(m.correctionsCarried)],
    ["Planted stories found", counted(m.storylineRecall)],
    ["About a real moment", counted(m.keyMomentPrecision)],
  ];
  return (
    <section aria-labelledby="benchmark-heading" className="benchmark">
      <h2 id="benchmark-heading" className="panel-heading">
        The full benchmark
      </h2>
      <p className="benchmark__lede">
        The harness&apos;s own reference run: {card.matches} matches from {card.firstMatch},
        explained by {promptName(card)} with no model and no cost.
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

interface RunFailure {
  readonly run: string;
  readonly failure: FailedClaim;
}

function Failures({ all }: { readonly all: readonly RunFailure[] }) {
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

function Recorded({ ground }: { readonly ground: ProvingGround }) {
  const failures: RunFailure[] = [
    ...ground.candidate.failures.map((failure) => ({ run: "Candidate", failure })),
    ...ground.baseline.failures.map((failure) => ({ run: "Production", failure })),
  ];
  return (
    <>
      <div className="poll-board">
        <TheCall ground={ground} />
        <Poll ground={ground} />
      </div>
      <section aria-labelledby="measures-heading" className="measures">
        <h2 id="measures-heading" className="panel-heading">
          Side by side
        </h2>
        <p className="measures__note">
          Every measure of both runs. A measure marked (reported) is shown for context: the gate
          does not rule on it.
        </p>
        <DataTable
          caption="Every measure, both runs"
          hideCaption
          columns={MEASURE_COLUMNS}
          rows={measures(ground)}
          rowKey={(m) => m.label}
        />
      </section>
      <div className="proving__lower" data-failures={failures.length > 0}>
        <Failures all={failures} />
        <Benchmark card={ground.benchmark} />
      </div>
    </>
  );
}

interface Line {
  readonly tone: "green" | "red" | "neutral";
  readonly text: string;
}

const NOT_READY: Readonly<Record<Exclude<Lookup["status"], "ready">, Line>> = {
  loading: { tone: "neutral", text: "Reading the recorded runs." },
  busy: { tone: "red", text: "Too many reads from here. Wait a moment and try again." },
  unavailable: {
    tone: "red",
    text: "The recorded runs could not be read: the match service did not answer.",
  },
};

function Verdict({ lookup }: { readonly lookup: Lookup }) {
  const verdict: Line =
    lookup.status === "ready" ? verdictLine(lookup.ground) : NOT_READY[lookup.status];
  return (
    <p role="status" aria-label="Release Gate verdict" className="verdict" data-tone={verdict.tone}>
      <span aria-hidden="true" className="verdict__lamp" />
      {verdict.text}
    </p>
  );
}

/** The Proving Ground: the Release Gate's last call on a candidate, rule by rule, and the runs
 * behind it. */
export function ProvingGroundScreen() {
  const { lookup, retry } = useProvingGround();
  const matches = lookup.status === "ready" ? lookup.ground.candidate.matches : null;
  return (
    <AppShell current="/proving-ground" studio="Meridian League Studios" replay>
      <header className="page-header">
        <h1>Proving Ground</h1>
        <Verdict lookup={lookup} />
      </header>
      {lookup.status === "ready" && <Recorded ground={lookup.ground} />}
      {(lookup.status === "busy" || lookup.status === "unavailable") && (
        <div className="proving__retry">
          <button type="button" className="key" data-size="sm" onClick={retry}>
            <span>Try again</span>
          </button>
        </div>
      )}
      <p className="page-footnote proving__footnote">
        All data is synthetic. Every pull request that changes the pipeline runs its own production
        configuration beside the base branch&apos;s, with the models, on the same{" "}
        {matches === null ? "benchmark matches" : `${matches} benchmark matches`}; the Release Gate
        blocks it if any rule above calls no-go. The candidate shown is a prompt kept deliberately
        worse, to show the gate blocking.
      </p>
    </AppShell>
  );
}
