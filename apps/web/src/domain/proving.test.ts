import { describe, expect, it } from "vitest";

import type { GateVerdict } from "@/contracts/gateVerdict";
import fixture from "@/fixtures/proving-ground.json";

import { measures, parseProvingGround, poll, type ProvingGround, verdictLine } from "./proving";

const RECORDED = fixture as unknown as ProvingGround;

function allowed(): ProvingGround {
  return {
    ...RECORDED,
    verdict: {
      ...RECORDED.verdict,
      allowed: true,
      checks: RECORDED.verdict.checks.map((c) => ({ ...c, passed: true })) as GateVerdict["checks"],
    },
  };
}

describe("parseProvingGround", () => {
  it("accepts the API's answer as it came", () => {
    expect(parseProvingGround(fixture)).toEqual(fixture);
  });

  it.each([
    ["nothing", null],
    ["no verdict", { ...RECORDED, verdict: undefined }],
    [
      "a verdict that is not a boolean",
      { ...RECORDED, verdict: { ...RECORDED.verdict, allowed: "no" } },
    ],
    [
      "an unknown rule",
      {
        ...RECORDED,
        verdict: { ...RECORDED.verdict, checks: [{ rule: "vibes", passed: true, detail: "x" }] },
      },
    ],
    [
      "a ratio with more hits than cases",
      {
        ...RECORDED,
        candidate: {
          ...RECORDED.candidate,
          metrics: { ...RECORDED.candidate.metrics, modelWritten: { hit: 9, of: 2 } },
        },
      },
    ],
    [
      "models that are not a list of names",
      {
        ...RECORDED,
        candidate: {
          ...RECORDED.candidate,
          configuration: { ...RECORDED.candidate.configuration, models: "fast" },
        },
      },
    ],
    [
      "a prompt that names no version",
      {
        ...RECORDED,
        candidate: {
          ...RECORDED.candidate,
          configuration: { ...RECORDED.candidate.configuration, analystPrompt: "analyst" },
        },
      },
    ],
    ["no recording time", { ...RECORDED, baseline: { ...RECORDED.baseline, generatedAt: 7 } }],
    [
      "a failure with no reasons",
      {
        ...RECORDED,
        candidate: {
          ...RECORDED.candidate,
          failures: [
            { matchId: "m1001", itemId: "it-x-v1", claimId: "cl-1", text: "x", eventIds: [] },
          ],
        },
      },
    ],
    [
      "runs over different benchmarks",
      { ...RECORDED, candidate: { ...RECORDED.candidate, matches: 100 } },
    ],
    [
      "a scorecard with no configuration",
      { ...RECORDED, baseline: { ...RECORDED.baseline, configuration: null } },
    ],
  ])("refuses %s", (_, value) => {
    expect(parseProvingGround(value)).toBeNull();
  });
});

describe("poll", () => {
  it("calls every rule in the gate's order, go or no-go", () => {
    const stations = poll(RECORDED);

    expect(stations.map((s) => [s.title, s.go])).toEqual([
      ["Unsupported claims on air", true],
      ["Policy breaches", true],
      ["Planted lies refused", true],
      ["Corrections carried", true],
      ["Planted stories found", true],
      ["Written by the model", false],
      ["Time to explain (p50)", true],
    ]);
  });

  it("sets the candidate's figure against production's and the margin the rule allows", () => {
    const written = poll(RECORDED).find((s) => s.rule === "model_written")!;
    const latency = poll(RECORDED).find((s) => s.rule === "latency_p50")!;
    const untrue = poll(RECORDED).find((s) => s.rule === "unsupported_claims")!;

    expect(written).toMatchObject({
      candidate: "29.1%",
      baseline: "98.7%",
      allowance: "Rule: may drop 5 points",
    });
    expect(latency).toMatchObject({
      candidate: "3.1 s",
      baseline: "4.9 s",
      allowance: "Rule: may grow 15% and 2 s",
    });
    expect(untrue).toMatchObject({
      candidate: "0 of 206",
      baseline: "0 of 236",
      allowance: "Rule: none",
    });
  });
});

describe("verdictLine", () => {
  it("names what is blocked and how many rules called no-go", () => {
    expect(verdictLine(RECORDED)).toEqual({
      tone: "red",
      text:
        "The Release Gate blocks Analyst prompt v1.4 against production's v1.2 on 1 of 7 rules: " +
        "written by the model, 29.1% against 98.7% (may drop 5 points).",
    });
  });

  it("says when a candidate may ship", () => {
    expect(verdictLine(allowed())).toEqual({
      tone: "green",
      text: "The Release Gate allows Analyst prompt v1.4 against production's v1.2: all 7 rules call go.",
    });
  });
});

describe("measures", () => {
  it("lists every measure side by side, gated or reported", () => {
    const rows = measures(RECORDED);

    expect(rows.map((r) => [r.label, r.gated])).toEqual([
      ["Unsupported claims on air", true],
      ["Policy breaches", true],
      ["Planted lies refused", true],
      ["Corrections carried", true],
      ["Planted stories found", true],
      ["Written by the model", true],
      ["Time to explain (p50)", true],
      ["About a real moment", false],
      ["Passed first time", false],
      ["Time to explain (p95)", false],
      ["Cost of the run", false],
    ]);
    expect(rows.find((r) => r.label === "Cost of the run")).toEqual({
      label: "Cost of the run",
      baseline: "$0.14",
      candidate: "$0.08",
      gated: false,
    });
    expect(rows.find((r) => r.label === "Written by the model")).toMatchObject({
      baseline: "78 of 79 (98.7%)",
      candidate: "23 of 79 (29.1%)",
      gated: true,
    });
  });
});
