/** Test doubles for Provenance: the signed records recorded from the m42 replay. */
import type { ProvenanceAnswer } from "@/domain/provenance";
import fixture from "@/fixtures/provenance-m42.json";

export const ANSWERS = fixture as unknown as Record<string, ProvenanceAnswer>;

export const ON_AIR_ID = "it-northlight-sport-in-m42-goal-HCY-s0287-a1-v1";
export const RETRACTED_ID = "it-northlight-sport-in-m42-goal-HCY-s1702-a1-v1";
export const AMENDED_ID = "it-northlight-sport-in-m42-goal-HCY-s2044-a1-v2";
export const HELD_ID = "it-tribuna-austral-in-m42-goal-HCY-s0287-a1-v1";
