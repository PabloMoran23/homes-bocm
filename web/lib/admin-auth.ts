/** Panel interno `/admin` — no enlazado desde la web pública. */

export const ADMIN_COOKIE = "homes_admin_v1";
const HMAC_SALT = "homes-bocm-admin-session-v1";

export function getAdminPassword(): string | undefined {
  const raw = process.env.ADMIN_PANEL_PASSWORD?.trim();
  return raw || undefined;
}

function bufferToHex(buf: ArrayBuffer): string {
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function adminSessionToken(password: string): Promise<string> {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    enc.encode(HMAC_SALT),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(password));
  return bufferToHex(sig);
}

export async function expectedAdminSessionToken(): Promise<string | null> {
  const pw = getAdminPassword();
  if (!pw) return null;
  return adminSessionToken(pw);
}

export async function isValidAdminSession(cookieValue: string | undefined): Promise<boolean> {
  if (!cookieValue) return false;
  const expected = await expectedAdminSessionToken();
  if (!expected) return false;
  return cookieValue === expected;
}

export function isAdminPath(pathname: string): boolean {
  return pathname === "/admin" || pathname.startsWith("/admin/") || pathname.startsWith("/api/admin");
}

export function isAdminPublicPath(pathname: string): boolean {
  return pathname === "/admin/login" || pathname === "/api/admin/auth";
}
