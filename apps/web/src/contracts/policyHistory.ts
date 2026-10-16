/* Generated from packages/contracts/schemas by `npm run contracts`. Do not edit. */

/**
 * @minItems 1
 * @maxItems 500
 */
export type Changes = [PolicyChange, ...PolicyChange[]];
export type Action = "bundled" | "edited" | "reset";
export type Changedat = string;
export type Editor = string;
/**
 * @maxItems 16
 */
export type Fields = (
  | "displayName"
  | "tone"
  | "preferTerms"
  | "avoidTerms"
  | "blockedTopics"
  | "approvalRequired"
  | "disclosureMode"
  | "latencyBudgetMs"
  | "maxItemsPerMinute"
  | "templates"
  | "correctionBehaviour"
)[];
export type Reason = string;
export type Tenantid = "northlight-sport" | "tribuna-austral" | "rheinblick-sport";
export type Version = number;
export type Tenantid1 = "northlight-sport" | "tribuna-austral" | "rheinblick-sport";
/**
 * @minItems 1
 * @maxItems 500
 */
export type Versions = [TenantPolicy, ...TenantPolicy[]];
/**
 * @maxItems 5
 */
export type Approvalrequired = ("insight" | "recap" | "stat" | "correction" | "score")[];
/**
 * @maxItems 50
 */
export type Avoidterms = string[];
/**
 * @maxItems 5
 */
export type Blockedtopics = (
  "injury_speculation" | "betting" | "transfer_rumour" | "referee_criticism" | "off_field"
)[];
export type Correctionbehaviour = "auto-amend" | "retract-and-notify" | "escalate";
export type Disclosuremode = "label-all" | "label-unless-approved" | "eu-strict";
export type Displayname = string;
export type Dutyeditor = string;
export type Latencybudgetms = number;
export type Locale = "en-GB" | "es-MX" | "de-DE";
export type Maxitemsperminute = number;
/**
 * @maxItems 50
 */
export type Preferterms = string[];
/**
 * @minItems 1
 * @maxItems 4
 */
export type Templates = [
  "lower_third" | "stat_card" | "correction_strap" | "score_bug",
  ...("lower_third" | "stat_card" | "correction_strap" | "score_bug")[]
];
export type Tenantid2 = "northlight-sport" | "tribuna-austral" | "rheinblick-sport";
/**
 * @minItems 1
 * @maxItems 6
 */
export type Tone = [string, ...string[]];
export type Version1 = number;

/**
 * One partner's policy versions, oldest first, each with the change that made it. Only the
 * newest are kept, so a history may start after version 1, but never skips one.
 */
export interface PolicyHistory {
  changes: Changes;
  tenantId: Tenantid1;
  versions: Versions;
}
/**
 * How one version came to be.
 */
export interface PolicyChange {
  action: Action;
  changedAt: Changedat;
  editor: Editor;
  fields: Fields;
  reason: Reason;
  tenantId: Tenantid;
  version: Version;
}
export interface TenantPolicy {
  approvalRequired: Approvalrequired;
  avoidTerms: Avoidterms;
  blockedTopics: Blockedtopics;
  correctionBehaviour: Correctionbehaviour;
  disclosureMode: Disclosuremode;
  displayName: Displayname;
  dutyEditor: Dutyeditor;
  latencyBudgetMs: Latencybudgetms;
  locale: Locale;
  maxItemsPerMinute: Maxitemsperminute;
  preferTerms: Preferterms;
  templates: Templates;
  tenantId: Tenantid2;
  tone: Tone;
  version: Version1;
}
