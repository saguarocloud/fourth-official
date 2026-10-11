import { PARTNERS } from "@/domain/broadcast";
import type { Incident } from "@/domain/corrections";

const WIDTH = 1000;
const ROW = 44;

function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** The corrected event, the insights resting on it, and every partner item it reached, drawn as
 * one fan. The boards beneath are its text equivalent. */
export function ImpactStrip({ incident, replay }: { incident: Incident; replay: number }) {
  const insights = incident.insightIds;
  const changes = incident.changes;
  const rows = Math.max(changes.length, insights.length, 1);
  const height = rows * ROW + 24;
  const rowY = (i: number, of: number) => 12 + ROW / 2 + ((rows - of) * ROW) / 2 + i * ROW;
  const event = incident.correction.correction.targetEventId;
  const label = `${event} reached ${plural(insights.length, "insight", "insights")} and ${plural(changes.length, "partner item", "partner items")}`;
  return (
    <svg
      className="impact"
      viewBox={`0 0 ${WIDTH} ${height}`}
      role="img"
      aria-label={label}
      data-replay={replay > 0 || undefined}
      key={replay}
    >
      {insights.map((id, i) => (
        <line
          key={`e-${id}`}
          className="impact__edge"
          x1={150}
          y1={height / 2}
          x2={430}
          y2={rowY(i, insights.length)}
        />
      ))}
      {changes.map((change, i) => {
        const from = Math.max(0, insights.indexOf(change.action.insightId));
        return (
          <line
            key={`i-${change.action.itemId}`}
            className="impact__edge"
            data-action={change.action.action}
            x1={590}
            y1={rowY(from, insights.length)}
            x2={760}
            y2={rowY(i, changes.length)}
          />
        );
      })}
      <g data-node="event">
        <rect
          className="impact__node"
          data-kind="event"
          x={20}
          y={height / 2 - 14}
          width={130}
          height={28}
        />
        <text className="impact__text" x={85} y={height / 2 + 5} textAnchor="middle">
          {event.split("-")[1]}
        </text>
      </g>
      {insights.map((id, i) => (
        <g key={id} data-node="insight">
          <rect
            className="impact__node"
            x={430}
            y={rowY(i, insights.length) - 14}
            width={160}
            height={28}
          />
          <text
            className="impact__text"
            x={510}
            y={rowY(i, insights.length) + 5}
            textAnchor="middle"
          >
            {id.split("-").slice(2, 4).join(" ")}
          </text>
        </g>
      ))}
      {changes.map((change, i) => {
        const partner = PARTNERS.find((p) => p.id === change.action.tenantId);
        return (
          <g key={change.action.itemId} data-node="item" data-action={change.action.action}>
            <rect
              className="impact__node"
              data-kind="item"
              x={760}
              y={rowY(i, changes.length) - 14}
              width={220}
              height={28}
            />
            <text
              className="impact__text"
              x={870}
              y={rowY(i, changes.length) + 5}
              textAnchor="middle"
            >
              {`${partner?.code ?? change.action.tenantId} · ${change.action.locale}`}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
