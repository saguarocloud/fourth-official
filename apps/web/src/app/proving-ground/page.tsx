/*
 * THESIS: the Release Gate's last call on a candidate, made as a go/no-go poll, rule by rule;
 * refuses a dashboard of metric cards and a bare pass/fail badge.
 * OWN-WORLD: the fourth official's board: panel blacks, hairlines, round lamps lit green for go and
 * red for no-go, the call itself lit on the LED board; a breached figure lit red, nothing else.
 * STORY: a platform engineer sees whether the candidate may ship, which rules said no and by how
 * much against production, then every measure side by side, the unsupported claims, and the
 * harness's own reference run over the full benchmark.
 * FIRST VIEWPORT: title and a verdict naming the failing rules; the call on the LED board at the
 * left; the seven-station poll at the right; the side-by-side table beneath.
 * FORM: go/no-go poll, candidate 3 of 7; seed d1a88d81.
 * FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the
 * verdict, and DESIGN.md.
 */
import { ProvingGroundScreen } from "@/components/proving/ProvingGroundScreen";

export default function ProvingGroundPage() {
  return <ProvingGroundScreen />;
}
