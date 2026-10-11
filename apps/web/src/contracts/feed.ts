/* Generated from packages/contracts/schemas by `npm run contracts`. Do not edit. */

export type FeedEntry = ClockEntry | MomentEntry | InsightEntry | CorrectionEntry;
export type Asofseq = number;
export type Minute = number;
export type Period = 1 | 2;
export type Second = number;
export type Entryseq = number;
export type Kind = "clock";
export type Matchid = string;
export type Away = number;
export type Home = number;
export type Entryseq1 = number;
export type Kind1 = "moment";
export type Matchid1 = string;
export type Asofseq1 = number;
export type Club = string;
/**
 * @maxItems 64
 */
export type Eventids = string[];
export type Kind2 =
  | "goal"
  | "big_chance"
  | "red_card"
  | "var_overturn"
  | "pressing_collapse"
  | "pressing_surge"
  | "momentum_swing"
  | "tactical_shift";
export type Matchid2 = string;
/**
 * @maxItems 16
 */
export type Metricsnapshotids = string[];
export type Momentid = string;
export type After = number;
export type Aftersnapshotid = string;
export type Before = number;
export type Beforesnapshotid = string;
export type Metric =
  | "possession"
  | "field_tilt"
  | "passes"
  | "pass_completion"
  | "shots"
  | "shots_on_target"
  | "xg"
  | "ppda"
  | "pressing_intensity"
  | "momentum"
  | "control_chaos";
/**
 * @maxItems 4
 */
export type Shifts = MetricShift[];
/**
 * @minItems 1
 * @maxItems 99
 */
export type Attempts = [AttemptRecord, ...AttemptRecord[]];
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
)[];
export type Model = string;
export type Number = number;
export type Outcome = "passed" | "failed" | "error";
export type Entryseq2 = number;
export type Asofseq2 = number;
/**
 * @minItems 1
 * @maxItems 5
 */
export type Claims = [Claim, ...Claim[]];
export type Claimid = string;
/**
 * @maxItems 64
 */
export type Eventids1 = string[];
/**
 * @maxItems 16
 */
export type Metricsnapshotids1 = string[];
export type Text = string;
export type Type = "stat" | "comparison" | "causal" | "milestone";
export type Headline = string;
export type Insightid = string;
export type Locale = "en";
export type Matchid3 = string;
export type Momentid1 = string;
export type Agent1 = string;
export type Model1 = string;
export type Producedby = "model" | "template";
export type Promptversion = string;
export type Kind3 = "insight";
export type Matchid4 = string;
/**
 * @minItems 1
 * @maxItems 5
 */
export type Claims1 = [string, ...string[]];
export type Headline1 = string;
export type Claimid1 = string | null;
export type Code =
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
  | "SUPERSEDED_EVIDENCE";
export type Detail = string;
/**
 * @maxItems 64
 */
export type Findings1 = Finding[];
export type Insightid1 = string;
export type Matchid5 = string;
export type Passed = boolean;
export type Correction = EventVoided | EventAmended;
export type Correctionid = string;
export type Issuedat = string;
export type Kind4 = "EVENT_VOIDED";
export type Matchid6 = string;
export type Newversion = number;
export type Reason =
  "VAR_OFFSIDE" | "VAR_FOUL" | "VAR_HANDBALL" | "ACCREDITATION_PANEL" | "PROVIDER_RESTATEMENT";
export type Targeteventid = string;
export type Assistid = string | null;
export type Card = ("yellow" | "second_yellow" | "red") | null;
export type Owngoal = boolean | null;
export type Scorerid = string | null;
export type Correctionid1 = string;
export type Issuedat1 = string;
export type Kind5 = "EVENT_AMENDED";
export type Matchid7 = string;
export type Newversion1 = number;
export type Reason1 =
  "VAR_OFFSIDE" | "VAR_FOUL" | "VAR_HANDBALL" | "ACCREDITATION_PANEL" | "PROVIDER_RESTATEMENT";
export type Targeteventid1 = string;
export type Entryseq3 = number;
export type Intext = string;
export type Kind6 = "correction";
export type Matchid8 = string;
export type Outtext = string;
export type Summary = string;

/**
 * The match clock and score as published so far (corrections in force applied).
 */
export interface ClockEntry {
  asOfSeq: Asofseq;
  clock: MatchClock;
  entrySeq: Entryseq;
  kind: Kind;
  matchId: Matchid;
  score: Score;
}
/**
 * Elapsed match time within a period, as shown on a broadcast clock (`67:12`).
 */
export interface MatchClock {
  minute: Minute;
  period: Period;
  second: Second;
}
export interface Score {
  away: Away;
  home: Home;
}
export interface MomentEntry {
  entrySeq: Entryseq1;
  kind: Kind1;
  matchId: Matchid1;
  moment: Moment;
}
export interface Moment {
  asOfSeq: Asofseq1;
  clock: MatchClock;
  club: Club;
  eventIds: Eventids;
  kind: Kind2;
  matchId: Matchid2;
  metricSnapshotIds: Metricsnapshotids;
  momentId: Momentid;
  shifts: Shifts;
}
/**
 * A metric that moved: its value in a baseline snapshot and in the current one.
 */
export interface MetricShift {
  after: After;
  afterSnapshotId: Aftersnapshotid;
  before: Before;
  beforeSnapshotId: Beforesnapshotid;
  metric: Metric;
}
/**
 * A verified insight, its verdict, its rendered text and how it was reached.
 */
export interface InsightEntry {
  attempts: Attempts;
  entrySeq: Entryseq2;
  insight: Insight;
  kind: Kind3;
  matchId: Matchid4;
  rendered: RenderedInsight;
  verdict: Verdict;
}
/**
 * One try at explaining a moment: who drafted, and how it ended.
 */
export interface AttemptRecord {
  agent: Agent;
  error: Error;
  findings: Findings;
  model: Model;
  number: Number;
  outcome: Outcome;
}
export interface Insight {
  asOfSeq: Asofseq2;
  claims: Claims;
  headline: Headline;
  insightId: Insightid;
  locale: Locale;
  matchId: Matchid3;
  momentId: Momentid1;
  provenance: Provenance;
}
export interface Claim {
  claimId: Claimid;
  evidence: Evidence;
  text: Text;
  type: Type;
}
export interface Evidence {
  eventIds: Eventids1;
  metricSnapshotIds: Metricsnapshotids1;
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
 * The insight as a viewer reads it: plain text, rendered by code from the references.
 */
export interface RenderedInsight {
  claims: Claims1;
  headline: Headline1;
}
export interface Verdict {
  findings: Findings1;
  insightId: Insightid1;
  matchId: Matchid5;
  passed: Passed;
}
export interface Finding {
  claimId: Claimid1;
  code: Code;
  detail: Detail;
}
export interface CorrectionEntry {
  correction: Correction;
  entrySeq: Entryseq3;
  inText: Intext;
  kind: Kind6;
  matchId: Matchid8;
  outText: Outtext;
  summary: Summary;
}
/**
 * The event no longer stands (for example, a goal disallowed by VAR).
 */
export interface EventVoided {
  correctionId: Correctionid;
  issuedAt: Issuedat;
  kind: Kind4;
  matchId: Matchid6;
  newVersion: Newversion;
  reason: Reason;
  targetEventId: Targeteventid;
}
/**
 * The event stands, with corrected details (for example, a reassigned scorer).
 */
export interface EventAmended {
  changes: Amendment;
  correctionId: Correctionid1;
  issuedAt: Issuedat1;
  kind: Kind5;
  matchId: Matchid7;
  newVersion: Newversion1;
  reason: Reason1;
  targetEventId: Targeteventid1;
}
/**
 * Fields of the target event that change. Only the fields present on the wire change.
 */
export interface Amendment {
  assistId?: Assistid;
  card?: Card;
  clock?: MatchClock | null;
  ownGoal?: Owngoal;
  scorerId?: Scorerid;
}
