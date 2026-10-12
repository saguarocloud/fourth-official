/** A partner item id (`it-northlight-sport-…-v1`): checked before it is ever put in a URL, in the
 * browser or the proxy. */
const ITEM_ID = /^it-[a-z]+(-[a-z]+)*-[A-Za-z0-9_-]{1,100}$/;
const MAX_LENGTH = 128;

export function isItemId(value: string): boolean {
  return value.length <= MAX_LENGTH && ITEM_ID.test(value);
}
