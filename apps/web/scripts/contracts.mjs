// Generate TypeScript types from the contract JSON Schemas (the Pydantic models are the source of
// truth; `make contracts` exports the schemas). Run `npm run contracts` after the schemas change; a
// test fails while the generated files are stale.
import { readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { compile } from "json-schema-to-typescript";

const here = dirname(fileURLToPath(import.meta.url));
const schemas = join(here, "../../../packages/contracts/schemas");
export const CONTRACTS = [
  { schema: "feed-entry.schema.json", output: "feed.ts" },
  { schema: "signed-provenance.schema.json", output: "provenance.ts" },
];
export const BANNER =
  "/* Generated from packages/contracts/schemas by `npm run contracts`. Do not edit. */";

export async function generate(name) {
  const schema = JSON.parse(await readFile(join(schemas, name), "utf8"));
  // The $id is a canonical URL, not a location: never let the compiler try to fetch it.
  delete schema.$id;
  return compile(schema, schema.title, {
    bannerComment: BANNER,
    additionalProperties: false,
    strictIndexSignatures: true,
    // Array length limits are enforced where data is validated (the server), not in types.
    maxItems: -1,
    format: true,
    style: { printWidth: 100 },
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  for (const { schema, output } of CONTRACTS) {
    const target = join(here, "../src/contracts", output);
    await writeFile(target, await generate(schema));
    console.log(`wrote ${target}`);
  }
}
