import { memo } from "react";

import { layoutText, type Dot } from "@/lib/led/glyphs";

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

/** One circle per dot as a single path: two arcs drawn from the dot's left edge. */
function dotsPath(dots: readonly Dot[], pitch: number, radius: number): string {
  return dots
    .map((dot) => {
      const cx = dot.x * pitch + radius;
      const cy = dot.y * pitch + radius;
      return `M${cx - radius} ${cy}a${radius} ${radius} 0 1 0 ${radius * 2} 0a${radius} ${radius} 0 1 0 ${-radius * 2} 0`;
    })
    .join("");
}

/**
 * A dot-matrix readout in the manner of the fourth official's LED board. Unlit dots stay faintly
 * visible, as on the physical board, so the readout keeps its shape when values change. All dots
 * are drawn as two paths (lit and unlit) to keep the DOM small.
 */
function LedReadoutImpl({ text, label, tone = "white", dotSize = 3, className }: LedReadoutProps) {
  const matrix = layoutText(text);
  const pitch = dotSize + DOT_GAP;
  const radius = dotSize / 2;
  const width = Math.max(matrix.columns * pitch - DOT_GAP, 0);
  const height = matrix.rows * pitch - DOT_GAP;
  const lit = matrix.dots.filter((dot) => dot.lit);
  const unlit = matrix.dots.filter((dot) => !dot.lit);

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
      <path d={dotsPath(unlit, pitch, radius)} data-lit="false" />
      <path d={dotsPath(lit, pitch, radius)} data-lit="true" />
    </svg>
  );
}

export const LedReadout = memo(LedReadoutImpl);
