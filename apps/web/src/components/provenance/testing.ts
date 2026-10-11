/** Test doubles for Provenance: the signed records recorded from the m42 replay. */
import type { ProvenanceAnswer } from "@/domain/provenance";
import fixture from "@/fixtures/provenance-m42.json";

const RECORDED = fixture as unknown as Record<string, ProvenanceAnswer>;
const STUDIO_KEY = "https://kv-fo.vault.azure.net/keys/provenance/0123456789abcdef";

/** The recorded answers as the deployed API gives them: signed with the studio's Key Vault key.
 * The web app never checks a signature itself; it shows the API's verdict. */
export const ANSWERS: Record<string, ProvenanceAnswer> = Object.fromEntries(
  Object.entries(RECORDED).map(([id, answer]) => [
    id,
    { ...answer, provenance: { ...answer.provenance!, algorithm: "ES256", keyId: STUDIO_KEY } },
  ]),
);

/** The answers as recorded, signed with the local development key. */
export const DEVELOPMENT = RECORDED;

export const ON_AIR_ID = "it-northlight-sport-in-m42-goal-HCY-s0287-a1-v1";
export const RETRACTED_ID = "it-northlight-sport-in-m42-goal-HCY-s1702-a1-v1";
export const AMENDED_ID = "it-northlight-sport-in-m42-goal-HCY-s2044-a1-v2";
export const HELD_ID = "it-tribuna-austral-in-m42-goal-HCY-s0287-a1-v1";
