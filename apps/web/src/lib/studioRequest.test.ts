import { describe, expect, it } from "vitest";

import { jsonBody } from "./studioRequest";

const CHUNK = new TextEncoder().encode(`"${"x".repeat(98)}"`);

// A body sent in chunks, with no length declared, that counts how much of it was read.
function streamed(chunks: number): { request: Request; read: () => number } {
  let pulled = 0;
  const body = new ReadableStream<Uint8Array>({
    pull(controller) {
      if (pulled === chunks) return controller.close();
      pulled += 1;
      controller.enqueue(CHUNK);
    },
  });
  const request = new Request("http://localhost/api", {
    method: "POST",
    body,
    duplex: "half",
  } as RequestInit);
  return { request, read: () => pulled };
}

describe("jsonBody", () => {
  it("reads a JSON body within the limit", async () => {
    const { request } = streamed(1);

    expect(await jsonBody(request, 1000)).toBe("x".repeat(98));
  });

  it("stops reading a body once it passes the limit", async () => {
    const { request, read } = streamed(50);

    expect(await jsonBody(request, 250)).toBeNull();
    expect(read()).toBeLessThan(10);
  });

  it("refuses a body that is not JSON", async () => {
    const request = new Request("http://localhost/api", { method: "POST", body: "{nope" });

    expect(await jsonBody(request, 1000)).toBeNull();
  });
});
