/**
 * The product mark: the fourth official's board held up, a 3×5 dot grid with the top row lit red
 * (out) and the bottom row lit green (in).
 */
export function BrandMark() {
  const columns = [0, 1, 2];
  const rows = [0, 1, 2, 3, 4];
  const toneFor = (row: number) => (row === 0 ? "out" : row === 4 ? "in" : "off");
  return (
    <svg className="brand-mark" width="22" height="34" viewBox="0 0 22 34" aria-hidden="true">
      <rect x="0.5" y="0.5" width="21" height="33" rx="2" className="brand-mark__frame" />
      {rows.flatMap((row) =>
        columns.map((column) => (
          <circle
            key={`${row}-${column}`}
            cx={5 + column * 6}
            cy={5 + row * 6}
            r="2"
            data-tone={toneFor(row)}
          />
        )),
      )}
    </svg>
  );
}
