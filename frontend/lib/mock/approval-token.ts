const TOKEN_PATTERN = /^apr-([1-9]\d*)\.([A-Za-z0-9_-]{43})$/;
const BASE64URL = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

async function sha256Bytes(value: string): Promise<Uint8Array> {
  const bytes = new TextEncoder().encode(value);
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return new Uint8Array(digest);
}

function base64Url(bytes: Uint8Array): string {
  let output = "";
  for (let index = 0; index < bytes.length; index += 3) {
    const first = bytes[index] ?? 0;
    const second = bytes[index + 1];
    const third = bytes[index + 2];
    const block = (first << 16) | ((second ?? 0) << 8) | (third ?? 0);
    output += BASE64URL[(block >> 18) & 63];
    output += BASE64URL[(block >> 12) & 63];
    if (second !== undefined) output += BASE64URL[(block >> 6) & 63];
    if (third !== undefined) output += BASE64URL[block & 63];
  }
  return output;
}

export async function replayCapabilitySecret(
  approvalId: number,
  subjectId: string,
): Promise<string> {
  return base64Url(
    await sha256Bytes(`compass-replay-approval:${approvalId}:${subjectId}`),
  );
}

export async function replayCapabilityHash(secret: string): Promise<string> {
  return [...(await sha256Bytes(secret))]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export function opaqueApprovalToken(approvalId: number, secret: string): string {
  return `apr-${approvalId}.${secret}`;
}

export function parseOpaqueApprovalToken(
  token: string,
): { approvalId: number; secret: string } | null {
  const match = TOKEN_PATTERN.exec(token.trim());
  if (!match) return null;
  return { approvalId: Number(match[1]), secret: match[2]! };
}

export function constantTimeTextEqual(left: string, right: string): boolean {
  const length = Math.max(left.length, right.length);
  let mismatch = left.length ^ right.length;
  for (let index = 0; index < length; index += 1) {
    mismatch |= (left.charCodeAt(index) || 0) ^ (right.charCodeAt(index) || 0);
  }
  return mismatch === 0;
}
