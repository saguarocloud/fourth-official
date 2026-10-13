import { describe, expect, it } from "vitest";

import type { PolicyHistory, TenantPolicy } from "@/contracts/policyHistory";
import fixture from "@/fixtures/policy-history-rheinblick.json";

import { changesOf, EDITABLE_FIELDS, parseHistory, toYaml, versionLine } from "./policy";

const HISTORY = fixture as unknown as PolicyHistory;
const [RELEASED, EDITED, RESET] = HISTORY.versions as [TenantPolicy, TenantPolicy, TenantPolicy];

describe("parseHistory", () => {
  it("accepts a history as the API sends it", () => {
    expect(parseHistory(fixture)).toEqual(fixture);
  });

  it.each([
    ["nothing", null],
    ["no versions", { ...HISTORY, versions: [] }],
    ["a change with no reason", { ...HISTORY, changes: [{ ...HISTORY.changes[0], reason: 7 }] }],
    ["an unknown action", { ...HISTORY, changes: [{ ...HISTORY.changes[0], action: "hacked" }] }],
    ["a policy with no templates", { ...HISTORY, versions: [{ ...RELEASED, templates: "all" }] }],
    ["versions and changes that disagree", { ...HISTORY, changes: HISTORY.changes.slice(1) }],
  ])("refuses %s", (_, value) => {
    expect(parseHistory(value)).toBeNull();
  });
});

describe("changesOf", () => {
  it("says what an edit changed, in words, before and after", () => {
    expect(changesOf(RELEASED, EDITED)).toEqual([
      {
        field: "avoidTerms",
        label: "Avoided terms",
        before: "Wahnsinn",
        after: "Wahnsinn, Skandal",
        added: ["Skandal"],
        removed: [],
      },
      {
        field: "approvalRequired",
        label: "Held for the duty editor",
        before: "Recaps",
        after: "Recaps, Insights",
        added: ["Insights"],
        removed: [],
      },
      { field: "maxItemsPerMinute", label: "Items a minute", before: "4", after: "3" },
    ]);
  });

  it("says nothing changed between identical policies", () => {
    expect(changesOf(RELEASED, { ...RELEASED, version: 9 })).toEqual([]);
  });

  it("names what a list lost as well as what it gained", () => {
    const after = { ...RELEASED, blockedTopics: ["betting", "referee_criticism"] } as TenantPolicy;

    expect(changesOf(RELEASED, after)[0]).toMatchObject({
      label: "Blocked topics",
      added: ["Criticism of referees"],
      removed: ["Injury speculation", "Transfer rumours", "Off the field"],
    });
  });

  it("does not count a list put in another order as a change", () => {
    const reordered = { ...RELEASED, templates: [...RELEASED.templates].reverse() } as TenantPolicy;

    expect(changesOf(RELEASED, reordered)).toEqual([]);
  });

  it("writes empty lists as none", () => {
    const before = { ...RELEASED, blockedTopics: [] } as TenantPolicy;

    expect(changesOf(before, RELEASED)[0]).toMatchObject({
      label: "Blocked topics",
      before: "None",
      after: "Injury speculation, Betting, Transfer rumours, Off the field",
    });
  });
});

describe("versionLine", () => {
  it("names who changed it, when and why", () => {
    expect(versionLine(HISTORY.changes[1]!)).toBe(
      "Edited by L. Vogt at 09:15 UTC: “Hold insights for the duty editor”",
    );
    expect(versionLine(HISTORY.changes[0]!)).toBe("Shipped with the release");
  });

  it("reads the time in UTC whatever offset it was written with", () => {
    const change = { ...HISTORY.changes[1]!, changedAt: "2026-10-12T11:15:00+02:00" };

    expect(versionLine(change)).toContain("at 09:15 UTC");
  });
});

describe("toYaml", () => {
  it("writes every field, strings quoted, so the studio's strict reader takes it back as is", () => {
    const yaml = toYaml(RESET);

    expect(yaml.split("\n")[0]).toBe('tenantId: "rheinblick-sport"');
    expect(yaml).toContain('tone: ["formal", "precise"]');
    expect(yaml).toContain("maxItemsPerMinute: 4");
    expect(yaml).toContain(
      'blockedTopics: ["injury_speculation", "betting", "transfer_rumour", "off_field"]',
    );
    expect(yaml.endsWith("\n")).toBe(true);
  });

  it("escapes what a term could hide", () => {
    const sly = { ...RESET, preferTerms: ['Tor"\nversion: 9'] } as TenantPolicy;

    expect(toYaml(sly)).toContain('preferTerms: ["Tor\\"\\nversion: 9"]');
  });
});

describe("EDITABLE_FIELDS", () => {
  it("lists the fields a studio editor may change, never who the policy belongs to", () => {
    const names = EDITABLE_FIELDS.map((f) => f.field);

    expect(names).toContain("disclosureMode");
    expect(names).not.toContain("tenantId");
    expect(names).not.toContain("locale");
    expect(names).not.toContain("dutyEditor");
  });
});
