import { PARTNERS } from "@/domain/broadcast";
import type { Incident } from "@/domain/corrections";
import { plural } from "@/lib/plural";

const WIDTH = 1000;
const ROW = 44;

/** The correction, the insights resting on it, and every partner item it reached, drawn as one
 * fan. The boards beneath are its text equivalent. */
export function ImpactStrip({ incident, replay }: { incident: Incident; replay: number }) {
  const { insights, changes, correction } = incident;
  const rows = Math.max(changes.length, insights.length, 1);
  const height = rows * ROW + 24;
  const rowY = (i: number, of: number) => 12 + ROW / 2 + ((rows - of) * ROW) / 2 + i * ROW;
  const at = new Map(insights.map((insight, i) => [insight.id, i]));
  const label = `${correction.summary}: reached ${plural(insights.length, "insight", "insights")} and ${plural(changes.length, "partner item", "partner items")}`;
  return (
    <div className="impact__frame">
      <NarrowFan incident={incident} replay={replay} label={label} />
      <svg
        className="impact"
        data-layout="wide"
        viewBox={`0 0 ${WIDTH} ${height}`}
        role="img"
        aria-label={label}
        data-replay={replay > 0 || undefined}
      >
        {insights.map((insight, i) => (
          <line
            key={`e-${insight.id}`}
            className="impact__edge"
            x1={190}
            y1={height / 2}
            x2={400}
            y2={rowY(i, insights.length)}
          />
        ))}
        {changes.map((change, i) => {
          const from = at.get(change.action.insightId);
          return from === undefined ? null : (
            <line
              key={`i-${change.action.itemId}`}
              className="impact__edge"
              data-action={change.action.action}
              x1={600}
              y1={rowY(from, insights.length)}
              x2={740}
              y2={rowY(i, changes.length)}
            />
          );
        })}
        <g data-node="event">
          <title>{correction.summary}</title>
          <rect
            className="impact__node"
            data-kind="event"
            x={10}
            y={height / 2 - 14}
            width={180}
            height={28}
          />
          <text className="impact__text" x={100} y={height / 2 + 5} textAnchor="middle">
            {`${correction.outText} → ${correction.inText}`}
          </text>
        </g>
        {insights.map((insight, i) => (
          <g key={insight.id} data-node="insight">
            <title>{insight.id}</title>
            <rect
              className="impact__node"
              x={400}
              y={rowY(i, insights.length) - 14}
              width={200}
              height={28}
            />
            <text
              className="impact__text"
              x={500}
              y={rowY(i, insights.length) + 5}
              textAnchor="middle"
            >
              {insight.label}
            </text>
          </g>
        ))}
        {changes.map((change, i) => {
          const partner = PARTNERS.find((p) => p.id === change.action.tenantId);
          return (
            <g key={change.action.itemId} data-node="item" data-action={change.action.action}>
              <title>{change.action.itemId}</title>
              <rect
                className="impact__node"
                data-kind="item"
                x={740}
                y={rowY(i, changes.length) - 14}
                width={250}
                height={28}
              />
              <text
                className="impact__text"
                x={865}
                y={rowY(i, changes.length) + 5}
                textAnchor="middle"
              >
                {`${partner?.name ?? change.action.tenantId} · ${change.action.locale}`}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

const NARROW = 400;
const STEP = 40;

/** The same fan for a phone, top to bottom: the correction, its insights, then each partner. */
function NarrowFan({
  incident,
  replay,
  label,
}: {
  incident: Incident;
  replay: number;
  label: string;
}) {
  const { insights, changes, correction } = incident;
  const insightY = (i: number) => 92 + i * STEP;
  const itemsTop = insightY(insights.length) + 36;
  const itemY = (i: number) => itemsTop + i * STEP;
  const height = itemY(changes.length) + 8;
  const at = new Map(insights.map((insight, i) => [insight.id, i]));
  return (
    <svg
      className="impact"
      data-layout="narrow"
      viewBox={`0 0 ${NARROW} ${height}`}
      role="img"
      aria-label={label}
      data-replay={replay > 0 || undefined}
    >
      {insights.map((insight, i) => (
        <line
          key={`e-${insight.id}`}
          className="impact__edge"
          x1={40}
          y1={44}
          x2={40}
          y2={insightY(i)}
        />
      ))}
      {changes.map((change, i) => {
        const from = at.get(change.action.insightId);
        return from === undefined ? null : (
          <line
            key={`i-${change.action.itemId}`}
            className="impact__edge"
            data-action={change.action.action}
            x1={60}
            y1={insightY(from) + 14}
            x2={60}
            y2={itemY(i)}
          />
        );
      })}
      <g data-node="event">
        <rect className="impact__node" data-kind="event" x={10} y={16} width={380} height={28} />
        <text className="impact__text" x={200} y={35} textAnchor="middle">
          {`${correction.outText} → ${correction.inText}`}
        </text>
      </g>
      {insights.map((insight, i) => (
        <g key={insight.id} data-node="insight">
          <rect className="impact__node" x={20} y={insightY(i) - 14} width={360} height={28} />
          <text className="impact__text" x={200} y={insightY(i) + 5} textAnchor="middle">
            {insight.label}
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
              x={40}
              y={itemY(i) - 14}
              width={350}
              height={28}
            />
            <text className="impact__text" x={215} y={itemY(i) + 5} textAnchor="middle">
              {`${partner?.name ?? change.action.tenantId} · ${change.action.locale}`}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
