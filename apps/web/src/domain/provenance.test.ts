import { describe, expect, it } from "vitest";

import type { FeedEntry } from "@/contracts/feed";
import type { ProvenanceRecord } from "@/contracts/provenance";
import feedM42 from "@/fixtures/feed-m42-partners.json";
import fixture from "@/fixtures/provenance-m42.json";

import { emptyBroadcast, foldBroadcast } from "./broadcast";

import {
  authorOf,
  itemsOnRecord,
  lifeOf,
  parseAnswer,
  type ProvenanceAnswer,
  sealOf,
  signerOf,
} from "./provenance";

const ANSWERS = fixture as unknown as Record<string, ProvenanceAnswer>;
const ON_AIR = ANSWERS["it-northlight-sport-in-m42-goal-HCY-s0287-a1-v1"]!;
const RETRACTED = ANSWERS["it-northlight-sport-in-m42-goal-HCY-s1702-a1-v1"]!;
const AMENDED = ANSWERS["it-northlight-sport-in-m42-goal-HCY-s2044-a1-v2"]!;
const HELD = ANSWERS["it-tribuna-austral-in-m42-goal-HCY-s0287-a1-v1"]!;

function recordOf(answer: ProvenanceAnswer): ProvenanceRecord {
  return answer.provenance!.record;
}

function withRecord(answer: ProvenanceAnswer, change: Partial<ProvenanceRecord>): ProvenanceRecord {
  return { ...recordOf(answer), ...change };
}

describe("parseAnswer", () => {
  it("accepts every recorded answer as it came", () => {
    for (const answer of Object.values(ANSWERS)) expect(parseAnswer(answer)).toEqual(answer);
  });

  it("accepts an answer with no record, as the API gives for one it cannot read", () => {
    const answer = { provenance: null, verification: { valid: false, reason: "unreadable" } };
    expect(parseAnswer(answer)).toEqual(answer);
  });

  it.each([
    [
      "a verdict of valid with no record behind it",
      { provenance: null, verification: { valid: true, reason: null } },
    ],
    [
      "a label that is not text",
      {
        ...ON_AIR,
        provenance: {
          ...ON_AIR.provenance,
          record: {
            ...recordOf(ON_AIR),
            disclosure: { label: { x: 1 }, mode: "label-all", reason: "ai_generated" },
          },
        },
      },
    ],
    [
      "an issue time that is not a time",
      {
        ...ON_AIR,
        provenance: {
          ...ON_AIR.provenance,
          record: { ...recordOf(ON_AIR), issuedAt: "yesterday" },
        },
      },
    ],
    [
      "a rejection with no reason",
      {
        ...ON_AIR,
        provenance: {
          ...ON_AIR.provenance,
          record: {
            ...recordOf(ON_AIR),
            approval: {
              decision: "rejected",
              editor: "T. Ibarra",
              decidedAt: "2026-10-11T15:04:00.000Z",
              reason: null,
            },
          },
        },
      },
    ],
    ["nothing", null],
    ["a string", "valid"],
    ["no verification", { provenance: ON_AIR.provenance }],
    [
      "a verdict that is not a boolean",
      { ...ON_AIR, verification: { valid: "yes", reason: null } },
    ],
    [
      "a record with no claims",
      {
        ...ON_AIR,
        provenance: { ...ON_AIR.provenance, record: { ...recordOf(ON_AIR), claims: [] } },
      },
    ],
    [
      "an unknown state",
      {
        ...ON_AIR,
        provenance: { ...ON_AIR.provenance, record: { ...recordOf(ON_AIR), state: "live" } },
      },
    ],
    [
      "an unknown algorithm",
      { ...ON_AIR, provenance: { ...ON_AIR.provenance, algorithm: "none" } },
    ],
    [
      "a claim with no evidence",
      {
        ...ON_AIR,
        provenance: {
          ...ON_AIR.provenance,
          record: { ...recordOf(ON_AIR), claims: [{ text: "x" }] },
        },
      },
    ],
  ])("refuses %s", (_, value) => {
    expect(parseAnswer(value)).toBeNull();
  });
});

describe("authorOf", () => {
  it("names a template as code, not as a model", () => {
    expect(authorOf(recordOf(ON_AIR).localized)).toBe("A template, in code");
  });

  it("names the model, the agent and the prompt version that wrote it", () => {
    const by = {
      agent: "explainer",
      model: "gpt-5-mini",
      producedBy: "model",
      promptVersion: "v1.3",
    } as const;
    expect(authorOf(by)).toBe("gpt-5-mini, as the explainer agent, prompt v1.3");
  });
});

describe("sealOf", () => {
  it("says a record is signed and unchanged when the check holds under the studio's key", () => {
    const signed = { ...ON_AIR.provenance!, algorithm: "ES256" as const };
    expect(sealOf({ ...ON_AIR, provenance: signed })).toEqual({
      tone: "verified",
      title: "Signed and unchanged",
      detail: null,
    });
  });

  it("never lets a development key pass for the studio's", () => {
    expect(sealOf(ON_AIR)).toEqual({
      tone: "development",
      title: "Unchanged, signed with a development key",
      detail: "The signature holds, but a local key signed it, not the studio's production key.",
    });
  });

  it("says a record does not verify, and why", () => {
    const failed = {
      ...ON_AIR,
      verification: { valid: false, reason: "the signature does not match" },
    };
    expect(sealOf(failed)).toEqual({
      tone: "failed",
      title: "Does not verify",
      detail: "the signature does not match",
    });
  });

  it("gives a reason even when the API gave none", () => {
    const failed = { ...ON_AIR, verification: { valid: false, reason: null } };
    expect(sealOf(failed).detail).toBe("The record could not be checked.");
  });
});

describe("signerOf", () => {
  it("names the studio's Key Vault key for ES256", () => {
    const signed = {
      ...ON_AIR.provenance!,
      algorithm: "ES256" as const,
      keyId: "https://kv-x.vault.azure.net/keys/provenance/0123abcd",
    };
    expect(signerOf(signed)).toBe("The studio's key in Azure Key Vault (ES256)");
  });

  it("calls a local key what it is: a development key", () => {
    expect(signerOf(ON_AIR.provenance!)).toBe("A local development key (HS256)");
  });
});

describe("lifeOf", () => {
  it("tells an on-air item's life: written, checked, localised, aired", () => {
    expect(lifeOf(recordOf(ON_AIR)).map((s) => [s.label, s.tone])).toEqual([
      ["Written", "step"],
      ["Checked", "step"],
      ["Localised", "step"],
      ["On air", "aired"],
    ]);
  });

  it("says who wrote it and which insight it explains", () => {
    const [written] = lifeOf(recordOf(ON_AIR));
    expect(written!.detail).toBe("A template, in code · insight in-m42-goal-HCY-s0287-a1");
  });

  it("counts the verifier's attempts and the findings it refused", () => {
    const record = withRecord(ON_AIR, {
      attempts: [
        {
          agent: "explainer",
          model: "gpt-5-mini",
          number: 1,
          outcome: "failed",
          findings: ["BARE_NUMBER", "TOO_LONG"],
          error: null,
        },
        {
          agent: "explainer",
          model: "gpt-5-mini",
          number: 2,
          outcome: "passed",
          findings: [],
          error: null,
        },
      ],
    });
    const checked = lifeOf(record).find((s) => s.label === "Checked")!;
    expect(checked.detail).toBe(
      "Passed the verifier on attempt 2 of 2; refused before: BARE_NUMBER, TOO_LONG",
    );
  });

  it("says when the verifier passed it first time", () => {
    const checked = lifeOf(recordOf(ON_AIR)).find((s) => s.label === "Checked")!;
    expect(checked.detail).toBe("Passed the verifier on attempt 1 of 1");
  });

  it("names the language it was put into and by whom", () => {
    const localised = lifeOf(recordOf(HELD)).find((s) => s.label === "Localised")!;
    expect(localised.detail).toBe("es-MX, by a template, in code");
  });

  it("holds an item awaiting its editor", () => {
    expect(lifeOf(recordOf(HELD)).at(-1)).toEqual({
      label: "Held",
      detail: "Off air until the partner's duty editor decides",
      tone: "held",
    });
  });

  it("records who approved an item and when", () => {
    const record = withRecord(HELD, {
      state: "on_air",
      approval: {
        decision: "approved",
        editor: "T. Ibarra",
        decidedAt: "2026-10-11T15:04:00.000Z",
      },
    });
    expect(lifeOf(record).slice(-2)).toEqual([
      { label: "Approved", detail: "By T. Ibarra at 15:04:00 UTC", tone: "step" },
      { label: "On air", detail: "Aired as approved", tone: "aired" },
    ]);
  });

  it("records who rejected an item and why", () => {
    const record = withRecord(HELD, {
      state: "rejected",
      approval: {
        decision: "rejected",
        editor: "T. Ibarra",
        decidedAt: "2026-10-11T15:04:00.000Z",
        reason: "Not our tone",
      },
    });
    expect(lifeOf(record).slice(-2)).toEqual([
      {
        label: "Rejected",
        detail: "By T. Ibarra at 15:04:00 UTC: “Not our tone”",
        tone: "dropped",
      },
      { label: "Kept off air", detail: "Never aired", tone: "dropped" },
    ]);
  });

  it("ends a retracted item pulled, by the correction that pulled it", () => {
    expect(lifeOf(recordOf(RETRACTED)).at(-1)).toEqual({
      label: "Pulled",
      detail: "Pulled by correction c-m42-01",
      tone: "retracted",
    });
  });

  it("marks an amended version as replaced", () => {
    const record = withRecord(ON_AIR, { state: "amended", corrections: ["c-m42-02"] });
    expect(lifeOf(record).at(-1)).toEqual({
      label: "Replaced",
      detail: "Superseded by a corrected version after correction c-m42-02",
      tone: "amended",
    });
  });

  it("says which version a remade item replaces", () => {
    const steps = lifeOf(recordOf(AMENDED));
    expect(steps.map((s) => s.label)).toEqual([
      "Written",
      "Remade",
      "Checked",
      "Localised",
      "On air",
    ]);
    expect(steps[1]).toEqual({
      label: "Remade",
      detail:
        "Version 2, replacing it-northlight-sport-in-m42-goal-HCY-s2044-a1-v1 after a correction",
      tone: "step",
    });
  });

  it("names every correction that touched an item", () => {
    const record = withRecord(RETRACTED, { corrections: ["c-m42-01", "c-m42-03"] });
    expect(lifeOf(record).at(-1)!.detail).toBe("Pulled by corrections c-m42-01, c-m42-03");
  });
});

describe("itemsOnRecord", () => {
  const DONE = foldBroadcast(feedM42 as unknown as FeedEntry[]);

  it("lists every partner's narrative item once, as its latest version, newest first", () => {
    const items = itemsOnRecord(DONE);

    expect(items.every((i) => i.localized !== null)).toBe(true);
    expect(new Set(items.map((i) => i.overlay.itemId)).size).toBe(items.length);
    const seqs = items.map((i) => i.entrySeq);
    expect(seqs).toEqual([...seqs].sort((a, b) => b - a));
    expect(items.map((i) => i.overlay.itemId)).toContain(
      "it-northlight-sport-in-m42-goal-HCY-s2044-a1-v2",
    );
  });

  it("lists nothing before anything is published", () => {
    expect(itemsOnRecord(emptyBroadcast(0))).toEqual([]);
  });
});
