import { PARTNERS, type PartnerId } from "@/domain/broadcast";

interface PartnerKeysProps {
  readonly current: PartnerId;
  /** Partners with a graphic on air now: their tally is lit. */
  readonly onAir: ReadonlySet<PartnerId>;
  readonly onChoose: (partner: PartnerId) => void;
}

/** One key per partner, numbered 1 to 3 like a vision mixer's bus. */
export function PartnerKeys({ current, onAir, onChoose }: PartnerKeysProps) {
  return (
    <div role="group" aria-label="Partner on the monitor" className="partner-keys">
      {PARTNERS.map((p) => (
        <button
          key={p.id}
          type="button"
          className="partner-key"
          aria-pressed={p.id === current}
          aria-keyshortcuts={p.key}
          onClick={() => onChoose(p.id)}
        >
          <span className="partner-key__cap" aria-hidden="true">
            {p.key}
          </span>
          <span className="partner-key__name">{p.name}</span>
          <span className="partner-key__code" aria-hidden="true">
            {p.code}
          </span>
          <span className="partner-key__language">{p.language}</span>
          <span
            className="partner-key__tally"
            data-lit={onAir.has(p.id) || undefined}
            aria-hidden="true"
          />
          {onAir.has(p.id) && <span className="sr-only">, on air</span>}
        </button>
      ))}
    </div>
  );
}
