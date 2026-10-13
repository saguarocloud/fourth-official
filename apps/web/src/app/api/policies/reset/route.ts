import { forward } from "@/lib/policyForward";
import { parseReset } from "@/lib/policyRequests";
import { declaresMoreThan, fromTheStudio, jsonBody, refuse } from "@/lib/studioRequest";

const MAX_RESET_BYTES = 1024;

/** Every partner's policy back to the release's, as its next version. */
export async function POST(request: Request): Promise<Response> {
  if (!fromTheStudio(request)) return refuse(403, "Policies are reset from the studio.");
  if (declaresMoreThan(request, MAX_RESET_BYTES)) return refuse(413, "That reset is too large.");
  const reset = parseReset(await jsonBody(request, MAX_RESET_BYTES));
  if (reset === null) return refuse(422, "A reset needs a reason.");
  return forward("/api/policies/reset", reset);
}
