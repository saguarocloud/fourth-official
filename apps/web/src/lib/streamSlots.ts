/**
 * Open live streams per client, so one client cannot hold every stream the match API allows.
 * Counted per web replica, in memory: a bound on abuse, not an exact quota.
 */

export interface StreamSlots {
  /** A release function for the slot, or null when the client already holds its share. */
  claim(client: string): (() => void) | null;
}

export function streamSlots(perClient: number): StreamSlots {
  const open = new Map<string, number>();
  return {
    claim(client) {
      const held = open.get(client) ?? 0;
      if (held >= perClient) return null;
      open.set(client, held + 1);
      let released = false;
      return () => {
        if (released) return;
        released = true;
        const left = (open.get(client) ?? 1) - 1;
        if (left <= 0) open.delete(client);
        else open.set(client, left);
      };
    },
  };
}

/** The client's address as the Container Apps ingress appended it: the last X-Forwarded-For
 * entry. Earlier entries are whatever the client claimed, so they are never trusted.
 *
 * This holds while the ingress is the only proxy in front of the web app. Put a CDN or Front
 * Door in front and the last entry becomes that proxy, so every client would share one bucket:
 * count trusted hops from the end instead. */
export function clientOf(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for");
  const last = forwarded?.split(",").at(-1)?.trim();
  return last ? network(last) : "direct";
}

const HEXTETS = 8;
const PREFIX_HEXTETS = 4;

/** An IPv6 address counted by its /64: one subscriber is usually handed a whole /64, so counting
 * single addresses would let one client take a fresh share per address. IPv4 is kept as it is. */
function network(address: string): string {
  const bare = address.replace(/^\[|\]$/g, "").toLowerCase();
  if (!bare.includes(":")) return bare;
  const [head = "", tail] = bare.split("::");
  const front = head ? head.split(":") : [];
  const back = tail ? tail.split(":") : [];
  const zeros =
    tail === undefined ? [] : Array<string>(HEXTETS - front.length - back.length).fill("0");
  const prefix = [...front, ...zeros, ...back].slice(0, PREFIX_HEXTETS);
  return `${prefix.map((h) => h.replace(/^0+(?=.)/, "")).join(":")}::/64`;
}
