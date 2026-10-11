/** A demo match id (`m42`): checked before it is ever put in a URL, in the browser or the proxy. */
const MATCH_ID = /^m[0-9]{1,12}$/;

export function isMatchId(value: string): boolean {
  return MATCH_ID.test(value);
}
