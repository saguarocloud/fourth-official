import type { TenantItemEntry } from "@/contracts/feed";

/** A lower third: the partner's headline and line, with its AI label exactly as its policy
 * writes it (and none when the policy shows none). */
export function LowerThird({ item }: { item: TenantItemEntry }) {
  const content = item.overlay.content;
  if (content.template !== "lower_third") return null;
  const label = item.overlay.disclosure?.label ?? null;
  return (
    <div className="gfx gfx-third">
      <div className="gfx-third__headline">
        <span lang={item.overlay.locale}>{content.headline}</span>
        {label && <span className="gfx-badge">{label}</span>}
      </div>
      <p className="gfx-third__line" lang={item.overlay.locale}>
        {content.line}
      </p>
    </div>
  );
}

/** A correction strap: the most urgent graphic, preempting the lower third. */
export function CorrectionStrap({ item }: { item: TenantItemEntry }) {
  const content = item.overlay.content;
  if (content.template !== "correction_strap") return null;
  const { text } = content;
  const [lead, ...rest] = text.split(": ");
  return (
    <div className="gfx gfx-strap" lang={item.overlay.locale}>
      {rest.length ? (
        <>
          <strong className="gfx-strap__lead">{lead}</strong>
          <span>{rest.join(": ")}</span>
        </>
      ) : (
        <span>{text}</span>
      )}
    </div>
  );
}

/** The score bug: both clubs, the score as the partner's market writes it, and the clock: the
 * running match clock when there is one, else the time the score changed; null shows no time. */
export function ScoreBug({
  item,
  clock: running,
}: {
  item: TenantItemEntry;
  clock?: string | null;
}) {
  const content = item.overlay.content;
  if (content.template !== "score_bug") return null;
  const { home, away, score, clock: changed } = content;
  const clock = running === undefined ? changed : running;
  return (
    <div className="gfx gfx-bug">
      <span className="gfx-bug__club">{home}</span>
      <span className="gfx-bug__score tabular">{score}</span>
      <span className="gfx-bug__club">{away}</span>
      {clock !== null && <span className="gfx-bug__clock tabular">{clock}</span>}
    </div>
  );
}
