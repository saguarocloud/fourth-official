import type { Connection } from "./useLiveFeed";
import { WireItem } from "./WireItem";
import type { LiveMatch, RunState } from "@/domain/live";

interface LiveWireProps {
  readonly live: LiveMatch;
  readonly connection: Connection;
  readonly state: RunState;
}

/** The minute-by-minute wire: every moment, newest first, as it was verified and corrected. */
export function LiveWire({ live, connection, state }: LiveWireProps) {
  const waiting = connection === "connecting" && live.items.length === 0;
  return (
    <section aria-labelledby="wire-heading" className="live-wire">
      <h2 id="wire-heading" className="panel-heading">
        Minute by minute
      </h2>
      {connection === "reconnecting" && (
        <p className="live-wire__notice" role="status">
          Connection lost. Reconnecting; nothing will be missed.
        </p>
      )}
      <div role="log" aria-live="polite" aria-relevant="additions" aria-label="Verified moments">
        {waiting ? (
          <ol className="live-wire__list" aria-hidden="true">
            {[0, 1, 2].map((row) => (
              <li key={row} className="wire-item wire-item--skeleton">
                <span />
                <span />
              </li>
            ))}
          </ol>
        ) : live.items.length === 0 ? (
          <p className="live-wire__empty">
            {state === "idle"
              ? "Nothing yet. Start the matchday and each goal, chance, card, VAR decision and change in the press appears here, explained and verified before it is shown."
              : "The match is under way. The first verified moment will appear here."}
          </p>
        ) : (
          <ol className="live-wire__list">
            {live.items.map((item) => (
              <WireItem key={item.moment.momentId} item={item} />
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}
