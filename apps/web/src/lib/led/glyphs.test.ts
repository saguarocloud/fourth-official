import { describe, expect, it } from "vitest";

import { GLYPHS, GLYPH_HEIGHT, GLYPH_WIDTH, layoutText } from "./glyphs";

describe("dot-matrix glyphs", () => {
  it("defines every glyph as a 5×7 grid of dots", () => {
    for (const [char, rows] of Object.entries(GLYPHS)) {
      expect(rows, char).toHaveLength(GLYPH_HEIGHT);
      for (const row of rows) {
        expect(row, char).toMatch(new RegExp(`^[01]{${GLYPH_WIDTH}}$`));
      }
    }
  });

  it("covers digits, letters and the marks match data needs", () => {
    for (const char of "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ:.,+-'%/$? ") {
      expect(GLYPHS, char).toHaveProperty([char]);
    }
  });

  it("draws distinct digits", () => {
    const digits = "0123456789".split("").map((d) => GLYPHS[d]?.join(""));
    expect(new Set(digits).size).toBe(10);
  });
});

describe("layoutText", () => {
  it("places glyphs one dot apart", () => {
    const layout = layoutText("12");

    expect(layout.columns).toBe(GLYPH_WIDTH * 2 + 1);
    expect(layout.rows).toBe(GLYPH_HEIGHT);
    expect(layout.dots).toHaveLength(layout.columns * layout.rows);
  });

  it("keeps a fixed width per character so ticking clocks never shift", () => {
    expect(layoutText("10:00").columns).toBe(layoutText("11:11").columns);
  });

  it("lights exactly the dots of the glyph", () => {
    const lit = layoutText("1")
      .dots.filter((d) => d.lit)
      .map((d) => `${d.x},${d.y}`);
    const expected = GLYPHS["1"]!.flatMap((row, y) =>
      row.split("").flatMap((bit, x) => (bit === "1" ? [`${x},${y}`] : [])),
    );

    expect(lit).toEqual(expected);
  });

  it("is case-insensitive", () => {
    expect(layoutText("hcy")).toEqual(layoutText("HCY"));
  });

  it("renders unsupported characters as a question mark rather than dropping them", () => {
    expect(layoutText("é")).toEqual(layoutText("?"));
  });

  it("returns an empty matrix for empty text", () => {
    expect(layoutText("")).toEqual({ columns: 0, rows: GLYPH_HEIGHT, dots: [] });
  });
});
