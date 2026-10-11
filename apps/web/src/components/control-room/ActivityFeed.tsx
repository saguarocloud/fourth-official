import { AiTag } from "@/components/ui/AiTag";
import { StatusLamp } from "@/components/ui/StatusLamp";
import type { ActivityEntry, Partner } from "@/domain/matchday";
import { formatMatchMinute } from "@/lib/format";

interface ActivityFeedProps {
  readonly entries: readonly ActivityEntry[];
  readonly partners: readonly Partner[];
}

/** Newest first. New entries are announced politely so a screen reader user is not interrupted. */
export function ActivityFeed({ entries, partners }: ActivityFeedProps) {
  const partnerName = new Map(partners.map((p) => [p.id, p.name]));

  return (
    <div role="log" aria-live="polite" aria-label="Live activity" className="activity">
      {entries.length === 0 ? (
        <p className="activity__empty">
          Published items, approvals and corrections appear here as the matches unfold.
        </p>
      ) : (
        <ol className="activity__list">
          {entries.map((entry) => (
            <li key={entry.id} className="activity__item" data-state={entry.state}>
              <time className="activity__time">
                {formatMatchMinute(entry.minute, entry.period)}
              </time>
              <p className="activity__text">{entry.text}</p>
              <p className="activity__meta">
                <StatusLamp state={entry.state} />
                {entry.aiGenerated && <AiTag />}
                <span>{entry.partnerId ? partnerName.get(entry.partnerId) : "All partners"}</span>
              </p>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
