/* Generated from packages/contracts/schemas by `npm run contracts`. Do not edit. */

export type Aiwritten = boolean;
export type Minute = number;
export type Period = 1 | 2;
export type Second = number;
export type Entryseq = number;
export type Headline = string;
export type Matchid = string;
export type State = "on_air" | "pending_approval" | "rejected" | "retracted" | "amended";
export type Tenantid = "northlight-sport" | "tribuna-austral" | "rheinblick-sport";
/**
 * @maxItems 50
 */
export type Activity = WallActivity[];
export type Generatedat = string;
export type Correctionid = string;
export type Elapsedms = number | null;
export type Intext = string;
export type Itemscorrected = number;
export type Languages = number;
export type Matchid1 = string;
export type Outtext = string;
export type Partners = number;
export type Summary = string;
export type Away = string;
export type Corrections = number;
export type Home = string;
export type Items = number;
export type Matchid2 = string;
/**
 * @maxItems 8
 */
export type Onair = ("northlight-sport" | "tribuna-austral" | "rheinblick-sport")[];
export type Pendingapprovals = number;
export type Away1 = number;
export type Home1 = number;
export type State1 = "idle" | "running" | "finished" | "failed";
/**
 * @maxItems 100
 */
export type Matches = WallMatch[];

export interface MatchdayWall {
  activity: Activity;
  generatedAt: Generatedat;
  latestCorrection: WallCorrection | null;
  matches: Matches;
}
/**
 * A partner item as it was published, newest first on the wall.
 */
export interface WallActivity {
  aiWritten: Aiwritten;
  clock: MatchClock;
  entrySeq: Entryseq;
  headline: Headline;
  matchId: Matchid;
  state: State;
  tenantId: Tenantid;
}
/**
 * Elapsed match time within a period, as shown on a broadcast clock (`67:12`).
 */
export interface MatchClock {
  minute: Minute;
  period: Period;
  second: Second;
}
/**
 * The latest correction and what the corrections desk did about it.
 */
export interface WallCorrection {
  correctionId: Correctionid;
  elapsedMs: Elapsedms;
  eventClock: MatchClock | null;
  inText: Intext;
  itemsCorrected: Itemscorrected;
  languages: Languages;
  matchId: Matchid1;
  outText: Outtext;
  partners: Partners;
  receivedClock: MatchClock;
  summary: Summary;
}
/**
 * One match: its score and clock as last published, and its partners' items.
 */
export interface WallMatch {
  away: Away;
  clock: MatchClock | null;
  corrections: Corrections;
  home: Home;
  items: Items;
  matchId: Matchid2;
  onAir: Onair;
  pendingApprovals: Pendingapprovals;
  score: Score;
  state: State1;
}
export interface Score {
  away: Away1;
  home: Home1;
}
