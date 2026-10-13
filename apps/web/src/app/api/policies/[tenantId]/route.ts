import { apiBase, UNAVAILABLE, UPSTREAM_TIMEOUT_MS } from "@/lib/matchApi";
import { forward } from "@/lib/policyForward";
import { MAX_EDIT_BYTES, parseEdit, TENANTS } from "@/lib/policyRequests";
import { declaresMoreThan, fromTheStudio, jsonBody, NO_STORE, refuse } from "@/lib/studioRequest";

interface Params {
  readonly tenantId: string;
}

/** A partner's policy history: every version and the change that made it (ADR-015). */
export async function GET(
  _request: Request,
  { params }: { params: Promise<Params> },
): Promise<Response> {
  const { tenantId } = await params;
  if (!TENANTS.has(tenantId)) return refuse(404, "No such partner.");
  try {
    const upstream = await fetch(`${apiBase()}/api/policies/${tenantId}`, {
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
    if (!upstream.ok) throw new Error(`match API answered ${upstream.status}`);
    return Response.json(await upstream.json(), { headers: NO_STORE });
  } catch {
    return Response.json(UNAVAILABLE, { status: 502, headers: NO_STORE });
  }
}

/** The partner's next policy, from Policy Studio's form or raw view. */
export async function POST(
  request: Request,
  { params }: { params: Promise<Params> },
): Promise<Response> {
  if (!fromTheStudio(request)) return refuse(403, "Policies are edited from the studio.");
  if (declaresMoreThan(request, MAX_EDIT_BYTES)) return refuse(413, "That edit is too large.");
  const { tenantId } = await params;
  if (!TENANTS.has(tenantId)) return refuse(404, "No such partner.");
  const edit = parseEdit(await jsonBody(request, MAX_EDIT_BYTES));
  if (edit === null) return refuse(422, "That edit cannot be sent: it needs a reason.");
  return forward(`/api/policies/${tenantId}`, edit);
}
