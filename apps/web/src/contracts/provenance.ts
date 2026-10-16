/* Generated from packages/contracts/schemas by `npm run contracts`. Do not edit. */

export type Algorithm = "ES256" | "HS256";
export type Contenthash = string;
export type Keyid = string;
export type Decidedat = string;
export type Decision = "approved" | "rejected";
export type Editor = string;
export type Reason = string | null;
export type Agent = string;
export type Error = string | null;
/**
 * @maxItems 64
 */
export type Findings = (
  | "MOMENT_MISMATCH"
  | "MALFORMED_INSIGHT"
  | "UNSUPPORTED_CHARACTER"
  | "BARE_NUMBER"
  | "RAW_NAME"
  | "UNVERIFIED_NAME"
  | "UNKNOWN_WORD"
  | "FUTURE_WORDING"
  | "UNKNOWN_PLAYER"
  | "UNKNOWN_CLUB"
  | "PLAYER_NOT_IN_EVIDENCE"
  | "MINUTE_NOT_IN_EVIDENCE"
  | "SNAPSHOT_NOT_FOUND"
  | "UNDEFINED_VALUE"
  | "EVIDENCE_NOT_FOUND"
  | "FUTURE_EVIDENCE"
  | "FUTURE_MINUTE"
  | "VOIDED_EVIDENCE"
  | "SUPERSEDED_EVIDENCE"
  | "CLAIMS_CHANGED"
  | "REFERENCES_CHANGED"
  | "BLOCKED_TOPIC"
  | "TOO_LONG"
)[];
export type Model = string;
export type Number = number;
export type Outcome = "passed" | "failed" | "error";
/**
 * @maxItems 99
 */
export type Attempts = SignedAttempt[];
export type Agent1 = string;
export type Model1 = string;
export type Producedby = "model" | "template";
export type Promptversion = string;
/**
 * @minItems 1
 * @maxItems 8
 */
export type Claims = [ProvenanceClaim, ...ProvenanceClaim[]];
/**
 * @maxItems 64
 */
export type Eventids = string[];
/**
 * @maxItems 16
 */
export type Metricsnapshotids = string[];
export type Text = string;
/**
 * @maxItems 50
 */
export type Corrections = string[];
export type Label = string | null;
export type Mode = "label-all" | "label-unless-approved" | "eu-strict";
export type Reason1 = "ai_generated" | "ai_assisted_reviewed" | "data";
export type Feedentry = number;
export type Headline = string;
export type Insightid = string;
export type Issuedat = string;
export type Issuer = string;
export type Itemid = string;
export type Locale = "en-GB" | "es-MX" | "de-DE";
export type Matchid = string;
export type State = "on_air" | "pending_approval" | "rejected" | "retracted" | "amended";
export type Supersedes = string | null;
export type Tenantid = "northlight-sport" | "tribuna-austral" | "rheinblick-sport";
export type Version = number;
export type Signature = string;

/**
 * A record, the SHA-256 of its canonical bytes, and the studio's signature over that hash.
 */
export interface SignedProvenance {
  algorithm: Algorithm;
  contentHash: Contenthash;
  keyId: Keyid;
  record: ProvenanceRecord;
  signature: Signature;
}
export interface ProvenanceRecord {
  approval: Approval | null;
  attempts: Attempts;
  canonical: Provenance | null;
  claims: Claims;
  corrections: Corrections;
  disclosure: Disclosure | null;
  feedEntry: Feedentry;
  headline: Headline;
  insightId: Insightid;
  issuedAt: Issuedat;
  issuer: Issuer;
  itemId: Itemid;
  locale: Locale;
  localized: Provenance;
  matchId: Matchid;
  state: State;
  supersedes: Supersedes;
  tenantId: Tenantid;
  version: Version;
}
/**
 * A named editor's decision on an item before it goes on air.
 */
export interface Approval {
  decidedAt: Decidedat;
  decision: Decision;
  editor: Editor;
  reason?: Reason;
}
/**
 * An attempt as a record signs it: who drafted and how it ended. What the attempt cost is
 * operations, not provenance, and stays out, so a record's signed bytes never change shape.
 */
export interface SignedAttempt {
  agent: Agent;
  error: Error;
  findings: Findings;
  model: Model;
  number: Number;
  outcome: Outcome;
}
/**
 * Who produced the insight and how: recorded for every published item.
 */
export interface Provenance {
  agent: Agent1;
  model: Model1;
  producedBy: Producedby;
  promptVersion: Promptversion;
}
/**
 * A claim as the audience read it, and the evidence it rests on.
 */
export interface ProvenanceClaim {
  evidence: Evidence;
  text: Text;
}
export interface Evidence {
  eventIds: Eventids;
  metricSnapshotIds: Metricsnapshotids;
}
/**
 * How AI involvement is shown on an item: the label (rendered by code, never by a model).
 */
export interface Disclosure {
  label: Label;
  mode: Mode;
  reason: Reason1;
}
