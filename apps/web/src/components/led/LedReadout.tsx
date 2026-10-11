import { layoutText } from "@/lib/led/glyphs";

export type LedTone = "green" | "red" | "amber" | "blue" | "violet" | "white";

const DOT_GAP = 1;

interface LedReadoutProps {
  /** Characters to light. Supports digits, A–Z and match marks (`: . , + - ' % / $`). */
  readonly text: string;
  /** Spoken alternative when the lit text is an abbreviation (e.g. a club code). */
  readonly label?: string;
  readonly tone?: LedTone;
  /** Dot diameter in CSS pixels; whole numbers keep every dot on the pixel grid. */
  readonly dotSize?: 2 | 3 | 4 | 5 | 6;
  readonly className?: string;
}

/**
 * A dot-matrix readout in the manner of the fourth official's LED board. Unlit dots stay faintly
 * visible, as on the physical board, so the readout keeps its shape when values change.
 */
export function LedReadout({
  text,
  label,
  tone = "white",
  dotSize = 3,
  className,
}: LedReadoutProps) {
  const matrix = layoutText(text);
  const pitch = dotSize + DOT_GAP;
  const radius = dotSize / 2;
  const width = Math.max(matrix.columns * pitch - DOT_GAP, 0);
  const height = matrix.rows * pitch - DOT_GAP;

  return (
    <svg
      role="img"
      aria-label={label ?? text}
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      data-tone={tone}
      className={["led", className].filter(Boolean).join(" ")}
    >
      {matrix.dots.map((dot) => (
        <circle
          key={`${dot.x}-${dot.y}`}
          cx={dot.x * pitch + radius}
          cy={dot.y * pitch + radius}
          r={radius}
          data-lit={dot.lit}
        />
      ))}
    </svg>
  );
}
