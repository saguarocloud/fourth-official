import { connection } from "next/server";

const SERVICE_NAME = "fourth-official-web";
const DEFAULT_VERSION = "dev";

/** Liveness probe for Container Apps and post-deploy smoke tests. */
export async function GET(): Promise<Response> {
  // Without this the handler is prerendered at build time and probes would only test a static file.
  await connection();
  // APP_VERSION is baked into the image at build time from the git SHA.
  const version = process.env.APP_VERSION?.trim() || DEFAULT_VERSION;
  return Response.json(
    { status: "ok", service: SERVICE_NAME, version },
    { headers: { "Cache-Control": "no-store" } },
  );
}
