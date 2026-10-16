import { describe, expect, it } from "vitest";

import type { MatchOperations, OperationsReport } from "@/contracts/operations";

import {
  budgetUse,
  budgetWords,
  dollars,
  timesOver,
  objectiveMet,
  parseOperations,
  ranFor,
  seconds,
  totals,
  verdict,
} from "./operations";

const spread = (count: number, p50: number | null, p95: number | null) => ({
  count,
  p50Ms: p50,
  p95Ms: p95,
});

function match(id: string, overrides: Partial<MatchOperations> = {}): MatchOperations {
  return {
    matchId: id,
    state: "finished",
    runMs: 600_000,
    eventsPlayed: 1400,
    moments: 12,
    explain: spread(12, 2500, 9000),
    onAir: spread(2, 3000, 6000),
    firstPass: { hit: 9, of: 12 },
    fallbacks: { hit: 1, of: 12 },
    modelDrafts: { hit: 11, of: 15 },
    modelErrors: 1,
    corrections: spread(1, 40, 40),
    correctedItems: 6,
    tokens: { input: 90_000, output: 12_000 },
    modelCostMicrousd: 46_500,
    infraCostMicrousd: 386,
    partners: [
      {
        tenantId: "rheinblick-sport",
        items: 3,
        held: 1,
        onAir: spread(2, 3000, 6000),
        withinTarget: { hit: 2, of: 2 },
        tokens: { input: 2400, output: 420 },
        costMicrousd: 1440,
        latencyBudgetMs: 8000,
        withinBudget: { hit: 2, of: 2 },
      },
    ],
    ...overrides,
  };
}

function report(overrides: Partial<OperationsReport> = {}): OperationsReport {
  return {
    generatedAt: "2026-10-16T09:00:00Z",
    objectives: [
      { key: "on_air_p50", targetMs: 4000, measuredMs: 3000 },
      { key: "on_air_p95", targetMs: 8000, measuredMs: 6000 },
      { key: "correction_p95", targetMs: 10000, measuredMs: 40 },
    ],
    budget: { withinPercent: 95, targetMs: 8000, late: 0, of: 40 },
    onAir: spread(40, 3000, 6000),
    matches: [match("m42"), match("m43")],
    pricing: {
      models: [
        {
          model: "fallback",
          inputMicrousdPerMillion: 400_000,
          outputMicrousdPerMillion: 1_600_000,
        },
        { model: "fast", inputMicrousdPerMillion: 250_000, outputMicrousdPerMillion: 2_000_000 },
      ],
      infraMicrousdPerHour: 6942,
    },
    ...overrides,
  };
}

const idle = () =>
  report({
    objectives: [
      { key: "on_air_p50", targetMs: 4000, measuredMs: null },
      { key: "on_air_p95", targetMs: 8000, measuredMs: null },
      { key: "correction_p95", targetMs: 10000, measuredMs: null },
    ],
    budget: { withinPercent: 95, targetMs: 8000, late: 0, of: 0 },
    onAir: spread(0, null, null),
    matches: [match("m42", { state: "idle", partners: [] })],
  });

describe("parseOperations", () => {
  it("reads a report shaped as the API sends it", () => {
    expect(parseOperations(report())).toEqual(report());
  });

  it("refuses anything else", () => {
    expect(parseOperations(null)).toBeNull();
    expect(
      parseOperations({ ...report(), matches: [{ ...match("m42"), onAir: undefined }] }),
    ).toBeNull();
    expect(parseOperations({ ...report(), matches: "m42" })).toBeNull();
    expect(parseOperations({ ...report(), budget: { late: -1 } })).toBeNull();
    for (const withinPercent of [0, 101]) {
      expect(
        parseOperations({ ...report(), budget: { ...report().budget, withinPercent } }),
      ).toBeNull();
    }
    expect(
      parseOperations({ ...report(), matches: [{ ...match("m42"), modelCostMicrousd: 1.5 }] }),
    ).toBeNull();
  });
});

describe("figures", () => {
  it("writes money from micro-dollars to the tenth of a cent, and below a cent exactly", () => {
    expect(dollars(46_886)).toBe("$0.0469");
    expect(dollars(1_234_567)).toBe("$1.2346");
    expect(dollars(0)).toBe("$0.0000");
    expect(dollars(58)).toBe("< $0.0001");
  });

  it("writes durations in seconds to the tenth, and under a second in milliseconds", () => {
    expect(seconds(11_635)).toBe("11.6 s");
    expect(seconds(8000)).toBe("8.0 s");
    expect(seconds(1000)).toBe("1.0 s");
    expect(seconds(40)).toBe("40 ms");
    expect(seconds(0)).toBe("0 ms");
  });

  it("writes how long a match ran in minutes and seconds", () => {
    expect(ranFor(758_474)).toBe("12 min 38 s");
    expect(ranFor(60_000)).toBe("1 min 0 s");
    expect(ranFor(13_700)).toBe("13.7 s");
  });

  it("adds up the run's cost and tokens", () => {
    expect(totals(report())).toEqual({
      modelMicrousd: 93_000,
      infraMicrousd: 772,
      totalMicrousd: 93_772,
      tokensIn: 180_000,
      tokensOut: 24_000,
    });
  });
});

describe("the error budget in words", () => {
  it("says a budget only just overspent is over, not spent in full", () => {
    const just = budgetUse({ withinPercent: 95, targetMs: 8000, late: 1001, of: 20_000 })!;
    expect(just).toMatchObject({ spentPercent: 100, over: true });
    expect(budgetWords(just)).toBe("1001 of 20000 items late, just over the error budget");
  });

  it("writes a whole number of times over without a decimal", () => {
    const five = budgetUse({ withinPercent: 95, targetMs: 8000, late: 248, of: 1000 })!;
    expect(timesOver(five)).toBe("5");
  });

  it("says how far over a spent budget went", () => {
    const over = budgetUse({ withinPercent: 95, targetMs: 8000, late: 8, of: 34 })!;
    expect(budgetWords(over)).toBe("8 of 34 items late, the error budget spent 4.7 times over");
    const within = budgetUse({ withinPercent: 95, targetMs: 8000, late: 1, of: 40 })!;
    expect(budgetWords(within)).toBe("1 of 40 items late, 50% of the error budget spent");
  });
});

describe("the error budget", () => {
  it("allows the share of items the objective leaves, and counts what the late ones spent", () => {
    expect(budgetUse({ withinPercent: 95, targetMs: 8000, late: 1, of: 40 })).toEqual({
      late: 1,
      of: 40,
      allowed: 2,
      spentPercent: 50,
      over: false,
    });
    expect(budgetUse({ withinPercent: 95, targetMs: 8000, late: 6, of: 6 })?.spentPercent).toBe(
      2000,
    );
  });

  it("is over budget whenever more items were late than allowed, whatever the rounding", () => {
    // 21 of 400 late against 20 allowed: 105%; 201 of 4000 against 200: 100.5%, shown as 101%.
    expect(budgetUse({ withinPercent: 95, targetMs: 8000, late: 201, of: 4000 })).toMatchObject({
      over: true,
    });
    expect(budgetUse({ withinPercent: 95, targetMs: 8000, late: 20, of: 400 })).toMatchObject({
      spentPercent: 100,
      over: false,
    });
  });

  it("allows no late item when every item must be on time", () => {
    expect(budgetUse({ withinPercent: 100, targetMs: 8000, late: 0, of: 10 })).toEqual({
      late: 0,
      of: 10,
      allowed: 0,
      spentPercent: 0,
      over: false,
    });
    expect(budgetUse({ withinPercent: 100, targetMs: 8000, late: 1, of: 10 })).toEqual({
      late: 1,
      of: 10,
      allowed: 0,
      spentPercent: null,
      over: true,
    });
  });

  it("is not judged before any item was timed", () => {
    expect(budgetUse({ withinPercent: 95, targetMs: 8000, late: 0, of: 0 })).toBeNull();
  });
});

describe("objectives", () => {
  it("are met at or under target and not judged before anything was measured", () => {
    expect(objectiveMet({ key: "on_air_p95", targetMs: 8000, measuredMs: 8000 })).toBe(true);
    expect(objectiveMet({ key: "on_air_p95", targetMs: 8000, measuredMs: 8001 })).toBe(false);
    expect(objectiveMet({ key: "on_air_p95", targetMs: 8000, measuredMs: null })).toBeNull();
  });
});

describe("verdict", () => {
  it("says nothing has been measured when no matchday has run", () => {
    expect(verdict(idle())).toEqual({
      tone: "neutral",
      text: "Nothing measured yet: no matchday has run since the platform last started. Start one from Match Live and this statement fills in as it plays.",
    });
  });

  it("leads with the service levels, the budget and the cost of a finished run", () => {
    expect(verdict(report())).toEqual({
      tone: "green",
      text: "The last matchday held its service levels: on air within 6.0 s for 95% of items, against 8.0 s. 0 of 40 items late, 0% of the error budget spent. It cost $0.0938.",
    });
  });

  it("names the miss while a run is under way", () => {
    const missing = report({
      objectives: [
        { key: "on_air_p50", targetMs: 4000, measuredMs: 11_635 },
        { key: "on_air_p95", targetMs: 8000, measuredMs: 12_664 },
        { key: "correction_p95", targetMs: 10000, measuredMs: null },
      ],
      budget: { withinPercent: 95, targetMs: 8000, late: 6, of: 6 },
      onAir: spread(6, 11_635, 12_664),
      matches: [match("m42", { state: "running" })],
    });

    expect(verdict(missing)).toEqual({
      tone: "red",
      text: "The matchday is missing the on-air median (11.6 s against 4.0 s) and the on-air 95th percentile (12.7 s against 8.0 s). 6 of 6 items late, the error budget spent 20 times over. It has cost $0.0469 so far.",
    });
  });

  it("says when every item had to be on time and one was not", () => {
    const strict = report({ budget: { withinPercent: 100, targetMs: 8000, late: 1, of: 40 } });

    expect(verdict(strict).text).toContain("1 of 40 items late, with no late item allowed");
  });

  it("waits for the first item while a run has timed none", () => {
    const early = report({
      objectives: idle().objectives,
      budget: idle().budget,
      onAir: spread(0, null, null),
      matches: [match("m42", { state: "running", partners: [] })],
    });

    expect(verdict(early)).toEqual({
      tone: "neutral",
      text: "The matchday is running; no item has gone on air without an editor yet. It has cost $0.0469 so far.",
    });
  });
});
