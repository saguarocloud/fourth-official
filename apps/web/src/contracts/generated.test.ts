// @vitest-environment node
import { readFile } from "node:fs/promises";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { CONTRACTS, render } from "../../scripts/contracts.mjs";

const here = join(process.cwd(), "src/contracts");

describe("generated contracts", () => {
  it.each(CONTRACTS as { schema: string; output: string }[])(
    "$output is what $schema generates, formatted as the project formats code",
    async ({ schema, output }) => {
      const target = join(here, output);
      expect(await readFile(target, "utf8")).toBe(await render(schema, target));
    },
  );
});
